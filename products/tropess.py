"""Reader for the NASA TROPESS (MUSES) HDO Level 2 products: AIRS and CrIS.

The raw tree holds one folder per collection, as downloaded: the first
downloads flat (``<ShortName>_<version>-<stamp>/``), the later ones by year
(``<ShortName>.<version>/<YYYY>/``). One stream, product type and collection
version can span both (``docs/products/tropess.md``, Collections):

```
<raw>/TRPSDL2HDOAIRSORS.1/<YYYY>/TROPESS_AIRS-Aqua_L2_Standard_HDO_<YYYYMMDD>_MUSES_R1p6_RS_F0p8_J0.nc
<raw>/TRPSYL2HDOAIRSORS_1-20240806_185241/TROPESS_AIRS-Aqua_L2_Summary_HDO_<YYYYMMDD>_MUSES_R1p6_RS_F0p8_J0.nc
```

**One product per platform, stream and collection version** (user decisions
2026-10-22, 10-23 and 10-26): the config's ``version`` is the collection
version the files declare (``VersionID``), ``version_product`` the stream and
``platform`` the satellite, so the stores are ``wisosat.airs.v_1.rs...``,
``wisosat.cris_jpss1.v_1.fs...`` and so on. The listing takes only that
platform's, stream's and version's folders and files (``LISTING_OPTIONS``):
the CrIS-SNPP and CrIS-JPSS1 folders sit side by side under one raw root.
The special collections (``SC_AUS``) are out of scope; their names match
neither pattern below, so they are never listed.

**One granule is one day: the Standard file and the Summary file, merged**
(2026-10-23). Summary v1 is exactly the Standard rows with DOF > 1.1, in the
same order, with identical values (TESTING.md finding 15), so:

- the obs axis is the Standard file's rows; Summary's five column fields
  (``dd_col_p`` and the rest) are placed on their Standard rows by time,
  latitude and longitude, and are absent (NaN) elsewhere;
- every Summary row must match one Standard row, in order, the matched rows
  must be exactly those with ``signal_dof`` > 1.1, and every variable both
  files hold must be identical on them, except the first ``x`` (below), or
  the read fails;
- a day with only one of the two files is read from it alone, but only if the
  config declares it (``expected_partial_granules``; R23);
- a product with no Standard collection upstream (CrIS-SNPP RS) is declared
  Summary-only (``granule_types: [Summary]``), and its obs axis is the
  Summary rows.

**Declared, never detected** (``docs/products/tropess.md``):
- **R22, the first ``x`` of every Standard file**, is ``x_test``, the kernel
  applied to the true profile. The config declares it
  (``declared_masked_values``, ``where: first_row_of_standard_file``), and the
  read confirms it equals ``x_test`` before marking it; shared code stores
  NaN.
- **R36, CrIS ``land_flag``** is 1 on every row of some early files. The
  config lists their days (``where: every_row_of_listed_days``), and the read
  confirms every row holds the declared value before marking the whole file;
  shared code stores the integer's declared fill.
- **R18, a replaced file:** where upstream replaced a day's file, the config
  names the old one (``superseded_files``); the listing confirms the other
  is newer, in algorithm and ``ProductionDateTime``, and reads only it.
- **R37, footprints in two files:** a CrIS file covers up to two days either
  side of its date, so a footprint can be in two files. Where the config
  declares the rule (``repeated_footprints``), the listing reads every file's
  time, latitude, longitude, algorithm and ``ProductionDateTime``, keeps each
  footprint once, in the newest algorithm's file and then the latest
  produced, and fails unless it leaves out exactly the declared count. Each
  granule carries its rows left out (``Granule.left_out``); the read drops
  them and their Summary rows, and the index records how many.

Format facts:
- **Groups:** a source is named by its path, e.g. ``observation_ops/xa``;
  ``x``, ``pressure``, ``time`` and the position are at the root.
- **Observation dimension** is ``target``; ``level`` (17) keeps its name, and
  a matrix's second ``level`` becomes ``level_2`` (naming pass N6).
- **Vertical order:** surface first.
- **Time** is float64 TAI seconds since 1993-01-01 (R3), whole seconds in
  every file. ``decode_time`` subtracts the leap seconds since 1993 from a
  fixed table, and every read checks the result against ``datetime_utc`` on
  every row.
- **Rows are not in time order** (R32): the source order is kept
  (``time_order: source``, user decision 2026-10-23).
- **Integers drift in width** between versions (R16); the config declares one
  dtype each (``source_dtypes``) and shared code casts.

The build reads with netCDF4. The verifier reads each file with h5py and
places Summary rows by matching ``MATCH_SOURCES`` against the stored
geolocation; ``check_files`` repeats the merge rules from raw.
"""

from __future__ import annotations

import collections
import datetime
import os
import re

import h5py
import netCDF4
import numpy as np

from utils.granules import (
    Granule, GranuleData, SourceArray, decode_text, leaked_rows, observed_rows, same_bits,
    squeeze_dims,
)

