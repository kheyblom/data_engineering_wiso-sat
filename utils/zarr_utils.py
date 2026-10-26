"""Turning raw granules into store content, and writing it to icechunk.

Everything here is shared by every product: a reader hands over raw arrays on
the store's dimensions (``utils/granules.py``), and this module does the rest.

- **Masking.** Only the values the config declares in ``source_fill_values``
  are treated as fill, per source variable. Floats become NaN; integers keep
  their dtype and value and carry the sentinel as an explicit ``_FillValue``,
  as the style guide requires.
- **Unit conversion.** The factor comes from the nomenclature key's
  ``unit_conversion``, applied in float64 and stored in the source dtype. A
  geolocation coordinate can take one too.
- **Vertical order.** An array on a vertical dimension (``level``, ``layer``,
  ``level_2``) keeps its source's order and says which it is in a
  ``vertical_order`` attribute, from the reader's ``VERTICAL_ORDER``
  (naming pass N7, 2026-10-19).
- **Attributes.** Source attributes are carried, the config's
  ``variable_attrs`` go on top, and the nomenclature goes on last so a config
  cannot override the key. A source ``standard_name`` is retained unchanged
  and none is ever added.
- **Writing.** A store is appended to granule by granule along two dimensions
  at once: ``obs`` for the data and ``granule`` for the index. Both land in
  one commit, so a store can never hold observations its index does not
  account for. Resume reads the index back.

What differs from the gridded MSWEP/GLEAM pipelines: there is no dask and no
``open_mfdataset``. A granule is read whole into numpy by a worker process, and
appends do not land on chunk boundaries (orbit sizes vary), so each append
rewrites the store's trailing partial chunk. That is safe because there is
only ever one writer per branch.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess

import icechunk
import numpy as np
import xarray as xr
import zarr
from icechunk.xarray import to_icechunk
from zarr.codecs import BloscCodec

from .granules import (
    GRANULE_DIM, LOCATION_COORDINATES, RowRule, declared_rows, index_attrs, index_entries,
    index_fields, location_keys,
)
from .nomenclature import (
    conversion_factor,
    coordinate_factor,
    coordinates,
    key_path,
    variable as key_variable,
)
from .path_utils import (
    GEOLOCATION, format_attrs, load_reader, run_stores, source_product, template_fields,
)

LOG = logging.getLogger(__name__)

# branch every commit is written to
BRANCH = 'main'

# Every build commit says which granules it holds and which revision of this
# code wrote them. Resume does not parse these (it reads the index back from
# the store), but finalize tells build commits from its own by them and builds
# the history attribute from their revisions, and a person reading the history
# can see the progress. Commits written before 2026-10-18 carry no revision
COMMIT_MESSAGE = 'write granules {first}..{last} ({count}) @ {revision}'
COMMIT_PREFIX = 'write granules '
COMMIT_RE = re.compile(
    r'^write granules (?P<first>\S+)\.\.(?P<last>\S+) \((?P<count>\d+)\)'
    r'(?: @ (?P<revision>\S+))?$'
)

# time is int64 since 1900-01-01, proleptic_gregorian, in the coarsest unit
# that holds the source times exactly (style guide). The unit is per product,
# from the coordinate key: milliseconds for TROPOMI, nanoseconds for GOSAT,
# whose float64 seconds land on no coarser decimal grid
TIME_EPOCH = '1900-01-01'
TIME_CALENDAR = 'proleptic_gregorian'
# the CF unit word -> numpy's datetime64 unit
TIME_UNIT_CODES = {'seconds': 's', 'milliseconds': 'ms', 'microseconds': 'us', 'nanoseconds': 'ns'}
# the int64 a NaT encodes to, for a granule that holds no observations
TIME_FILL = np.iinfo('int64').min

# source attributes that describe the container, fill or time encoding rather
# than the quantity; the store sets its own. xarray refuses to write a time
# whose attributes already hold 'calendar'
DROPPED_ATTRS = ('_FillValue', 'missing_value', 'units', 'long_name', 'calendar')

# the style guide's vertical dimensions. Every product names them so, whatever
# its source calls them; a matrix's second axis is level_2 (naming pass N5, N6)
VERTICAL_DIMS = ('level', 'layer', 'level_2')
# which end of the column index 0 is, as the source orders it (N7)
VERTICAL_ORDERS = ('top_first', 'surface_first')

NOMENCLATURE_NOTE = (
    'Variable names, units and long names follow the internal data engineering '
    'nomenclature (nomenclature_data.md). The original -> canonical mapping for '
    'this product, including every unit conversion, is '
    'nomenclature-key_{source_name}.md in the data_engineering_wiso-sat repository. '
    'What the source published is preserved on each variable as '
    'original_variable_name, original_units and original_long_name.'
)

LAYOUT_NOTE = (
    'Level 2 observations on their native swath, one store per variable over '
    'the whole record. Every store of this product shares one obs axis and one '
    'granule index: observation i of any store is observation i of every '
    'other. time, lat and lon are in the geolocation store only. Observations '
    'are appended in source granule order and keep their source order within a '
    'granule; {time_order}'
)
# the end of the layout note, per the config's time_order. 'source' is the
# style guide's exception for files that are not in time order (TROPESS, user
# decision 2026-10-23)
TIME_ORDER_NOTES = {
    'sorted': 'time never decreases along obs.',
    'source': (
        'the source files are not in time order, so time is not monotonic '
        'along obs. Each granule\'s earliest and latest time are in the granule '
        'index (granule_time_start, granule_time_end).'
    ),
}


def time_order(settings):
    """The config's ``time_order``: whether time never decreases along obs.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        str: 'sorted' (the default: the build and verifier check that time
            never decreases) or 'source' (source order kept, time not
            monotonic, as the style guide allows for unordered files).

    Raises:
        ValueError: On any other value.
    """
    order = settings.get('time_order') or 'sorted'
    if order not in TIME_ORDER_NOTES:
        raise ValueError(f'time_order must be one of {sorted(TIME_ORDER_NOTES)}; it is {order!r}')
    return order


def layout_note(settings):
    """The ``layout`` global attribute for the config's time order.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        str: The note.
    """
    return LAYOUT_NOTE.format(time_order=TIME_ORDER_NOTES[time_order(settings)])


def code_revision():
    """The git revision of this working tree, for provenance.

    Returns:
        str: The short revision, '-dirty' if the tree has uncommitted changes,
            or 'unknown' if git cannot answer.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        revision = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, check=True, cwd=here,
        ).stdout.strip()
        dirty = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True, text=True, check=True, cwd=here,
        ).stdout.strip()
        return f'{revision}-dirty' if dirty else revision
    except Exception:
        # provenance is worth recording but not worth failing a run for
        return 'unknown'


