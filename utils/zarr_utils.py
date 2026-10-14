"""Turning raw granules into store content, and writing it to icechunk.

Everything here is shared by every product: a reader hands over raw arrays on
the store's dimensions (``utils/granules.py``), and this module does the rest.

- **Masking.** Only the values the config declares in ``source_fill_values``
  are treated as fill, per source variable. Floats become NaN; integers keep
  their dtype and value and carry the sentinel as an explicit ``_FillValue``,
  as the style guide requires.
- **Unit conversion.** The factor comes from the nomenclature key's
  ``unit_conversion``, applied in float64 and stored in the source dtype.
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

import icechunk
import numpy as np
import xarray as xr
import zarr
from icechunk.xarray import to_icechunk

from .granules import GRANULE_DIM, INDEX_ATTRS, INDEX_FIELDS, index_entries
from .nomenclature import (
    conversion_factor,
    coordinates,
    key_path,
    variable as key_variable,
)
from .path_utils import GEOLOCATION, format_attrs, template_fields

LOG = logging.getLogger(__name__)

# branch every commit is written to
BRANCH = 'main'

# Every build commit says which granules it holds. Resume does not parse these
# (it reads the index back from the store), but finalize tells build commits
# from its own by them, and a person reading the history can see the progress
COMMIT_MESSAGE = 'write granules {first}..{last} ({count})'
COMMIT_PREFIX = 'write granules '

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

NOMENCLATURE_NOTE = (
    'Variable names, units and long names follow the internal data engineering '
    'nomenclature (nomenclature_data.md). The original -> canonical mapping for '
    'this product, including every unit conversion, is '
    'nomenclature-key_{product}.md in the data_engineering_wiso-sat repository. '
    'What the source published is preserved on each variable as '
    'original_variable_name, original_units and original_long_name.'
)

LAYOUT_NOTE = (
    'Level 2 observations on their native swath, one store per variable over '
    'the whole record. Every store of this product shares one obs axis and one '
    'granule index: observation i of any store is observation i of every '
    'other. time, lat and lon are in the geolocation store only. Observations '
    'are appended in source granule order and keep their source order within a '
    'granule; time never decreases along obs.'
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


def absent_fill(settings, source):
    """The value an integer source holds where its file lacks the observation.

    Only a merged granule has such observations (GOSAT: a sounding in the H2O
    file but not the DED file). Floats are NaN there; an integer needs a value
    the source never writes, declared in ``absent_fill_values``.

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
    """Fail if ``source_fill_values`` names a source this product does not use.

    Args:
        settings (dict): The loaded configuration.
        sources (Iterable): Source paths the key and coordinate key know.

    Raises:
        ValueError: On an unknown source, or more than one value for a source.
    """
    declared = settings.get('source_fill_values') or {}
    for key in ('source_fill_values', 'absent_fill_values'):
        unknown = sorted(set(settings.get(key) or {}) - set(sources))
        if unknown:
            raise ValueError(f'{key} names sources the key does not: {unknown}')
    for source, values in declared.items():
        if len(values or []) > 1:
            # an integer store can carry only one _FillValue, and no float
            # source in scope needs two
            raise ValueError(f'source_fill_values declares {len(values)} values for {source}')