# a collection folder: TRPS + D (Standard) / Y (Summary) / F (Full) + L2HDO +
# instrument + stream, then the collection version after '_' or '.'
FOLDER_RE = re.compile(
    r'^TRPS(?P<kind>[DYF])L2HDO(?P<instrument>[A-Z0-9]+?)(?P<stream>RS|FS)[._](?P<collection>\d+)(?:-\d{8}_\d{6})?$'
)
FILE_RE = re.compile(
    r'^TROPESS_(?P<platform>[A-Za-z0-9-]+)_L2_(?P<type>Standard|Summary)_HDO_(?P<date>\d{8})_MUSES_'
    r'(?P<algorithm>R\dp\d+)_(?P<stream>RS|FS)_(?P<format>F\dp\d+)(?:_(?P<joint>J\d))?\.nc$'
)
KINDS = {'D': 'Standard', 'Y': 'Summary'}
# the order of a granule's files, and so of its granule_file entry
TYPES = ('Standard', 'Summary')
# per Platform attribute: the instrument token(s) of its collection folders
# (AIRS RS is TRPS?L2HDOAIRSORS) and the platform token of its file names
PLATFORMS = {
    'Aqua': (('AIRS', 'AIRSO'), 'AIRS-Aqua'),
    'SUOMI-NPP': (('CRS',), 'CrIS-SNPP'),
    'JPSS-1': (('CRS1',), 'CrIS-JPSS1'),
}
# fill in time, latitude and longitude, which the repeat rule skips
LOCATION_FILL = -999
# the root attribute that orders two files of one algorithm (R18, R37)
PRODUCTION_ATTR = 'ProductionDateTime'
# the one rule repeated_footprints may declare (R37, user decision 2026-10-26)
REPEAT_KEEP = 'newest_algorithm_then_latest_production'

OBSERVATION_DIM = 'target'
DIMENSION_RENAMES = {}
VERTICAL_ORDER = 'surface_first'
LEVELS = 17

VERSION_ATTR = 'VersionID'
PLATFORM_ATTR = 'Platform'
# the config's platform picks the files listed (PLATFORMS), so a platform the
# files do not declare fails the listing rather than the first read
LISTS_BY_PLATFORM = True
SHORT_NAME_ATTR = 'ShortName'

# what identifies an observation across a day's two files
MATCH_SOURCES = ('time', 'latitude', 'longitude')

# config settings list_granules takes (utils/path_utils.listing_options)
LISTING_OPTIONS = (
    'version', 'version_product', 'platform', 'expected_partial_granules', 'granule_types',
    'superseded_files', 'repeated_footprints',
)

# this reader applies the config's declared_masked_values
DECLARED_MASKS = True

# the Summary product is the Standard rows with DOF strictly above this,
# compared in the files' float32 (audit 2026-10-23, R31)
SUMMARY_DOF = np.float32(1.1)
DOF_SOURCE = 'observation_ops/signal_dof'

# the declared defects this reader can confirm: row 0 of the Standard file,
# which must equal x_test bit for bit (R22); and every row of the files of
# listed days, which must all hold one declared value (R36)
MASK_FIRST_ROW = 'first_row_of_standard_file'
MASK_LISTED_DAYS = 'every_row_of_listed_days'
MASK_WHERE = (MASK_FIRST_ROW, MASK_LISTED_DAYS)

# a source missing from a declared one-sided day takes this layout, so the
# day's arrays still line up: dims after the observation dimension, and dtype
# (every one float32 in every v1 file; audit 2026-10-23)
ABSENT_LAYOUT = {
    'observation_ops/averaging_kernel': (('level', 'level_2'), (LEVELS, LEVELS), 'float32'),
    'observation_ops/xa': (('level',), (LEVELS,), 'float32'),
    'observation_ops/observation_error_h2o': (('level',), (LEVELS,), 'float32'),
    'observation_ops/signal_dof': ((), (), 'float32'),
    'geophysical/average_cloud_eod': ((), (), 'float32'),
    'geophysical/cloud_top_pressure': ((), (), 'float32'),
    'geophysical/surface_temperature': ((), (), 'float32'),
    'dd_col_p': ((), (), 'float32'),
    'dd_col_p_error': ((), (), 'float32'),
    'dd_004': ((), (), 'float32'),
    'x_h2o_col_p': ((), (), 'float32'),
    'x_h2o_col_p_error': ((), (), 'float32'),
}

# the reader's own granule index fields (utils/granules.py index_fields),
# per file in granule_file's order (user decision 2026-10-22)
INDEX_EXTRA = {
    'granule_algorithm': {
        'long_name': 'MUSES algorithm version of each source file of the granule, separated by "; "',
        'comment': 'R1pNN is MUSES v1.NN, the files\' source attribute; in granule_file order',
    },
    'granule_format': {
        'long_name': 'format version and joint processing flag of each source file, separated by "; "',
        'comment': 'F<major>p<minor>, then J0 (single) or J1 (joint retrieval) where the name has one',
    },
}
# added where a config declares repeated_footprints (R37), so the AIRS stores
# built before it keep their index
INDEX_LEFT_OUT = {
    'granule_rows_left_out': {
        'long_name': 'observations of the granule left out because another file holds the same footprint',
        'comment': (
            'Rows of the granule\'s first file (and their Summary rows) whose time, latitude and '
            'longitude another file of the product within the declared look-back also holds, and '
            'whose copy there is kept: the newest algorithm\'s, then the latest produced '
            '(repeated_footprints; docs/products/tropess.md R37). A decimal count.'
        ),
    },
}

