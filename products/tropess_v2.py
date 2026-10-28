"""Reader for the NASA TROPESS (MUSES) HDO Level 2 v2 Full products: AIRS and CrIS-JPSS1.

v2 (collection ``VersionID`` 2, algorithm R1p25) continues the v1 Forward
Stream from 2026-06-01 (``docs/products/tropess.md``, "v2: answers" and the v2
production subset V1-V9, approved 2026-10-28). It is built from the **Full**
files only (user decision 2026-10-28), one file per day:

```
<raw>/TRPSFL2HDOAIRSFS.2/<YYYY>/TROPESS_AIRS-Aqua_L2_Full_HDO_<YYYYMMDD>_MUSES_R1p25_FS_F2p10_J1.nc
<raw>/TRPSFL2HDOCRS1FS.2/<YYYY>/TROPESS_CrIS-JPSS1_L2_Full_HDO_<YYYYMMDD>_MUSES_R1p25_FS_F2p10_J0.nc
```

What differs from v1 (``products/tropess.py``), and why this is a reader and
key of its own (V9, D1): the same canonical names come from other source
paths (``pressure`` from ``pressure_ret``, ``altitude`` from the forward-model
grid), and there is no Summary merge, no first-row defect (R22 does not occur
in v2) and no declared mask. What it shares with v1 is imported from it: the
platforms, the time decoding and its check against ``datetime_utc``, the R37
repeat rule (``select_repeats``, ``file_rank``) and the granule index fields.

The 34-wide retrieval dimension holds v1's 17 levels padded (R42), and Full's
``altitude`` sits on the 67-level forward-model grid (R43). This reader
returns every source whole, on its own dimensions; the config's slices,
checked remainders and lookup (``utils/selections.py``) take the 17 levels.

Format facts:
- **Groups:** a source is named by its path (``observation_ops/xa``); ``x``,
  ``pressure_ret``, ``time``, the position and the joint kernel blocks are at
  the root.
- **Dimensions:** ``target`` is the observation dimension; ``level_ret``
  becomes ``level``, and a matrix's second ``level_ret`` becomes ``level_2``
  (N6). ``level_fm`` keeps its name, except on ``retrieval/air_density``,
  which Full declares on ``level_fm`` but which holds the retrieval levels
  (twice, then fill; R42, checked on every observation): its axis is
  ``level`` (``SOURCE_RENAMES``).
- **Vertical order:** surface first.
- **Time** is float64 TAI seconds since 1993-01-01 (R3), checked against
  ``datetime_utc`` on every row, as v1.
- **Rows are not in time order** (R32 AIRS, R40 CrIS, the same situation as
  v1): the source order is kept (``time_order: source``).
- The int8-packed 67x67 blocks are never read.
"""

from __future__ import annotations

import datetime
import os

import netCDF4
import numpy as np

from products.tropess import (
    FOLDER_RE,
    INDEX_EXTRA,
    INDEX_LEFT_OUT,
    PLATFORMS,
    PRODUCTION_ATTR,  # noqa: F401  (file_rank's attribute, named here for readers of this module)
    decode_time,
    file_facts,
    file_rank,
    file_version,
    index_extra,
    read_attrs,
    select_repeats,
    time_problems,
)
from utils.granules import (
    Granule,
    GranuleData,
    SourceArray,
    decode_text,
    leaked_rows,
    observed_rows,
    squeeze_dims,
)

__all__ = ['decode_time', 'file_rank', 'file_version', 'index_extra']

# the Full collection folders: TRPSF..., and their type in the file names
FULL_KIND = 'F'
FULL_TYPE = 'Full'

OBSERVATION_DIM = 'target'
DIMENSION_RENAMES = {'level_ret': 'level'}
# a source whose declared dimension is not what it holds (R42)
SOURCE_RENAMES = {'retrieval/air_density': {'level_fm': 'level'}}
VERTICAL_ORDER = 'surface_first'

VERSION_ATTR = 'VersionID'
PLATFORM_ATTR = 'Platform'
# the config's platform picks the folders and files listed, as v1
LISTS_BY_PLATFORM = True
SHORT_NAME_ATTR = 'ShortName'

# what identifies an observation, for the repeat rule and its check
MATCH_SOURCES = ('time', 'latitude', 'longitude')