def uncommitted_changes():
    """What ``git status`` reports for this working tree.

    Returns:
        list | None: ``git status --porcelain`` lines (empty when clean), or
            None if git cannot answer.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        output = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True, text=True, check=True, cwd=here,
        ).stdout
    except Exception:
        return None
    return [line for line in output.splitlines() if line.strip()]


def check_clean_tree(revision, settings):
    """Refuse to build from anything but a clean commit (user decision 2026-10-18).

    Every build commit is stamped with the revision that wrote it, and that
    stamp is permanent. A dirty tree makes it say ``-dirty``, which nobody can
    later explain from the store alone, so a build has to start from a
    committed tree.

    Only a fixture config may set ``allow_dirty_tree``. The pipeline test
    builds during development, and its stores are throwaway; the test checks
    that no other config sets it.

    Args:
        revision (str): From ``code_revision``.
        settings (dict): The loaded configuration.

    Raises:
        ValueError: If the tree has uncommitted or untracked changes, or git
            cannot say which revision this is.
    """
    if settings.get('allow_dirty_tree'):
        return
    if revision == 'unknown':
        raise ValueError('git cannot say which revision this is; build from a git checkout')
    if revision.endswith('-dirty'):
        changes = uncommitted_changes() or []
        raise ValueError(
            f'the working tree is not a clean commit ({len(changes)} changes, e.g. '
            f'{changes[:5]}); commit them, or move them out, before building: every '
            f'build commit is stamped with the revision that wrote it'
        )


def time_units(product):
    """The product's time units, from its coordinate key.

    Args:
        product (str): The product.

    Returns:
        tuple: The CF units string, e.g. 'milliseconds since 1900-01-01', and
            the matching numpy datetime64 unit code, e.g. 'ms'.

    Raises:
        ValueError: If the key's units are not '<unit> since 1900-01-01'.
    """
    units = coordinates(product)['time'].units
    word, _, epoch = units.partition(' since ')
    if epoch != TIME_EPOCH or word not in TIME_UNIT_CODES:
        raise ValueError(
            f'time units {units!r} in the {product} key must be one of '
            f'{sorted(TIME_UNIT_CODES)} since {TIME_EPOCH}'
        )
    return units, TIME_UNIT_CODES[word]


def vertical_order(settings):
    """The vertical order of the product's profiles, as its reader declares it.

    A format fact, so it lives in the reader beside its dimension renames.
    Each source keeps its own order (naming pass N7): no product is flipped.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        str: 'top_first' or 'surface_first'.

    Raises:
        ValueError: If the reader declares none, or something else. Only a
            product that stores a vertical dimension needs to declare it.
    """
    order = getattr(load_reader(settings), 'VERTICAL_ORDER', None)
    if order not in VERTICAL_ORDERS:
        raise ValueError(
            f'products/{source_product(settings)}.py must set VERTICAL_ORDER to one of '
            f'{VERTICAL_ORDERS} to store a vertical dimension; it is {order!r}'
        )
    return order


def configure_runtime(settings):
    """Resolve the settings that bound cost and memory, and log them.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        tuple: ``(num_workers, granules_per_commit)``.

    Raises:
        ValueError: If either is missing or not a positive integer. Both are
            scale settings, which live in per-product config rather than code.
    """
    resolved = []
    for key in ('num_workers', 'granules_per_commit'):
        value = settings.get(key)
        if not isinstance(value, int) or value < 1:
            raise ValueError(f'config must set {key} to a positive integer, got {value!r}')
        resolved.append(value)
    LOG.info(f'read workers: {resolved[0]}, granules per commit: {resolved[1]}')
    return tuple(resolved)


def resolve_chunks(settings):
    """The configured chunk lengths, checked.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        dict: ``{'obs': n, 'granule': n}``.

    Raises:
        ValueError: If either is missing. The style guide chunks only along
            ``obs``; ``granule`` sizes the index, which is small but appended.
    """
    chunks = settings.get('chunks') or {}
    missing = [name for name in ('obs', GRANULE_DIM) if not chunks.get(name)]
    if missing:
        raise ValueError(f'config does not chunk {missing}')
    extra = sorted(set(chunks) - {'obs', GRANULE_DIM})
    if extra:
        raise ValueError(
            f'config chunks {extra}; Level 2 stores chunk only along obs and '
            f'never split secondary dimensions'
        )
    return {'obs': int(chunks['obs']), GRANULE_DIM: int(chunks[GRANULE_DIM])}


# what every array the config's compression block does not name is written
# with: zarr's default, zstd with no shuffle
DEFAULT_COMPRESSOR = 'zstd'


def resolve_compression(settings):
    """The codecs for the arrays the config names, checked.

    A scale setting, so it lives in config (condition 3). Byte-shuffled blosc
    stores TROPOMI's 50-layer kernels, priors and pressure ~34% smaller than
    zarr's default zstd, losslessly (measured on two orbits, 2026-10-19).

    ``shard_obs`` (optional) packs the named arrays' chunks into shards of
    that many observations, one file each (user decision 2026-10-19). A
    50-wide float32 array's chunk is 131,072 obs, so unsharded it would hold
    ~249,000 chunk files in one directory; a shard of 4,194,304 obs, the
    configured ``chunks.obs``, holds 32 of them and gives the array as many
    files as a 1-D one. The chunk stays the unit a reader fetches, within the
    style guide's 5-40 MiB. Each commit rewrites the partly filled last shard,
    and ``finalize --expire`` reclaims the superseded copies.

    Every array not named keeps the default, unsharded, so stores built
    before this are unchanged.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        dict: Array name -> ``{'compressors': [BloscCodec], 'shard_obs': int |
            None}``; empty if the config sets none.

    Raises:
        ValueError: If the block has keys other than ``blosc``, ``shard_obs``
            and ``arrays``, lacks ``blosc`` or ``arrays``, names an array no
            store of the config holds, or sets a ``shard_obs`` that is not a
            positive multiple of ``chunks.obs``.
    """
    config = settings.get('compression') or {}
    if not config:
        return {}
    extra = sorted(set(config) - {'blosc', 'shard_obs', 'arrays'})
    if extra or not config.get('blosc') or not config.get('arrays'):
        raise ValueError(
            f'compression must set blosc and arrays, and may set shard_obs; it sets '
            f'{sorted(config)}'
        )
    source_name = source_product(settings)
    known = {name for store in run_stores(settings) for name in store_sources(source_name, store)}
    unknown = sorted(set(config['arrays']) - known)
    if unknown:
        raise ValueError(f'compression names arrays no store of this config holds: {unknown}')
    shard = config.get('shard_obs')
    if shard is not None:
        # a multiple of chunks.obs, so shard boundaries are chunk boundaries of
        # every unsharded array too; every halved obs chunk divides it
        length = resolve_chunks(settings)['obs']
        if not isinstance(shard, int) or shard < 1 or shard % length:
            raise ValueError(
                f'compression shard_obs must be a positive multiple of chunks.obs '
                f'({length}); it is {shard!r}'
            )
    # one codec per array: a codec instance is immutable, but each array's
    # typesize is filled in from its own dtype when it is created
    return {
        name: {'compressors': [BloscCodec(**config['blosc'])], 'shard_obs': shard}
        for name in config['arrays']
    }


def sharded_stores(settings):
    """The stores holding an array the config shards.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        list: Store variable slots, in run order.
    """
    sharded = {name for name, spec in resolve_compression(settings).items() if spec['shard_obs']}
    source_name = source_product(settings)
    return [
        store for store in run_stores(settings)
        if sharded & set(store_sources(source_name, store))
    ]


def codecs_match(array, codecs):
    """Whether a stored array carries the compressor and shards the config gives it.

    Args:
        array (zarr.Array): The stored array.
        codecs (dict): From ``resolve_compression``.

    Returns:
        tuple: ``(ok, detail)``, the detail naming what is stored.
    """
    stored = [codec.to_dict() for codec in array.compressors]
    names = [entry['name'] for entry in stored]
    expected = codecs.get(array.basename)
    if expected is None:
        return names == [DEFAULT_COMPRESSOR] and array.shards is None, f'{names}, shards {array.shards}'
    want = expected['compressors'][0].to_dict()['configuration']
    shards = None
    if expected['shard_obs']:
        shards = (expected['shard_obs'],) + tuple(array.shape[1:])
    ok = names == ['blosc'] and array.shards == shards and all(
        stored[0]['configuration'].get(key) == want[key] for key in ('cname', 'clevel', 'shuffle')
    )
    return ok, f'{stored}, shards {array.shards}'


# the style guide's ceiling on one uncompressed chunk
MAX_CHUNK_BYTES = 40 * 2**20


def obs_chunk(length, itemsize, secondary=()):
    """An array's chunk length along ``obs``.

    The configured length, halved until one chunk fits the style guide's
    40 MiB. Halving keeps every array aligned with the others (user decision
    2026-10-18): each configured chunk boundary is also a boundary of every
    halved array, so one read of a range of observations meets the same
    boundaries in every store. A 1-D float32 or int64 array keeps the full
    length; TROPOMI's (obs, 4) corners take half.

    Args:
        length (int): The configured ``chunks.obs``.
        itemsize (int): Bytes per element as stored.
        secondary (tuple): The array's other dimension lengths, never split.

    Returns:
        int: The obs chunk length.
    """
    width = int(np.prod(secondary)) if len(secondary) else 1
    while length > 1 and length * itemsize * width > MAX_CHUNK_BYTES:
        length //= 2
    return length


def absent_fill(settings, source):
    """The value an integer source holds where it has no value of its own.

    That is where its file lacks the observation, which only a merged granule
    has (GOSAT: a sounding in the H2O file but not the DED file), or where the
    config declares the value a defect (CrIS ``land_flag``, R36). Floats are
    NaN there; an integer needs a value the source never writes, declared in
    ``absent_fill_values``.

    Args:
        settings (dict): The loaded configuration.
        source (str): The source path.

    Returns:
        int | None: The declared value.
    """
    return (settings.get('absent_fill_values') or {}).get(source)


def declared_fill(settings, source):
    """The fill values the config declares for one source variable.

    Args:
        settings (dict): The loaded configuration.
        source (str): The source path.

    Returns:
        list: The declared values, empty if none.
    """
    return list((settings.get('source_fill_values') or {}).get(source) or [])


def check_fill_config(settings, sources):
    """Fail if a per-source config setting names a source this product does not use.

    Args:
        settings (dict): The loaded configuration.
        sources (Iterable): Source paths the key and coordinate key know.

    Raises:
        ValueError: On an unknown source, or more than one value for a source.
    """
    declared = settings.get('source_fill_values') or {}
    for key in ('source_fill_values', 'absent_fill_values', 'allowed_on_rows_left_out', 'source_dtypes'):
        unknown = sorted(set(settings.get(key) or []) - set(sources))
        if unknown:
            raise ValueError(f'{key} names sources the key does not: {unknown}')
    masked = [str(entry.get('source')) for entry in settings.get('declared_masked_values') or []]
    unknown = sorted(set(masked) - set(sources))
    if unknown:
        raise ValueError(f'declared_masked_values names sources the key does not: {unknown}')
    for source, dtype in (settings.get('source_dtypes') or {}).items():
        if np.dtype(dtype).kind not in 'iu':
            # a declared cast unifies integer widths that drift between files;
            # a float is never narrowed or widened
            raise ValueError(f'source_dtypes casts {source} to {dtype}; only integer casts are declared')
    for source, values in declared.items():
        if len(values or []) > 1:
            # an integer store can carry only one _FillValue, and no float
            # source in scope needs two
            raise ValueError(f'source_fill_values declares {len(values)} values for {source}')


def mask_and_convert(values, fill, factor, absent=None, absent_value=None, declared=None):
    """Mask declared fill, fill absent observations, and convert units.

    Args:
        values (numpy.ndarray): Raw values.
        fill (list): Declared fill values for this source.
        factor (float | None): The conversion factor, or None.
        absent (numpy.ndarray | None): Along ``obs``, True where the
            observation is not in this source's file.
        absent_value (int | None): What an integer source holds there, and
            where it has a declared defect.
        declared (numpy.ndarray | None): Along ``obs``, True where the config
            declares the value a defect and the reader confirmed it; NaN, or
            ``absent_value`` for an integer.

    Returns:
        tuple: The stored values, the integer ``_FillValue`` to declare (None
            for floats), and how many values were masked as source fill.

    Raises:
        ValueError: If an integer source needs a unit conversion, which would
            change its dtype; if an integer source has absent observations or
            declared defects and no declared value for them, or a value the
            source itself writes; or if its source fill and absent value
            differ, since an integer store carries only one ``_FillValue``.
    """
    dtype = values.dtype
    is_float = np.issubdtype(dtype, np.floating)

    def along_obs(mask):
        # broadcast a per-observation mask over any secondary dimensions
        mask = np.zeros(values.shape[0], dtype=bool) if mask is None else mask
        return np.broadcast_to(mask.reshape(mask.shape + (1,) * (values.ndim - 1)), values.shape)

    absent = along_obs(absent)
    declared = along_obs(declared)
    masked = np.zeros(values.shape, dtype=bool)
    for value in fill:
        masked |= (values == np.asarray(value, dtype=dtype)) & ~absent
    count = int(masked.sum())

    if not is_float:
        if factor is not None:
            raise ValueError('an integer source cannot take a unit conversion')
        source_fill = np.asarray(fill[0], dtype=dtype) if fill else None
        # an integer has no NaN: an absent observation and a declared defect
        # both hold the declared absent fill
        replaced = absent | declared
        if not replaced.any():
            return values, source_fill, count
        if absent_value is None:
            raise ValueError(
                'an integer source has absent observations or declared defects but no '
                'absent_fill_values entry in the config'
            )
        absent_value = np.asarray(absent_value, dtype=dtype)
        if source_fill is not None and source_fill != absent_value:
            raise ValueError(
                f'source fill {source_fill} and absent fill {absent_value} differ; '
                f'an integer store has one _FillValue'
            )
        if ((values == absent_value) & ~replaced).any():
            raise ValueError(
                f'absent fill {absent_value} occurs in the source itself, so it '
                f'could not tell a missing value from a real one'
            )
        out = values.copy()
        out[replaced] = absent_value
        return out, absent_value, count

    masked |= absent | declared
    if factor is None:
        out = values.copy() if masked.any() else values
        out[masked] = np.nan
        return out, None, count

    # masked before converting, so a fill sentinel is never scaled (9.97e36 x
    # 1000 overflows float32). float64 so the factor is applied once at full
    # precision; the store keeps the source dtype, per the style guide
    wide = values.astype('float64')
    wide[masked] = np.nan
    wide *= factor
    with np.errstate(over='ignore'):
        out = wide.astype(dtype)
    overflowed = np.isinf(out) & np.isfinite(wide)
    if overflowed.any():
        raise ValueError(
            f'{int(overflowed.sum())} values overflow {dtype} after the unit '
            f'conversion; an undeclared fill value is the likely cause'
        )
    return out, None, count


def unit_conversion_note(entry, source_units):
    """The ``unit_conversion`` attribute for a variable.

    Args:
        entry (nomenclature.Variable): The key row.
        source_units (str): The units the source file carries.

    Returns:
        str: What was done to reach the canonical units.
    """
    if entry.unit_conversion == 'none':
        if source_units == entry.units:
            return 'none -- the source already publishes the canonical units'
        return (
            f'none -- {source_units or "(no units attribute)"!r} and '
            f'{entry.units!r} are the same unit; respelled only, no value changed'
        )
    return (
        f'{entry.unit_conversion} -- {source_units!r} to {entry.units!r}, '
        f'multiplied in float64 and stored in the source dtype'
    )


def variable_attrs(product, canonical, array, settings, fill):
    """A variable store's data variable attributes.

    Args:
        product (str): The product.
        canonical (str): The canonical name.
        array (SourceArray): The variable as read from the first granule.
        settings (dict): The loaded configuration.
        fill (list): Declared fill values.

    Returns:
        dict: The attributes.
    """
    entry = key_variable(product, canonical)
    source = dict(array.attrs)
    attrs = {key: value for key, value in source.items() if key not in DROPPED_ATTRS}
    attrs.update(format_attrs(settings, canonical, 'variable_attrs'))
    attrs.update(
        {
            'long_name': entry.long_name,
            'units': entry.units,
            'original_variable_name': entry.original,
            'original_units': str(source.get('units', '')),
            'original_long_name': str(source.get('long_name', '')),
            'unit_conversion': unit_conversion_note(entry, str(source.get('units', ''))),
            'dimension_changes': array.dimension_note,
        }
    )
    if fill:
        attrs['source_fill_values_masked'] = (
            f'{", ".join(repr(value) for value in fill)}: undeclared in the source '
            f'(no _FillValue), declared in the config and masked'
            + ('' if np.issubdtype(array.values.dtype, np.floating) else
               '; integer, so kept as the stored value and declared as _FillValue')
        )
    defects = [entry for entry in settings.get('declared_masked_values') or []
               if entry.get('source') == entry_source(product, canonical)]
    if defects:
        attrs['declared_defects_masked'] = ' '.join(
            str(entry.get('reason', '')).strip() for entry in defects
        )
    cast = (settings.get('source_dtypes') or {}).get(entry_source(product, canonical))
    if cast:
        attrs['dtype_change'] = (
            f'stored as {cast}: the source files publish this integer at different '
            f'widths (declared in the config, source_dtypes); every value fits'
        )
    return attrs


def entry_source(product, canonical):
    """The source path a canonical variable is read from.

    Args:
        product (str): The product.
        canonical (str): The canonical name.

    Returns:
        str: Its ``original_variable_name``.
    """
    return key_variable(product, canonical).original


def coordinate_attrs(product, name, array, settings, fill):
    """Attributes of one geolocation coordinate.

    Args:
        product (str): The product.
        name (str): 'time', 'lat', 'lon', ...
        array (SourceArray): As read from the first granule.
        settings (dict): The loaded configuration.
        fill (list): Declared fill values.

    Returns:
        dict: The attributes. ``time`` carries no ``units``: xarray writes them
            from the encoding, and refuses a write where both are set.
    """
    entry = coordinates(product)[name]
    source = dict(array.attrs)
    attrs = {key: value for key, value in source.items() if key not in DROPPED_ATTRS}
    attrs.update(
        {
            'long_name': str(source.get('long_name', name)),
            'original_variable_name': entry.original,
            'original_units': str(source.get('units', '')),
            'dimension_changes': array.dimension_note,
        }
    )
    if entry.unit_conversion == 'decoded':
        attrs['unit_conversion'] = f'decoded from {entry.original_units!r} to a timestamp'
        if 'calendar' in source:
            attrs['original_calendar'] = str(source['calendar'])
    elif entry.unit_conversion == 'none':
        attrs['units'] = entry.units
        attrs['unit_conversion'] = (
            'none -- respelled only, no value changed'
            if entry.units != source.get('units') else 'none'
        )
    else:
        attrs['units'] = entry.units
        attrs['unit_conversion'] = unit_conversion_note(entry, str(source.get('units', '')))
    if fill:
        attrs['source_fill_values_masked'] = ', '.join(repr(value) for value in fill)
    return attrs


def row_rule(settings, granules=()):
    """The rule for which source rows are observations (``utils/granules.py``).

    Args:
        settings (dict): The loaded configuration.
        granules (list): The reader's listing, which declared rows are
            checked against; needed only when the config declares any.

    Returns:
        RowRule: Location sources from the key, fills, allowed sources and
            declared rows from the config.

    Raises:
        ValueError: If the config declares rows and the product's reader
            cannot apply them, which would otherwise ignore them silently.
    """
    key = coordinates(source_product(settings))
    location = tuple(key[name].original for name in LOCATION_COORDINATES)
    fills = {
        source: tuple(values or [])
        for source, values in (settings.get('source_fill_values') or {}).items()
    }
    declared = {}
    if settings.get('declared_rows_left_out'):
        if not getattr(load_reader(settings), 'DECLARED_ROWS', False):
            raise ValueError(
                f'declared_rows_left_out is set, but the {source_product(settings)} reader '
                f'does not apply declared rows'
            )
        declared = declared_rows(settings, granules)
    masked = tuple(dict(entry) for entry in settings.get('declared_masked_values') or [])
    if masked and not getattr(load_reader(settings), 'DECLARED_MASKS', False):
        raise ValueError(
            f'declared_masked_values is set, but the {source_product(settings)} reader '
            f'does not apply declared masks'
        )
    for entry in masked:
        if not entry.get('source') or not str(entry.get('reason', '')).strip():
            raise ValueError(f'declared_masked_values entry {entry}: a source and a reason are required')
    return RowRule(
        location=location,
        fills=fills,
        allowed=tuple(settings.get('allowed_on_rows_left_out') or []),
        declared=declared,
        masked=masked,
    )


def store_sources(product, store):
    """The source paths a store is built from, by store variable name.

    Args:
        product (str): The product.
        store (str): The store's variable slot.

    Returns:
        dict: Store variable name -> source path.
    """
    if store == GEOLOCATION:
        return {name: entry.original for name, entry in coordinates(product).items()}
    return {store: key_variable(product, store).original}


def time_source(product):
    """The source path of the time coordinate.

    Args:
        product (str): The product.

    Returns:
        str: e.g. 'instrument/time'.
    """
    return coordinates(product)['time'].original


def assemble(store, datas, obs_start, settings):
    """The pieces of one append to one store.

    Args:
        store (str): The store's variable slot.
        datas (list): :class:`GranuleData` in source order, all to be written.
        obs_start (int): Where along ``obs`` the first of them begins.
        settings (dict): The loaded configuration.

    Returns:
        tuple: ``(observations, index, masked, fills)``: a Dataset on
            ``obs``, a Dataset of index coordinates on ``granule``, the masked
            count per variable, and the ``_FillValue`` each integer variable
            declares.

    Raises:
        ValueError: If the granules disagree on a variable's dtype or
            dimensions.
    """
    source_name = source_product(settings)
    casts = settings.get('source_dtypes') or {}
    variables, masked, fills = {}, {}, {}
    for name, source in store_sources(source_name, store).items():
        arrays = [declared_cast(data.arrays[source], casts.get(source), data.granule.id)
                  for data in datas]
        # attributes come from the first granule whose file holds the source:
        # in a merged granule that lacks one file, the source is absent
        # throughout and carries none (TROPESS's one-sided days, R23)
        first = next(
            (array for array in arrays if array.absent is None or not array.absent.all()), arrays[0]
        )
        for data, other in zip(datas, arrays):
            if other.values.dtype != first.values.dtype or other.dims != first.dims:
                raise ValueError(
                    f'{source} is {other.values.dtype} {other.dims} in granule '
                    f'{data.granule.id} but {first.values.dtype} {first.dims} elsewhere'
                )
        values = np.concatenate([array.values for array in arrays])
        absent = None
        if any(array.absent is not None for array in arrays):
            absent = np.concatenate([
                np.zeros(data.n_obs, dtype=bool) if array.absent is None else array.absent
                for data, array in zip(datas, arrays)
            ])
        declared = None
        if any(array.masked is not None for array in arrays):
            declared = np.concatenate([
                np.zeros(data.n_obs, dtype=bool) if array.masked is None else array.masked
                for data, array in zip(datas, arrays)
            ])
        fill = declared_fill(settings, source)

        if store == GEOLOCATION:
            factor = coordinate_factor(coordinates(source_name)[name])
            attrs = coordinate_attrs(source_name, name, first, settings, fill)
        else:
            factor = conversion_factor(key_variable(source_name, name).unit_conversion)
            attrs = variable_attrs(source_name, name, first, settings, fill)

        if np.issubdtype(values.dtype, np.datetime64):
            # the reader decodes to the key's unit; anything else would be
            # rounded or padded by the encoding rather than stored exactly
            unit = time_units(source_name)[1]
            if np.datetime_data(values.dtype)[0] != unit:
                raise ValueError(
                    f'{source} decodes to {values.dtype}, but the key stores '
                    f'time in {unit}'
                )
            stored, integer_fill, count = values, None, 0
        else:
            stored, integer_fill, count = mask_and_convert(
                values, fill, factor, absent, absent_fill(settings, source), declared
            )
        if absent is not None and absent.any():
            attrs['absent_observations'] = (
                'This product merges several source files per granule into one '
                'obs axis. Where an observation is not in the file this '
                f'variable comes from, it holds '
                f'{"NaN" if np.issubdtype(values.dtype, np.floating) else integer_fill}, '
                'which no source value equals.'
            )
        if set(first.dims) & set(VERTICAL_DIMS):
            attrs['vertical_order'] = vertical_order(settings)
        if integer_fill is not None:
            fills[name] = integer_fill
        variables[name] = xr.Variable(first.dims, stored, attrs)
        masked[name] = count

    observations = xr.Dataset(variables)
    entries = index_entries(datas, time_source(source_name), obs_start)
    reader = load_reader(settings)
    fields, attrs = index_fields(reader, settings), index_attrs(reader, settings)
    if set(entries) != set(fields):
        raise ValueError(
            f'the reader returned index fields {sorted(entries)}, not its declared {sorted(fields)}'
        )
    index = xr.Dataset(
        coords={field: (GRANULE_DIM, entries[field], attrs[field]) for field in fields}
    )
    return observations, index, masked, fills


def declared_cast(array, dtype, granule):
    """A source array cast to the integer dtype the config declares for it.

    TROPESS publishes some flags and indices at int16, int32 or int64 by
    version (R16); the store holds one dtype, declared in ``source_dtypes``.

    Args:
        array (SourceArray): The array as read.
        dtype (str | None): The declared dtype, or None to keep the source's.
        granule (str): The granule id, for messages.

    Returns:
        SourceArray: The array, its values cast when a dtype is declared.

    Raises:
        ValueError: If a value does not fit the declared dtype.
    """
    if dtype is None or array.values.dtype == np.dtype(dtype):
        return array
    cast = array.values.astype(dtype)
    if not np.array_equal(cast.astype(array.values.dtype), array.values):
        raise ValueError(f'granule {granule}: a value does not fit the declared dtype {dtype}')
    return array._replace(values=cast)


def global_attrs(settings, store, versions):
    """The global attributes a store is created with.

    Coverage and provenance are not here: they describe a record and an audit
    that are not finished at the first write, and ``finalize_wisosat_zarr.py
    --attrs`` writes them once they are.

    Args:
        settings (dict): The loaded configuration.
        store (str): The store's variable slot.
        versions (dict): ``{'processor': ...}`` as read from the granules.

    Returns:
        dict: The attributes.
    """
    source_name = source_product(settings)
    derived = {
        'cdm_data_type': 'Point',
        'temporal_frequency': template_fields(settings, store)['frequency'],
        'original_temporal_frequency': settings['temporal_resolution'],
        'source_processor_version': versions['processor'],
        'nomenclature': NOMENCLATURE_NOTE.format(source_name=source_name),
        'layout': layout_note(settings),
        'quality_filtering': (
            'none applied. Every observation in the source files is kept. '
            'Upstream guidance: ' + str(settings.get('filtering_guidance', '')).strip()
        ),
    }
    return derived | format_attrs(settings, store)


def build_encoding(observations, index, chunks, fills, product, codecs):
    """Zarr encoding for every variable of a first write.

    Args:
        observations (xarray.Dataset): The first append's data, on ``obs``.
        index (xarray.Dataset): Its index entries, on ``granule``.
        chunks (dict): From ``resolve_chunks``.
        fills (dict): Integer variable -> the ``_FillValue`` it declares.
        product (str): The product, whose key sets the time units.
        codecs (dict): From ``resolve_compression``; an array not in it keeps
            zarr's default, unsharded.

    Returns:
        dict: Encoding for ``to_icechunk``.
    """
    units, _ = time_units(product)
    encoding = {}
    for dataset in (observations, index):
        for name, variable in dataset.variables.items():
            # only the leading dimension is chunked; secondary dimensions stay
            # whole, per the style guide. Along obs, a wide array takes a
            # halved length so its chunks stay within the guide's size
            leading = chunks[variable.dims[0]]
            if variable.dims[0] == 'obs':
                itemsize = 8 if np.issubdtype(variable.dtype, np.datetime64) else variable.dtype.itemsize
                leading = obs_chunk(leading, itemsize, tuple(variable.shape[1:]))
            shape = (leading,) + tuple(variable.shape[1:])
            encoding[name] = {'chunks': shape}
            if name in codecs:
                encoding[name]['compressors'] = codecs[name]['compressors']
                if codecs[name]['shard_obs']:
                    encoding[name]['shards'] = (codecs[name]['shard_obs'],) + tuple(variable.shape[1:])
            if np.issubdtype(variable.dtype, np.datetime64):
                encoding[name].update(
                    {'units': units, 'calendar': TIME_CALENDAR, 'dtype': 'int64',
                     '_FillValue': TIME_FILL}
                )
            elif np.issubdtype(variable.dtype, np.floating):
                encoding[name]['_FillValue'] = np.nan
            elif name in fills:
                encoding[name]['_FillValue'] = fills[name]
    return encoding


def open_repository(path):
    """Open the icechunk repository at a path, creating it if absent.

    Args:
        path (str): Directory holding the store.

    Returns:
        icechunk.Repository: The opened repository.
    """
    return icechunk.Repository.open_or_create(icechunk.local_filesystem_storage(path))


def open_existing_repository(path):
    """Open an icechunk repository that must already exist.

    Anything administrative uses this rather than ``open_repository``: a
    mistyped path would otherwise create an empty repository that every later
    report would truthfully describe.

    Args:
        path (str): Directory holding the store.

    Returns:
        icechunk.Repository: The opened repository.
    """
    return icechunk.Repository.open(icechunk.local_filesystem_storage(path))


def open_store(repository):
    """Open a store's branch tip read only, or None if nothing is written.

    Args:
        repository (icechunk.Repository): The repository.

    Returns:
        xarray.Dataset | None: The decoded store.
    """
    session = repository.readonly_session(branch=BRANCH)
    try:
        return xr.open_zarr(session.store, consolidated=False)
    except Exception:
        # a freshly created repository has an empty root group and no arrays
        return None


def committed_state(repository, granules, store):
    """How far a store has got, checked against the granule listing.

    Args:
        repository (icechunk.Repository): The store's repository.
        granules (list): Every granule of the record, in source order.
        store (str): The store's variable slot, for messages.

    Returns:
        dict: ``n_granules``, ``n_obs`` and ``last_time`` (the last committed
            granule's end time, or None).

    Raises:
        ValueError: If the store's index is not a prefix of the listing, or its
            obs length disagrees with its own index. Either means it was built
            from something else, and resuming would append onto it.
    """
    stored = open_store(repository)
    if stored is None:
        return {'n_granules': 0, 'n_obs': 0, 'last_time': None}

    ids = [str(value) for value in stored['granule_id'].values]
    expected = [granule.id for granule in granules[: len(ids)]]
    if ids != expected:
        raise ValueError(
            f'{store}: the granules already in the store are not the first '
            f'{len(ids)} of the raw listing; delete the store to rebuild it'
        )
    counts = stored['granule_obs_count'].values
    n_obs = int(stored.sizes.get('obs', 0))
    if int(counts.sum()) != n_obs:
        raise ValueError(
            f'{store}: the index accounts for {int(counts.sum())} observations '
            f'but the store holds {n_obs}; delete the store to rebuild it'
        )
    last = stored['granule_time_end'].values[-1] if ids else None
    return {'n_granules': len(ids), 'n_obs': n_obs, 'last_time': last}


def repeat_look_back(settings):
    """How many granules back the repeat check looks (``check_repeats``).

    Args:
        settings (dict): The loaded configuration.

    Returns:
        int: ``repeated_footprints.look_back`` where a config declares the
            rule (CrIS R37: 2), else 1.
    """
    rule = settings.get('repeated_footprints') or {}
    return int(rule.get('look_back', 1))


def stored_seam_keys(repository, before, look_back=1):
    """The location keys of the last stored granules with observations before a point.

    A resumed run checks its first granule against these for repeats
    (``check_repeats``), as ``last_time`` serves ``check_time``.

    Args:
        repository (icechunk.Repository): The geolocation store's repository.
        before (int): The position of the first granule the run writes.
        look_back (int): How many granules with observations to return.

    Returns:
        list | None: One key set (``location_keys``) per granule, oldest
            first; None if no earlier granule has observations.
    """
    stored = open_store(repository)
    if stored is None or not before:
        return None
    counts = stored['granule_obs_count'].values[:before]
    nonzero = np.flatnonzero(counts)
    if not nonzero.size:
        return None
    seams = []
    for last in nonzero[-look_back:]:
        lo = int(stored['granule_obs_start'].values[last])
        rows = slice(lo, lo + int(counts[last]))
        seams.append(set(location_keys(*(stored[name][rows].values for name in LOCATION_COORDINATES))))
    return seams


def write_append(repository, observations, index, encoding, message):
    """Append one run of granules to a store as one commit.

    Args:
        repository (icechunk.Repository): The store's repository.
        observations (xarray.Dataset): The data, on ``obs``.
        index (xarray.Dataset): Its index entries, on ``granule``.
        encoding (dict | None): For the first write, which creates the arrays;
            None for every later one, which extends them.
        message (str): The commit message.

    Returns:
        str: The snapshot id.
    """
    session = repository.writable_session(branch=BRANCH)
    if encoding is not None:
        merged = xr.merge([observations, index])
        # set explicitly: merge's attribute policy has changed between xarray
        # releases, and this one drops them
        merged.attrs = dict(observations.attrs)
        to_icechunk(merged, session, mode='w', encoding=encoding)
    else:
        # an append replaces the group's attributes with the appended
        # dataset's, so each append carries the ones already stored, or the
        # second commit would strip the store's global attributes
        stored = dict(zarr.open_group(session.store, mode='r').attrs)
        stored.pop('coordinates', None)
        observations = observations.assign_attrs(stored)
        index = index.assign_attrs(stored)
        # two appends in one session: the data and its index commit together
        # or not at all, so the index can never disagree with the data
        to_icechunk(observations, session, append_dim='obs')
        to_icechunk(index, session, append_dim=GRANULE_DIM)
    return session.commit(message)


def log_key(product):
    """Log which key the run is reading, so a log names its own nomenclature.

    Args:
        product (str): The product.
    """
    LOG.info(f'nomenclature key {key_path(product)}')