# leap seconds after the TAI93 epoch (1993-01-01), by the UTC date each took
# effect. None has been announced since 2017-01-01; a later one would show as
# time disagreeing with datetime_utc, which every read checks
LEAP_DATES = (
    '1993-07-01', '1994-07-01', '1996-01-01', '1997-07-01', '1999-01-01',
    '2006-01-01', '2009-01-01', '2012-07-01', '2015-07-01', '2017-01-01',
)
TAI93_EPOCH = np.datetime64('1993-01-01T00:00:00', 's')
# each leap second's TAI93 instant: its UTC seconds since the epoch plus the
# leap seconds already in effect, itself included
LEAP_TAI = np.array([
    (np.datetime64(f'{day}T00:00:00', 's') - TAI93_EPOCH).astype('int64') + count
    for count, day in enumerate(LEAP_DATES, 1)
], dtype='float64')


def file_facts(path):
    """What a file's name says about it.

    Args:
        path (str): A TROPESS file.

    Returns:
        re.Match: ``platform``, ``type``, ``date``, ``algorithm``, ``stream``,
            ``format`` and ``joint`` groups.

    Raises:
        ValueError: If the name is not a TROPESS HDO file name.
    """
    match = FILE_RE.match(os.path.basename(path))
    if match is None:
        raise ValueError(f'{path} is not a TROPESS HDO file name')
    return match


def list_granules(raw_root, expected_empty=(), expected_unreadable=(), version=None,
                  version_product=None, platform=None, expected_partial_granules=None,
                  granule_types=None, superseded_files=None, repeated_footprints=None):
    """Every day of one platform, stream and collection version, in date order.

    Args:
        raw_root (str): The instrument's raw folder, e.g. ``.../raw/AIRS``.
        expected_empty (Iterable): Unused; must be empty.
        expected_unreadable (Iterable): Unused; must be empty.
        version (str): The collection version (``VersionID``).
        version_product (str): The stream, ``rs`` or ``fs``.
        platform (str): The files' ``Platform`` attribute, a key of
            ``PLATFORMS``, which picks the folders and files.
        expected_partial_granules (dict | None): Day id -> the one type it
            has (``Standard`` or ``Summary``), for days upstream has only one
            file of (R23). Any other one-sided day fails the listing.
        granule_types (list | None): The types a day is made of; ``[Summary]``
            for a product with no Standard collection (CrIS-SNPP RS). Default
            both.
        superseded_files (dict | None): Day id -> the name of a file upstream
            has replaced (R18). Only the replacement is read; any other day
            with two files of one type fails the listing.
        repeated_footprints (dict | None): The R37 rule, ``keep``,
            ``look_back``, ``expected_left_out`` and ``reason``; see
            ``select_repeats``.

    Returns:
        list: :class:`Granule` per day, paths in ``TYPES`` order, each with
            its rows left out where the config declares ``repeated_footprints``.

    Raises:
        FileNotFoundError: If the root does not exist.
        ValueError: If the options are missing, a day has two files of one
            type that are not a declared replacement, one-sided days differ
            from the declared ones, or the repeat rule leaves out other than
            the declared count.
    """
    if not os.path.isdir(raw_root):
        raise FileNotFoundError(f'no raw data directory at {raw_root}')
    if list(expected_empty) or list(expected_unreadable):
        raise ValueError('TROPESS has no empty or unreadable granules; leave both unset')
    if version is None or version_product is None:
        raise ValueError('a TROPESS config sets version (the collection) and version_product (the stream)')
    stream = str(version_product).upper()
    if stream not in ('RS', 'FS'):
        raise ValueError(f'version_product must be rs or fs; it is {version_product!r}')
    if platform not in PLATFORMS:
        raise ValueError(f'the config declares platform {platform!r}; this reader lists only {sorted(PLATFORMS)}')
    instruments, token = PLATFORMS[platform]
    types = tuple(granule_types or TYPES)
    if not types or set(types) - set(TYPES):
        raise ValueError(f'granule_types must be drawn from {TYPES}; it is {granule_types!r}')

    found_files = {}
    for folder in sorted(os.listdir(raw_root)):
        match = FOLDER_RE.match(folder)
        if match is None or match['kind'] not in KINDS:
            continue
        if (match['stream'] != stream or match['collection'] != str(version)
                or match['instrument'] not in instruments):
            continue
        kind = KINDS[match['kind']]
        if kind not in types:
            raise ValueError(f'{folder} is a {kind} collection, but granule_types is {list(types)}')
        base = os.path.join(raw_root, folder)
        # a later download keeps a folder per year; the first ones are flat
        places = [os.path.join(base, entry) for entry in sorted(os.listdir(base))
                  if entry.isdigit() and os.path.isdir(os.path.join(base, entry))] or [base]
        for place in places:
            for name in sorted(os.listdir(place)):
                found = FILE_RE.match(name)
                # skips L3 files and the local *_target.nc copies (R5, R6)
                if found is None:
                    continue
                if found['type'] != kind or found['stream'] != stream or found['platform'] != token:
                    raise ValueError(f'{place} holds {name}, which is not {token} {kind} {stream}')
                found_files.setdefault(found['date'], {}).setdefault(kind, []).append(os.path.join(place, name))

    if not found_files:
        raise ValueError(
            f'no {token} {stream} collection folder under {raw_root} has version {version!r}: '
            f'the configured processor version matches no files'
        )
    days = resolve_superseded(found_files, superseded_files)
    if types == TYPES:
        check_partial(days, expected_partial_granules)
    elif expected_partial_granules:
        raise ValueError('expected_partial_granules applies only to a product of both types')
    granules = [
        Granule(
            id=day,
            day=datetime.datetime.strptime(day, '%Y%m%d').date(),
            paths=tuple(files[kind] for kind in TYPES if kind in files),
        )
        for day, files in sorted(days.items())
    ]
    if repeated_footprints:
        left_out = select_repeats(granules, repeated_footprints)
        granules = [granule._replace(left_out=left_out[granule.id]) for granule in granules]
    return granules