# config settings list_granules takes (utils/path_utils.listing_options)
LISTING_OPTIONS = ('version', 'version_product', 'platform', 'repeated_footprints')


def list_granules(raw_root, expected_empty=(), expected_unreadable=(), version=None,
                  version_product=None, platform=None, repeated_footprints=None):
    """Every day of one platform's v2 Full collection, in date order.

    Args:
        raw_root (str): The instrument's raw folder, e.g. ``.../raw/AIRS``.
        expected_empty (Iterable): Unused; must be empty.
        expected_unreadable (Iterable): Unused; must be empty.
        version (str): The collection version (``VersionID``), '2'.
        version_product (str): The stream, ``fs``.
        platform (str): The files' ``Platform`` attribute, a key of
            ``PLATFORMS``, which picks the folders and files.
        repeated_footprints (dict | None): The R37 rule; see
            ``products.tropess.select_repeats``.

    Returns:
        list: :class:`Granule` per day, one Full file each, with its rows left
            out where the config declares ``repeated_footprints``.

    Raises:
        FileNotFoundError: If the root does not exist.
        ValueError: If the options are missing, no folder matches, a folder
            holds another platform's or type's file, a day has two files, or
            the repeat rule leaves out other than the declared count.
    """
    if not os.path.isdir(raw_root):
        raise FileNotFoundError(f'no raw data directory at {raw_root}')
    if list(expected_empty) or list(expected_unreadable):
        raise ValueError('TROPESS has no empty or unreadable granules; leave both unset')
    if version is None or version_product is None:
        raise ValueError('a TROPESS config sets version (the collection) and version_product (the stream)')
    stream = str(version_product).upper()
    if platform not in PLATFORMS:
        raise ValueError(f'the config declares platform {platform!r}; this reader lists only {sorted(PLATFORMS)}')
    instruments, token = PLATFORMS[platform]

    found = {}
    for folder in sorted(os.listdir(raw_root)):
        match = FOLDER_RE.match(folder)
        if (match is None or match['kind'] != FULL_KIND or match['stream'] != stream
                or match['collection'] != str(version) or match['instrument'] not in instruments):
            continue
        base = os.path.join(raw_root, folder)
        places = [os.path.join(base, entry) for entry in sorted(os.listdir(base))
                  if entry.isdigit() and os.path.isdir(os.path.join(base, entry))] or [base]
        for place in places:
            for name in sorted(os.listdir(place)):
                try:
                    facts = file_facts(name)
                except ValueError:
                    continue
                if facts['type'] != FULL_TYPE or facts['stream'] != stream or facts['platform'] != token:
                    raise ValueError(f'{place} holds {name}, which is not {token} {FULL_TYPE} {stream}')
                if facts['date'] in found:
                    raise ValueError(f'two {token} Full files for {facts["date"]}: '
                                     f'{os.path.basename(found[facts["date"]])} and {name}')
                found[facts['date']] = os.path.join(place, name)
    if not found:
        raise ValueError(
            f'no {token} {stream} Full collection folder under {raw_root} has version {version!r}: '
            f'the configured processor version matches no files'
        )
    granules = [
        Granule(id=day, day=datetime.datetime.strptime(day, '%Y%m%d').date(), paths=(path,))
        for day, path in sorted(found.items())
    ]
    if repeated_footprints:
        left_out = select_repeats(granules, repeated_footprints)
        granules = [granule._replace(left_out=left_out[granule.id]) for granule in granules]
    return granules


def header_problems(attrs, path):
    """What a Full file's global attributes must say, given its name.

    Args:
        attrs (dict): Its global attributes, decoded.
        path (str): Its path.

    Returns:
        list: Problems, empty if the attributes agree with the name.
    """
    facts = file_facts(path)
    problems = []
    name = str(attrs.get(SHORT_NAME_ATTR, ''))
    if not (name.startswith('TRPSFL2HDO') and name.endswith(facts['stream'])):
        problems.append(f'ShortName {name!r} is not a Full {facts["stream"]} collection')
    source = str(attrs.get('source', ''))
    if source != f'MUSES v1.{facts["algorithm"][3:]}':
        problems.append(f'source {source!r} does not match the name\'s {facts["algorithm"]}')
    return problems


