"""Reader for the NASA TROPESS (MUSES) HDO Level 2 products, AIRS first.

The raw tree holds one folder per collection, as downloaded: the first
downloads flat (``<ShortName>_<version>-<stamp>/``), the later ones by year
(``<ShortName>.<version>/<YYYY>/``). One stream, product type and collection
version can span both (``docs/products/tropess.md``, Collections):

```
<raw>/TRPSDL2HDOAIRSORS.1/<YYYY>/TROPESS_AIRS-Aqua_L2_Standard_HDO_<YYYYMMDD>_MUSES_R1p6_RS_F0p8_J0.nc
<raw>/TRPSYL2HDOAIRSORS_1-20240806_185241/TROPESS_AIRS-Aqua_L2_Summary_HDO_<YYYYMMDD>_MUSES_R1p6_RS_F0p8_J0.nc
```

**One product per stream and collection version** (user decisions
2026-10-22 and 10-23): the config's ``version`` is the collection version
the files declare (``VersionID``) and ``version_product`` the stream, so the
stores are ``wisosat.airs.v_1.rs...`` and ``wisosat.airs.v_1.fs...``. The
listing takes only that stream's and version's folders (``LISTING_OPTIONS``).

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
  config declares it (``expected_partial_granules``; R23).

**The first ``x`` of every Standard file is a defect** (R22): it is
``x_test``, the kernel applied to the true profile. The config declares it
(``declared_masked_values``), and the read confirms it equals ``x_test``
before marking it; shared code stores NaN.

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

OBSERVATION_DIM = 'target'
DIMENSION_RENAMES = {}
VERTICAL_ORDER = 'surface_first'
LEVELS = 17

VERSION_ATTR = 'VersionID'
PLATFORM_ATTR = 'Platform'
SHORT_NAME_ATTR = 'ShortName'

# what identifies an observation across a day's two files
MATCH_SOURCES = ('time', 'latitude', 'longitude')

# config settings list_granules takes (utils/path_utils.listing_options)
LISTING_OPTIONS = ('version', 'version_product', 'expected_partial_granules')

# this reader applies the config's declared_masked_values
DECLARED_MASKS = True

# the Summary product is the Standard rows with DOF strictly above this,
# compared in the files' float32 (audit 2026-10-23, R31)
SUMMARY_DOF = np.float32(1.1)
DOF_SOURCE = 'observation_ops/signal_dof'

# the one declared defect this reader can confirm (R22): row 0 of the Standard
# file, which must equal x_test bit for bit
MASK_WHERE = 'first_row_of_standard_file'

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
                  version_product=None, expected_partial_granules=None):
    """Every day of one stream and collection version, in date order.

    Args:
        raw_root (str): The instrument's raw folder, e.g. ``.../raw/AIRS``.
        expected_empty (Iterable): Unused; must be empty.
        expected_unreadable (Iterable): Unused; must be empty.
        version (str): The collection version (``VersionID``).
        version_product (str): The stream, ``rs`` or ``fs``.
        expected_partial_granules (dict | None): Day id -> the one type it
            has (``Standard`` or ``Summary``), for days upstream has only one
            file of (R23). Any other one-sided day fails the listing.

    Returns:
        list: :class:`Granule` per day, paths in ``TYPES`` order.

    Raises:
        FileNotFoundError: If the root does not exist.
        ValueError: If the options are missing, a day has two files of one
            type, or one-sided days differ from the declared ones.
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

    days = {}
    for folder in sorted(os.listdir(raw_root)):
        match = FOLDER_RE.match(folder)
        if match is None or match['kind'] not in KINDS:
            continue
        if match['stream'] != stream or match['collection'] != str(version):
            continue
        kind = KINDS[match['kind']]
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
                if found['type'] != kind or found['stream'] != stream:
                    raise ValueError(f'{place} holds {name}, which is not {kind} {stream}')
                files = days.setdefault(found['date'], {})
                if kind in files:
                    raise ValueError(f'two {kind} files for {found["date"]}: {files[kind]} and {name}')
                files[kind] = os.path.join(place, name)

    if not days:
        raise ValueError(
            f'no {stream} collection folder under {raw_root} has version {version!r}: the '
            f'configured processor version matches no files'
        )
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
    return [
        Granule(
            id=day,
            day=datetime.datetime.strptime(day, '%Y%m%d').date(),
            paths=tuple(files[kind] for kind in TYPES if kind in files),
        )
        for day, files in sorted(days.items())
    ]


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

        # the declared defects: row 0 of the Standard file, confirmed first
        masked = {}
        for entry in rule.masked:
            if entry.get('where') != MASK_WHERE:
                raise ValueError(f'declared_masked_values: this reader confirms only where: {MASK_WHERE}')
            source, equals = entry['source'], entry.get('equals')
            if 'Standard' not in handles or source not in sources:
                continue
            first = np.asarray(handles['Standard'][source][0])
            expected = np.asarray(handles['Standard'][equals][...])
            if not same_bits(first, expected):
                raise ValueError(f'day {granule.id}: the first {source} is not {equals}, as declared')
            if keeps['Standard'][0]:
                mask = np.zeros(n_obs, dtype=bool)
                mask[0] = True
                masked[source] = mask

        rows = None
        if len(handles) == 2:
            rows = match_rows(kept['Standard'], kept['Summary'])
            dof = np.asarray(handles['Standard'][DOF_SOURCE][...])[keeps['Standard']]
            shared = {
                source: (kept['Standard'][source], kept['Summary'][source])
                for source in kept['Summary'] if source in kept['Standard']
            }
            skip = {source: 0 for source in masked}
            failures = merge_problems(rows, dof, shared, skip)
            if failures:
                raise ValueError(f'day {granule.id}: {"; ".join(failures)}')

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
            index_extra=index_extra(granule.paths),
        )
    finally:
        for handle in handles.values():
            handle.close()


def index_extra(paths):
    """The reader's granule index fields for one granule, from its file names.

    Args:
        paths (tuple): The granule's files, in ``TYPES`` order.

    Returns:
        dict: ``granule_algorithm`` and ``granule_format``.
    """
    facts = [file_facts(path) for path in paths]
    return {
        'granule_algorithm': '; '.join(fact['algorithm'] for fact in facts),
        'granule_format': '; '.join(
            fact['format'] + (f'_{fact["joint"]}' if fact['joint'] else '') for fact in facts
        ),
    }


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
    if file_facts(path)['type'] != 'Standard':
        return found, problems
    for entry in masks:
        if entry.get('where') != MASK_WHERE:
            problems.append(f'declared mask where {entry.get("where")!r} is not {MASK_WHERE!r}')
            continue
        source, equals = entry['source'], entry.get('equals')
        if not np.array_equal(handle[source][0].view(np.uint8), handle[equals][...].view(np.uint8)):
            problems.append(f'{os.path.basename(path)}: the first {source} is not {equals}, as declared')
            continue
        row = np.zeros(kept.size, dtype=bool)
        row[0] = True
        found[source] = row[kept]
    return found, problems