def resolve_superseded(found, superseded):
    """One file per day and type, the declared replaced files set aside (R18).

    Args:
        found (dict): Day id -> type -> the paths listed.
        superseded (dict | None): Day id -> the name of the replaced file.

    Returns:
        dict: Day id -> type -> path.

    Raises:
        ValueError: If a day has two files of one type and neither is
            declared replaced; a replacement is not newer in algorithm and
            ``ProductionDateTime``; or a declaration names no listed file.
    """
    superseded = {str(day): str(name) for day, name in (superseded or {}).items()}
    used, days = set(), {}
    for day, kinds in found.items():
        for kind, paths in kinds.items():
            if len(paths) == 1:
                days.setdefault(day, {})[kind] = paths[0]
                continue
            old = [path for path in paths if os.path.basename(path) == superseded.get(day)]
            if len(paths) != 2 or not old:
                raise ValueError(f'{len(paths)} {kind} files for {day}: {[os.path.basename(p) for p in paths]}')
            new = next(path for path in paths if path != old[0])
            if file_rank(new) <= file_rank(old[0]):
                raise ValueError(
                    f'{day}: {os.path.basename(new)} {file_rank(new)} is not newer than the '
                    f'superseded {os.path.basename(old[0])} {file_rank(old[0])}'
                )
            if file_facts(new)['algorithm'] == file_facts(old[0])['algorithm']:
                raise ValueError(f'{day}: the replacement has the superseded file\'s algorithm')
            used.add(day)
            days.setdefault(day, {})[kind] = new
    stale = sorted(set(superseded) - used)
    if stale:
        raise ValueError(f'superseded_files names days with no second file: {stale}')
    return days


def check_partial(days, expected_partial_granules):
    """Fail unless the one-sided days are exactly the declared ones (R23).

    Args:
        days (dict): Day id -> type -> path.
        expected_partial_granules (dict | None): Day id -> its one type.

    Raises:
        ValueError: On a one-sided day not declared, a declared one with both
            files, or a declared one with none.
    """
    partial = {str(day): str(kind) for day, kind in (expected_partial_granules or {}).items()}
    problems = []
    for day, files in sorted(days.items()):
        if len(files) == 2:
            if day in partial:
                problems.append(f'{day} is declared {partial[day]} only but has both files')
        elif partial.get(day) != next(iter(files)):
            problems.append(f'{day} has only a {next(iter(files))} file, and is not declared so')
    stale = sorted(set(partial) - set(days))
    if stale:
        problems.append(f'days declared partial have no file: {stale}')
    if problems:
        raise ValueError(f'{len(problems)} problems with one-sided days (expected_partial_granules): {problems[:10]}')


def file_rank(path):
    """How a file ranks against another copy of its footprints: newer is larger.

    The algorithm version first, then the root ``ProductionDateTime``, an ISO
    UTC timestamp that sorts as text (R37, user decision 2026-10-26).

    Args:
        path (str): A TROPESS file.

    Returns:
        tuple: ``(algorithm number, ProductionDateTime)``.
    """
    with h5py.File(path, 'r') as handle:
        made = str(decode_text(handle.attrs[PRODUCTION_ATTR]))
    return int(file_facts(path)['algorithm'][3:]), made


def footprint_keys(path):
    """Each row's time, latitude and longitude as one key, bit for bit.

    Args:
        path (str): A TROPESS file.

    Returns:
        list: One ``(int, int, int)`` per row, or None where any of the three
            is fill or NaN (not an observation; ``RowRule`` leaves it out).
    """
    with h5py.File(path, 'r') as handle:
        columns = [np.asarray(handle[source][...]) for source in MATCH_SOURCES]
    missing = np.zeros(columns[0].shape[0], dtype=bool)
    for column in columns:
        missing |= (column == LOCATION_FILL) | np.isnan(column)
    views = [column.view(f'u{column.dtype.itemsize}') for column in columns]
    keys = list(zip(*(view.tolist() for view in views)))
    return [None if gone else key for key, gone in zip(keys, missing.tolist())]