def index_extra_fields(settings):
    """The reader's own granule index fields under a config, as v1.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        dict: ``INDEX_EXTRA``, and ``INDEX_LEFT_OUT`` where the config
            declares ``repeated_footprints``.
    """
    return INDEX_EXTRA | (INDEX_LEFT_OUT if settings.get('repeated_footprints') else {})


def read_granule(granule, sources, time_source, rule):
    """Read one day's Full file, raw, keeping its observations.

    Args:
        granule (Granule): The day, from ``list_granules``.
        sources (Sequence): Source paths to read, whole.
        time_source (str): The time variable, returned decoded.
        rule (RowRule): Which rows are observations.

    Returns:
        GranuleData: The day's arrays on its observations, less the rows the
            repeat rule leaves out.

    Raises:
        KeyError: If the file lacks a source.
        ValueError: If the header disagrees with the name, time disagrees with
            datetime_utc, a row that is not an observation holds data, a row
            the listing leaves out is not an observation, or the config
            declares masks or rows this reader does not apply.
    """
    if rule.masked or rule.declared:
        raise ValueError('the TROPESS v2 reader applies no declared masks or declared rows')
    path = granule.paths[0]
    handle = netCDF4.Dataset(path, 'r')
    try:
        # masking off: only the config's declared fill counts as missing
        handle.set_auto_mask(False)
        attrs = read_attrs(handle)
        problems = header_problems(attrs, path)
        problems += time_problems(np.asarray(handle['time'][...]), np.asarray(handle['datetime_utc'][...]))
        raw = {source: np.asarray(handle[source][...]) for source in rule.location}
        keep = observed_rows(raw, rule)
        for source in sources:
            raw.setdefault(source, np.asarray(handle[source][...]))
        for source, values in raw.items():
            leaked = leaked_rows(source, values, keep, rule)
            if leaked:
                problems.append(f'{source} holds data on {leaked} rows with no time, latitude or longitude')
        if problems:
            raise ValueError(f'day {granule.id}: {"; ".join(problems)}')

        # R37: the rows the listing leaves out, each an observation
        if granule.left_out:
            drop = np.zeros(keep.size, dtype=bool)
            drop[list(granule.left_out)] = True
            if (drop & ~keep).any():
                raise ValueError(f'day {granule.id}: a row the listing leaves out is not an observation')
            keep = keep & ~drop
        n_obs = int(keep.sum())

        arrays = {}
        for source in sources:
            variable = handle[source]
            dims, values, note = squeeze_dims(
                raw[source][keep], variable.dimensions, OBSERVATION_DIM,
                DIMENSION_RENAMES | SOURCE_RENAMES.get(source, {}),
            )
            if dims.count('level') == 2:
                # a matrix over levels: rows retrieved, columns true (N6;
                # the ratio kernel equals hdo_hdo - h2o_hdo, finding 18)
                dims = ('obs', 'level', 'level_2')
                note = f'{note}; the second level -> level_2' if note != 'none' else 'the second level -> level_2'
            if source == time_source:
                values = decode_time(values)
                note = f'{note}; TAI93 seconds less the leap seconds, decoded to UTC'
            arrays[source] = SourceArray(
                dims=dims, values=values, attrs=read_attrs(variable), dimension_note=note,
            )
        return GranuleData(
            granule=granule,
            n_obs=n_obs,
            version=file_version(attrs.get(VERSION_ATTR, '')),
            attrs=attrs,
            arrays=arrays,
            n_source_rows=handle.dimensions[OBSERVATION_DIM].size,
            platform=str(attrs.get(PLATFORM_ATTR, '')),
            index_extra=index_extra(granule.paths, granule.left_out),
        )
    finally:
        handle.close()


def check_granule(handle):
    """Format invariants the verifier confirms on every file.

    Args:
        handle (h5py.File): An open Full file.

    Returns:
        list: Problems: a header that disagrees with the file name, or time
            that is not ``datetime_utc`` less the leap seconds.
    """
    attrs = {key: decode_text(value) for key, value in handle.attrs.items()}
    attrs = {key: value[0] if isinstance(value, np.ndarray) and value.size == 1 else value
             for key, value in attrs.items()}
    problems = header_problems(attrs, handle.filename)
    problems += time_problems(handle['time'][...], handle['datetime_utc'][...])
    return problems