def mask_and_convert(values, fill, factor, absent=None, absent_value=None):
    """Mask declared fill, fill absent observations, and convert units.

    Args:
        values (numpy.ndarray): Raw values.
        fill (list): Declared fill values for this source.
        factor (float | None): The conversion factor, or None.
        absent (numpy.ndarray | None): Along ``obs``, True where the
            observation is not in this source's file.
        absent_value (int | None): What an integer source holds there.

    Returns:
        tuple: The stored values, the integer ``_FillValue`` to declare (None
            for floats), and how many values were masked as source fill.

    Raises:
        ValueError: If an integer source needs a unit conversion, which would
            change its dtype; if an integer source has absent observations and
            no declared value for them, or a value the source itself writes; or
            if its source fill and absent value differ, since an integer store
            carries only one ``_FillValue``.
    """
    dtype = values.dtype
    is_float = np.issubdtype(dtype, np.floating)
    absent = np.zeros(values.shape[0], dtype=bool) if absent is None else absent
    # broadcast the per-observation mask over any secondary dimensions
    absent = absent.reshape(absent.shape + (1,) * (values.ndim - 1))
    absent = np.broadcast_to(absent, values.shape)
    masked = np.zeros(values.shape, dtype=bool)
    for value in fill:
        masked |= (values == np.asarray(value, dtype=dtype)) & ~absent
    count = int(masked.sum())

    if not is_float:
        if factor is not None:
            raise ValueError('an integer source cannot take a unit conversion')
        declared = np.asarray(fill[0], dtype=dtype) if fill else None
        if not absent.any():
            return values, declared, count
        if absent_value is None:
            raise ValueError(
                'an integer source has absent observations but no '
                'absent_fill_values entry in the config'
            )
        absent_value = np.asarray(absent_value, dtype=dtype)
        if declared is not None and declared != absent_value:
            raise ValueError(
                f'source fill {declared} and absent fill {absent_value} differ; '
                f'an integer store has one _FillValue'
            )
        if ((values == absent_value) & ~absent).any():
            raise ValueError(
                f'absent fill {absent_value} occurs in the source itself, so it '
                f'could not tell a missing observation from a real value'
            )
        out = values.copy()
        out[absent] = absent_value
        return out, absent_value, count

    masked |= absent
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
    return attrs


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
    else:
        attrs['units'] = entry.units
        attrs['unit_conversion'] = (
            'none -- respelled only, no value changed'
            if entry.units != source.get('units') else 'none'
        )
    if fill:
        attrs['source_fill_values_masked'] = ', '.join(repr(value) for value in fill)
    return attrs


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
    product = settings['product']
    variables, masked, fills = {}, {}, {}
    for name, source in store_sources(product, store).items():
        first = datas[0].arrays[source]
        for data in datas[1:]:
            other = data.arrays[source]
            if other.values.dtype != first.values.dtype or other.dims != first.dims:
                raise ValueError(
                    f'{source} is {other.values.dtype} {other.dims} in granule '
                    f'{data.granule.id} but {first.values.dtype} {first.dims} before it'
                )
        values = np.concatenate([data.arrays[source].values for data in datas])
        absent = None
        if any(data.arrays[source].absent is not None for data in datas):
            absent = np.concatenate([
                np.zeros(data.n_obs, dtype=bool) if data.arrays[source].absent is None
                else data.arrays[source].absent
                for data in datas
            ])
        fill = declared_fill(settings, source)

        if store == GEOLOCATION:
            factor = None
            attrs = coordinate_attrs(product, name, first, settings, fill)
        else:
            factor = conversion_factor(key_variable(product, name).unit_conversion)
            attrs = variable_attrs(product, name, first, settings, fill)

        if np.issubdtype(values.dtype, np.datetime64):
            # the reader decodes to the key's unit; anything else would be
            # rounded or padded by the encoding rather than stored exactly
            unit = time_units(product)[1]
            if np.datetime_data(values.dtype)[0] != unit:
                raise ValueError(
                    f'{source} decodes to {values.dtype}, but the key stores '
                    f'time in {unit}'
                )
            stored, integer_fill, count = values, None, 0
        else:
            stored, integer_fill, count = mask_and_convert(
                values, fill, factor, absent, absent_fill(settings, source)
            )
        if first.absent is not None:
            attrs['absent_observations'] = (
                'This product merges several source files per granule into one '
                'obs axis. Where an observation is not in the file this '
                f'variable comes from, it holds '
                f'{"NaN" if np.issubdtype(values.dtype, np.floating) else integer_fill}, '
                'which no source value equals.'
            )
        if integer_fill is not None:
            fills[name] = integer_fill
        variables[name] = xr.Variable(first.dims, stored, attrs)
        masked[name] = count

    observations = xr.Dataset(variables)
    entries = index_entries(datas, time_source(product), obs_start)
    index = xr.Dataset(
        coords={
            field: (GRANULE_DIM, entries[field], INDEX_ATTRS[field]) for field in INDEX_FIELDS
        }
    )
    return observations, index, masked, fills


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
    product = settings['product']
    derived = {
        'cdm_data_type': 'Point',
        'temporal_frequency': template_fields(settings, store)['frequency'],
        'original_temporal_frequency': settings['temporal_resolution'],
        'source_processor_version': versions['processor'],
        'nomenclature': NOMENCLATURE_NOTE.format(product=product),
        'layout': LAYOUT_NOTE,
        'quality_filtering': (
            'none applied. Every observation in the source files is kept. '
            'Upstream guidance: ' + str(settings.get('filtering_guidance', '')).strip()
        ),
    }
    return derived | format_attrs(settings, store)


def build_encoding(observations, index, chunks, fills, product):
    """Zarr encoding for every variable of a first write.

    Args:
        observations (xarray.Dataset): The first append's data, on ``obs``.
        index (xarray.Dataset): Its index entries, on ``granule``.
        chunks (dict): From ``resolve_chunks``.
        fills (dict): Integer variable -> the ``_FillValue`` it declares.
        product (str): The product, whose key sets the time units.

    Returns:
        dict: Encoding for ``to_icechunk``.
    """
    units, _ = time_units(product)
    encoding = {}
    for dataset in (observations, index):
        for name, variable in dataset.variables.items():
            # only the leading dimension is chunked; secondary dimensions stay
            # whole, per the style guide
            shape = (chunks[variable.dims[0]],) + tuple(variable.shape[1:])
            encoding[name] = {'chunks': shape}
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