def select_repeats(granules, rule):
    """The rows each granule leaves out under the declared R37 rule.

    A footprint (time, latitude and longitude, bit for bit) held by the first
    file of more than one granule within ``look_back`` granules is kept once:
    in the file with the newest algorithm, then the latest
    ``ProductionDateTime`` (``file_rank``). Within one file a footprint may not
    repeat, and two copies may not rank equal.

    Args:
        granules (list): The listing, in order.
        rule (dict): ``keep`` (``REPEAT_KEEP``), ``look_back`` (granules),
            ``expected_left_out`` (the total, from a measured pass) and
            ``reason``.

    Returns:
        dict: Granule id -> tuple of rows of its first file left out.

    Raises:
        ValueError: If the rule is malformed, a file repeats a footprint, two
            copies rank equal, or the total differs from ``expected_left_out``.
    """
    if rule.get('keep') != REPEAT_KEEP or not str(rule.get('reason', '')).strip():
        raise ValueError(f'repeated_footprints needs keep: {REPEAT_KEEP} and a reason; it is {rule}')
    look_back = int(rule.get('look_back', 0))
    if look_back < 1:
        raise ValueError(f'repeated_footprints look_back must be 1 or more; it is {look_back}')
    left_out = {granule.id: set() for granule in granules}
    ranks = {}
    # the kept copy of each footprint held in the last look_back granules
    kept = {}
    held = collections.deque()
    for position, granule in enumerate(granules):
        while held and held[0][0] < position - look_back:
            gone, keys = held.popleft()
            for key in keys:
                if kept.get(key, (None,))[0] == gone:
                    del kept[key]
        path = granule.paths[0]
        ranks[position] = file_rank(path)
        seen = set()
        for row, key in enumerate(footprint_keys(path)):
            if key is None:
                continue
            if key in seen:
                raise ValueError(f'{os.path.basename(path)} repeats a footprint within itself (row {row})')
            seen.add(key)
            if key not in kept:
                kept[key] = (position, row)
                continue
            other, other_row = kept[key]
            if ranks[position] == ranks[other]:
                raise ValueError(
                    f'{granule.id} row {row} and {granules[other].id} row {other_row} hold one '
                    f'footprint, and their files rank equal {ranks[position]}'
                )
            if ranks[position] > ranks[other]:
                left_out[granules[other].id].add(other_row)
                kept[key] = (position, row)
            else:
                left_out[granule.id].add(row)
        held.append((position, seen))
    total = sum(len(rows) for rows in left_out.values())
    expected = rule.get('expected_left_out')
    if expected is None or int(expected) != total:
        raise ValueError(
            f'repeated_footprints leaves out {total} observations in '
            f'{sum(bool(rows) for rows in left_out.values())} granules, but the config declares '
            f'expected_left_out: {expected}'
        )
    return {gid: tuple(sorted(rows)) for gid, rows in left_out.items()}


def decode_time(raw):
    """Decode TAI93 float64 seconds to UTC datetime64[s].

    Args:
        raw (numpy.ndarray): float64 TAI seconds since 1993-01-01.

    Returns:
        numpy.ndarray: datetime64[s], UTC.

    Raises:
        ValueError: If a time is not a whole second, which seconds could not
            hold exactly.
    """
    raw = np.asarray(raw, dtype='float64')
    if (raw != np.round(raw)).any():
        raise ValueError(f'{int((raw != np.round(raw)).sum())} times are not whole seconds')
    leaps = np.searchsorted(LEAP_TAI, raw, side='right')
    return TAI93_EPOCH + (raw - leaps).astype('int64').astype('timedelta64[s]')


def utc_from_fields(fields):
    """``datetime_utc`` rows (year, month, day, hour, minute, second) as datetime64[s].

    Args:
        fields (numpy.ndarray): int rows of six.

    Returns:
        numpy.ndarray: datetime64[s].
    """
    fields = np.asarray(fields, dtype='int64')
    days = np.array(
        [f'{y:04d}-{m:02d}-{d:02d}' for y, m, d in fields[:, :3].tolist()], dtype='datetime64[D]'
    ).astype('datetime64[s]')
    return days + (fields[:, 3] * 3600 + fields[:, 4] * 60 + fields[:, 5]).astype('timedelta64[s]')


def time_problems(time_raw, utc_fields):
    """Whether TAI93 time, decoded, is ``datetime_utc`` on every row.

    Args:
        time_raw (numpy.ndarray): The file's ``time``.
        utc_fields (numpy.ndarray): Its ``datetime_utc``.

    Returns:
        list: Problems, empty if every row agrees.
    """
    try:
        decoded = decode_time(time_raw)
    except ValueError as error:
        return [str(error)]
    differ = int((decoded != utc_from_fields(utc_fields)).sum())
    return [f'time less the leap seconds differs from datetime_utc on {differ} rows'] if differ else []


def header_problems(attrs, path):
    """What a file's global attributes must say, given its name.

    Args:
        attrs (dict): Its global attributes, decoded.
        path (str): Its path.

    Returns:
        list: Problems, empty if the attributes agree with the name.
    """
    facts = file_facts(path)
    short = f'TRPS{"D" if facts["type"] == "Standard" else "Y"}L2HDO'
    problems = []
    name = str(attrs.get(SHORT_NAME_ATTR, ''))
    if not (name.startswith(short) and name.endswith(facts['stream'])):
        problems.append(f'ShortName {name!r} is not a {facts["type"]} {facts["stream"]} collection')
    source = str(attrs.get('source', ''))
    if source != f'MUSES v1.{facts["algorithm"][3:]}':
        problems.append(f'source {source!r} does not match the name\'s {facts["algorithm"]}')
    return problems


def read_attrs(item):
    """An item's attributes, byte strings decoded.

    Args:
        item: A netCDF4 Dataset or Variable.

    Returns:
        dict: Attribute name -> value.
    """
    return {name: decode_text(item.getncattr(name)) for name in item.ncattrs()}


def file_version(value):
    """The collection version a file declares, as text.

    ``VersionID`` is an integer attribute, which netCDF4 and h5py both read
    as a one-element array.

    Args:
        value: The raw ``VersionID`` attribute.

    Returns:
        str: e.g. '1'.
    """
    value = decode_text(value)
    if isinstance(value, np.ndarray) and value.size == 1:
        value = value.reshape(-1)[0]
    return str(value.item() if isinstance(value, np.generic) else value)


def holds(handle, source):
    """Whether an open netCDF4 file has a source, by its path.

    Args:
        handle (netCDF4.Dataset): The file.
        source (str): ``<group>/<variable>``, or a root variable's name.

    Returns:
        bool: True if the variable exists.
    """
    group, _, name = source.rpartition('/')
    if group and group not in handle.groups:
        return False
    return name in (handle[group] if group else handle).variables


def match_rows(standard, summary):
    """Where each Summary row is among the Standard rows.

    Args:
        standard (dict): Standard ``time``, ``latitude``, ``longitude``.
        summary (dict): Summary's, the same sources.

    Returns:
        numpy.ndarray: Per Summary row, its Standard row, or -1.
    """
    def keys(columns):
        record = np.empty(columns['time'].shape[0], dtype=[('t', 'f8'), ('a', 'u4'), ('o', 'u4')])
        record['t'] = columns['time']
        # bit patterns, so a row matches only the identical position
        record['a'] = np.ascontiguousarray(columns['latitude']).view('u4')
        record['o'] = np.ascontiguousarray(columns['longitude']).view('u4')
        return record

    ours, theirs = keys(standard), keys(summary)
    order = np.argsort(ours, kind='stable')
    at = np.clip(np.searchsorted(ours[order], theirs), 0, max(len(order) - 1, 0))
    if not len(order):
        return np.full(len(theirs), -1)
    found = ours[order][at] == theirs
    if np.unique(ours).size != ours.size:
        raise ValueError('the Standard file repeats a row')
    return np.where(found, order[at], -1)


def merge_problems(rows, dof, shared, skip=None):
    """The merge rules, given where Summary's rows are among Standard's.

    Args:
        rows (numpy.ndarray): From ``match_rows``.
        dof (numpy.ndarray): Standard's ``signal_dof``, float32.
        shared (dict): Source -> ``(standard values, summary values)`` for
            every source both files hold.
        skip (dict | None): Source -> Standard row whose value is a declared
            defect, not compared.

    Returns:
        list: Problems, empty if Summary is exactly the Standard rows with
            DOF > 1.1, in order, with identical values.
    """
    problems = []
    if (rows < 0).any():
        problems.append(f'{int((rows < 0).sum())} Summary rows match no Standard row')
        return problems
    if (np.diff(rows) <= 0).any():
        problems.append('Summary rows are not in the Standard order')
    member = np.zeros(dof.size, dtype=bool)
    member[rows] = True
    rule = dof > SUMMARY_DOF
    if (member != rule).any():
        problems.append(
            f'Summary is not the Standard rows with DOF > {SUMMARY_DOF}: '
            f'{int((member != rule).sum())} rows differ'
        )
    for source, (ours, theirs) in shared.items():
        ours = ours[rows]
        if skip and source in skip:
            keep = rows != skip[source]
            ours, theirs = ours[keep], theirs[keep]
        if ours.dtype.kind in 'iu' and theirs.dtype.kind in 'iu':
            # integers can differ in width between the two files (R16)
            same = np.array_equal(ours, theirs)
        else:
            same = same_bits(np.ascontiguousarray(ours), np.ascontiguousarray(theirs))
        if not same:
            problems.append(f'{source} differs between Standard and Summary on matched rows')
    return problems


def read_granule(granule, sources, time_source, rule):
    """Read one day's Standard and Summary files onto one obs axis, raw.

    Args:
        granule (Granule): The day, from ``list_granules``.
        sources (Sequence): Source paths to read.
        time_source (str): The time variable, returned decoded.
        rule (RowRule): Which rows are observations, and the declared masks.

    Returns:
        GranuleData: The day's arrays on the Standard rows (the Summary rows
            on a Summary-only day). A source is marked absent where its file
            lacks the observation, or the day lacks its file.

    Raises:
        KeyError: If a source is in neither file and has no absent layout.
        ValueError: If the files disagree on their version or platform, their
            headers disagree with their names, time disagrees with
            datetime_utc, a row left out holds data, the merge rules fail, or
            a declared defect is not what its declaration says.
    """
    handles = {file_facts(path)['type']: netCDF4.Dataset(path, 'r') for path in granule.paths}
    try:
        for handle in handles.values():
            # masking off: only the config's declared fill counts as missing
            handle.set_auto_mask(False)
        attrs = {kind: read_attrs(handle) for kind, handle in handles.items()}
        problems = []
        for kind, handle in handles.items():
            problems += [f'{kind}: {p}' for p in header_problems(attrs[kind], handle.filepath())]
            problems += [f'{kind}: {p}' for p in time_problems(
                np.asarray(handle['time'][...]), np.asarray(handle['datetime_utc'][...])
            )]
        versions = {file_version(item.get(VERSION_ATTR, '')) for item in attrs.values()}
        platforms = {str(item.get(PLATFORM_ATTR, '')) for item in attrs.values()}
        if len(versions) != 1 or len(platforms) != 1:
            problems.append(f'the files declare versions {sorted(versions)} and platforms {sorted(platforms)}')

        raw = {kind: {} for kind in handles}
        keeps = {}
        for kind, handle in handles.items():
            location = {source: np.asarray(handle[source][...]) for source in rule.location}
            raw[kind].update(location)
            keeps[kind] = observed_rows(location, rule)
            for source in sources:
                if holds(handle, source):
                    raw[kind].setdefault(source, np.asarray(handle[source][...]))
            for source, values in raw[kind].items():
                leaked = leaked_rows(source, values, keeps[kind], rule)
                if leaked:
                    problems.append(f'{kind}: {source} holds data on {leaked} rows with no time, latitude or longitude')
        if problems:
            raise ValueError(f'day {granule.id}: {"; ".join(problems)}')

        axis = 'Standard' if 'Standard' in handles else 'Summary'
        kept = {kind: {source: values[keeps[kind]] for source, values in raw[kind].items()} for kind in handles}
        n_obs = int(keeps[axis].sum())

        # the declared defects, each confirmed in raw before it is marked
        masked = {}
        for entry in rule.masked:
            if entry.get('where') not in MASK_WHERE:
                raise ValueError(f'declared_masked_values: this reader confirms only where: {MASK_WHERE}')
            source = entry['source']
            if source not in sources:
                continue
            if entry['where'] == MASK_FIRST_ROW:
                # R22: row 0 of the Standard file is x_test
                if 'Standard' not in handles:
                    continue
                equals = entry.get('equals')
                first = np.asarray(handles['Standard'][source][0])
                expected = np.asarray(handles['Standard'][equals][...])
                if not same_bits(first, expected):
                    raise ValueError(f'day {granule.id}: the first {source} is not {equals}, as declared')
                if keeps['Standard'][0]:
                    mask = np.zeros(n_obs, dtype=bool)
                    mask[0] = True
                    masked[source] = mask
            elif granule.id in listed_days(entry):
                # R36: the whole file, every row the declared value
                holder = next(kind for kind in TYPES if kind in handles and source in raw[kind])
                if not (raw[holder][source] == entry['value']).all():
                    raise ValueError(
                        f'day {granule.id}: {source} is not {entry["value"]} on every row, as declared'
                    )
                masked[source] = np.ones(n_obs, dtype=bool)

        rows = None
        if len(handles) == 2:
            rows = match_rows(kept['Standard'], kept['Summary'])
            dof = np.asarray(handles['Standard'][DOF_SOURCE][...])[keeps['Standard']]
            shared = {
                source: (kept['Standard'][source], kept['Summary'][source])
                for source in kept['Summary'] if source in kept['Standard']
            }
            # R22's row is not compared; R36 holds the same values in both
            skip = {source: 0 for source, mask in masked.items() if not mask.all()}
            failures = merge_problems(rows, dof, shared, skip)
            if failures:
                raise ValueError(f'day {granule.id}: {"; ".join(failures)}')

        # R37: the rows the listing leaves out, and the Summary rows that
        # match them; checked against the merge above, so dropped after it
        if granule.left_out:
            drop = np.zeros(keeps[axis].size, dtype=bool)
            drop[list(granule.left_out)] = True
            if (drop & ~keeps[axis]).any():
                raise ValueError(f'day {granule.id}: a row the listing leaves out is not an observation')
            stay = ~drop[keeps[axis]]
            kept[axis] = {source: values[stay] for source, values in kept[axis].items()}
            masked = {source: mask[stay] for source, mask in masked.items()}
            if rows is not None:
                other = 'Summary' if axis == 'Standard' else 'Standard'
                summary_stay = stay[rows]
                kept[other] = {source: values[summary_stay] for source, values in kept[other].items()}
                rows = (np.cumsum(stay) - 1)[rows[summary_stay]]
            n_obs = int(stay.sum())

        arrays = {}
        for source in sources:
            holder = next((kind for kind in TYPES if kind in handles and source in kept[kind]), None)
            if holder is None:
                if source not in ABSENT_LAYOUT:
                    raise KeyError(f'no file of day {granule.id} holds {source}')
                dims, shape, dtype = ABSENT_LAYOUT[source]
                arrays[source] = SourceArray(
                    dims=('obs',) + dims, values=np.zeros((n_obs,) + shape, dtype=dtype), attrs={},
                    dimension_note=f'none; this day has no {"Summary" if axis == "Standard" else "Standard"} file',
                    absent=np.ones(n_obs, dtype=bool),
                )
                continue
            variable = handles[holder][source]
            dims, values, note = squeeze_dims(
                kept[holder][source], variable.dimensions, OBSERVATION_DIM, DIMENSION_RENAMES
            )
            if dims.count('level') == 2:
                # a matrix over levels: rows retrieved, columns true (N6)
                dims = ('obs', 'level', 'level_2')
                note = f'{note}; the second level -> level_2' if note != 'none' else 'the second level -> level_2'
            if source == time_source:
                values = decode_time(values)
                note = f'{note}; TAI93 seconds less the leap seconds, decoded to UTC'
            source_attrs = read_attrs(variable)
            absent = None
            if holder != axis:
                # a Summary field on the Standard rows
                placed = np.zeros((n_obs,) + values.shape[1:], dtype=values.dtype)
                placed[rows] = values
                absent = np.ones(n_obs, dtype=bool)
                absent[rows] = False
                values = placed
            if len(handles) == 2:
                note = (f'{note}; the day\'s Standard and Summary files merged onto the Standard '
                        f'rows (this variable from the {holder} file)')
            arrays[source] = SourceArray(
                dims=dims, values=values, attrs=source_attrs, dimension_note=note,
                absent=absent if absent is not None and absent.any() else None,
                masked=masked.get(source),
            )
        return GranuleData(
            granule=granule,
            n_obs=n_obs,
            version=versions.pop(),
            attrs=attrs[axis],
            arrays=arrays,
            n_source_rows=sum(handle.dimensions[OBSERVATION_DIM].size for handle in handles.values()),
            platform=platforms.pop(),
            index_extra=index_extra(granule.paths, granule.left_out),
        )
    finally:
        for handle in handles.values():
            handle.close()


def listed_days(entry):
    """The days a whole-file declared mask names (R36).

    Args:
        entry (dict): A ``declared_masked_values`` entry with ``days``: day
            ids, or ``[first, last]`` ranges, inclusive.

    Returns:
        set: Day ids, ``YYYYMMDD``.
    """
    days = set()
    for item in entry.get('days') or []:
        if isinstance(item, (list, tuple)):
            first, last = (datetime.datetime.strptime(str(day), '%Y%m%d').date() for day in item)
            days.update(
                (first + datetime.timedelta(days=step)).strftime('%Y%m%d')
                for step in range((last - first).days + 1)
            )
        else:
            days.add(str(item))
    return days


def index_extra_fields(settings):
    """The reader's own granule index fields under a config.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        dict: ``INDEX_EXTRA``, and ``INDEX_LEFT_OUT`` where the config
            declares ``repeated_footprints``.
    """
    return INDEX_EXTRA | (INDEX_LEFT_OUT if settings.get('repeated_footprints') else {})


def index_extra(paths, left_out=None):
    """The reader's granule index fields for one granule.

    Args:
        paths (tuple): The granule's files, in ``TYPES`` order.
        left_out (tuple | None): Its rows left out under ``repeated_footprints``;
            None where the config declares no such rule.

    Returns:
        dict: ``granule_algorithm`` and ``granule_format``, from the file
            names, and ``granule_rows_left_out`` where there is a rule.
    """
    facts = [file_facts(path) for path in paths]
    fields = {
        'granule_algorithm': '; '.join(fact['algorithm'] for fact in facts),
        'granule_format': '; '.join(
            fact['format'] + (f'_{fact["joint"]}' if fact['joint'] else '') for fact in facts
        ),
    }
    if left_out is not None:
        fields['granule_rows_left_out'] = str(len(left_out))
    return fields


def check_granule(handle):
    """Format invariants the verifier confirms on every file.

    Args:
        handle (h5py.File): An open file.

    Returns:
        list: Problems: a header that disagrees with the file name, time
            that is not ``datetime_utc`` less the leap seconds, or a level
            count other than 17.
    """
    attrs = {key: decode_text(value) for key, value in handle.attrs.items()}
    attrs = {key: value[0] if isinstance(value, np.ndarray) and value.size == 1 else value
             for key, value in attrs.items()}
    problems = header_problems(attrs, handle.filename)
    problems += time_problems(handle['time'][...], handle['datetime_utc'][...])
    if handle['pressure'].shape[1:] != (LEVELS,):
        problems.append(f'pressure has {handle["pressure"].shape[1:]} levels, not {LEVELS}')
    return problems


def check_files(paths):
    """The merge rules, from raw, for the verifier.

    Args:
        paths (tuple): The granule's files.

    Returns:
        list: Problems, empty if Summary is exactly the Standard rows with
            DOF > 1.1, in order, with identical shared values; the verifier
            compares each file's values with the store itself, so this
            checks only the row selection.
    """
    if len(paths) != 2:
        return []
    with h5py.File(paths[0], 'r') as standard, h5py.File(paths[1], 'r') as summary:
        rows = match_rows(
            {source: standard[source][...] for source in MATCH_SOURCES},
            {source: summary[source][...] for source in MATCH_SOURCES},
        )
        return merge_problems(rows, standard[DOF_SOURCE][...], {})


def declared_masks(handle, path, masks, kept):
    """Find and confirm the config's declared defects in one file, for the verifier.

    A whole-file mask (R36) is also checked the other way: a Standard file of
    a day not declared must not hold the declared value on every row, so a
    defective file the config misses fails (user decision 2026-10-26, Q1).

    Args:
        handle (h5py.File): The open file.
        path (str): Its path.
        masks (tuple): The config's ``declared_masked_values``.
        kept (numpy.ndarray): bool per row, the rows stored.

    Returns:
        tuple: Source -> bool over the stored rows, True where the value is a
            confirmed defect; and the problems found.
    """
    found, problems = {}, []
    facts = file_facts(path)
    name = os.path.basename(path)
    for entry in masks:
        where, source = entry.get('where'), entry['source']
        if where == MASK_FIRST_ROW:
            if facts['type'] != 'Standard':
                continue
            equals = entry.get('equals')
            if not np.array_equal(handle[source][0].view(np.uint8), handle[equals][...].view(np.uint8)):
                problems.append(f'{name}: the first {source} is not {equals}, as declared')
                continue
            row = np.zeros(kept.size, dtype=bool)
            row[0] = True
            found[source] = row[kept]
        elif where == MASK_LISTED_DAYS:
            if source not in handle:
                continue
            every = bool((handle[source][...] == entry['value']).all())
            if facts['date'] in listed_days(entry):
                if not every:
                    problems.append(f'{name}: {source} is not {entry["value"]} on every row, as declared')
                    continue
                found[source] = np.ones(int(kept.sum()), dtype=bool)
            elif every and facts['type'] == 'Standard':
                problems.append(
                    f'{name}: {source} is {entry["value"]} on every row, but its day is not declared'
                )
        else:
            problems.append(f'declared mask where {where!r} is not one of {MASK_WHERE}')
    return found, problems
