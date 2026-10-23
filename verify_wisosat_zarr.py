"""Verify the stores of one WISO-SAT Level 2 product against the raw files.

Reads the same config the build did, so it checks the stores that config names
and needs no paths of its own. Nothing here writes: every session is read
only.

**Every observation is checked, not a sample** (project rule, 2026-10-14). The
values phase covers every granule and compares every value of every store with
what the raw file says it should be. It runs as scans of one group of stores
over one range of granules (``verify_granules_per_task``), in
``verify_num_workers`` processes; each scan reads raw and stored values itself
and returns only counts, so one store's record can be spread over many cores
(TESTING.md finding 12). ``--stores`` compares only the stores it names: the
geolocation store is opened for the index and placement, and its own values
are compared only when it is named.

**The raw side is read independently of the build.** The build reads with
netCDF4 through the product's reader; this reads with h5py, straight from the
source paths in the nomenclature key, with no masking and no CF decoding, and
applies the declared fill and the key's conversion itself. Only three
format facts are shared with the build, through the reader: how the product
encodes time (``decode_time``), its swath layout (``check_granule``), and the
vertical order its profiles are stored in (``VERTICAL_ORDER``).
Comparisons are bit-exact, reading the stored values undecoded through zarr:
the build does the same arithmetic in the same order, so anything short of
identical is a defect.

Four phases, all run by default, selectable with ``--phases``:

``structure``
    Per store, from metadata alone: the variables, dimensions, chunks, dtypes,
    fill values, time encoding, the global and variable attributes the style
    guide and the key require, and the store's name.
``index``
    That every store carries an identical granule index and obs length, that
    the index matches the raw listing, and that the listing passes the build's
    own coverage check.
``values``
    The pass over every granule: every value of every store against raw; each
    granule's index entry (observation count, earliest and latest time, and
    any fields of the reader's own) against the file; time never decreasing,
    unless the config keeps an unordered source's order (``time_order:
    source``); the processor version, and the platform where the reader reads
    one; the product's swath layout, and the reader's checks across a
    granule's files; values the config declares defects
    (``declared_masked_values``) confirmed in raw and stored as NaN; every
    declared fill value occurring somewhere in the record; and no netCDF
    default fill surviving in a source that does not declare it.
``repository``
    Every commit in each store's history is one the pipeline makes.

The last lines of the log are what ``finalize_wisosat_zarr.py`` reads as
evidence: the phases, the stores, the geospatial bounds seen, and the verdict.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import logging
import multiprocessing
import os
import sys

import h5py
import netCDF4
import numpy as np
import zarr

from utils.granules import (
    FILE_SEPARATOR,
    GRANULE_DIM,
    LOCATION_COORDINATES,
    check_coverage,
    check_order,
    declared_mask,
    declared_rows,
    decode_text,
    index_fields,
)
from utils.log_utils import log_peak_memory, setup_logging
from utils.nomenclature import (
    canonical_frequency,
    conversion_factor,
    coordinate_factor,
    coordinates,
    variable as key_variable,
)
from utils.path_utils import (
    GEOLOCATION,
    listing_options,
    load_config,
    load_reader,
    log_path,
    run_stores,
    source_product,
    store_path,
    version_token,
)
from utils.zarr_utils import (
    BRANCH,
    COMMIT_PREFIX,
    TIME_CALENDAR,
    TIME_EPOCH,
    TIME_FILL,
    VERTICAL_DIMS,
    absent_fill,
    codecs_match,
    declared_fill,
    obs_chunk,
    open_existing_repository,
    resolve_chunks,
    resolve_compression,
    store_sources,
    time_order,
    time_source,
    time_units,
    vertical_order,
)

LOG = logging.getLogger(__name__)

PHASES = ('structure', 'index', 'values', 'repository')
DEFAULT_PHASES = PHASES

# global attributes the build writes and the style guide or this project
# requires on every store
REQUIRED_ATTRS = (
    'title', 'summary', 'Conventions', 'source', 'cdm_data_type',
    'temporal_frequency', 'original_temporal_frequency', 'source_processor_version',
    'nomenclature', 'layout', 'quality_filtering',
)

# commits the pipeline itself makes, besides the build's own
KNOWN_MESSAGES = ('Repository initialized', 'add provenance and discovery attributes')


class Report:
    """Collects check outcomes so the exit status can reflect all of them.

    Attributes:
        failures (list): Labels of the checks that failed.
        n_checks (int): How many checks were recorded.
    """

    def __init__(self):
        self.failures = []
        self.n_checks = 0

    def check(self, label, ok, detail=''):
        """Record a pass or fail.

        Args:
            label (str): What was checked.
            ok (bool): Whether it held.
            detail (str): Measured values to log alongside the verdict.

        Returns:
            bool: The ``ok`` that was passed in, so callers can branch on it.
        """
        self.n_checks += 1
        LOG.info(f'{"PASS" if ok else "FAIL"}  {label}{"  " + detail if detail else ""}')
        if not ok:
            self.failures.append(label)
        return ok

    def note(self, message):
        """Log an observation that is not a pass/fail judgement.

        Args:
            message (str): The observation.
        """
        LOG.info(f'note  {message}')


def parse_args():
    """Parse the command line.

    Returns:
        argparse.Namespace: The parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description='verify the zarr stores of one wiso-sat level 2 product against raw.'
    )
    parser.add_argument(
        '--config', type=str, required=True, help='Path to YAML configuration file.'
    )
    parser.add_argument(
        '--phases',
        type=str,
        default=','.join(DEFAULT_PHASES),
        help=f'Comma separated subset of {",".join(PHASES)}. A run that skips '
        'a phase does not count as verification.',
    )
    parser.add_argument(
        '--stores',
        type=str,
        default=None,
        help='Comma separated subset of the stores the config builds. Defaults '
        'to all of them. The geolocation store is always opened, since the '
        'index check is against it, but its values are compared only if named.',
    )
    return parser.parse_args()


def missing_rows(values, fill=()):
    """Rows of a raw array that hold no value at all.

    Missing is the netCDF default fill for the dtype, a declared fill, or NaN.
    Written apart from the build's ``utils.granules.unwritten``, so that the
    two sides cannot agree by construction on which rows are observations.

    Args:
        values (numpy.ndarray): Observation dimension first.
        fill (Iterable): The source's declared fill values.

    Returns:
        numpy.ndarray: bool per row.
    """
    flat = values.reshape(values.shape[0], -1)
    empty = np.isnan(flat) if flat.dtype.kind == 'f' else np.zeros(flat.shape, dtype=bool)
    default = netCDF4.default_fillvals.get(values.dtype.str[1:])
    for value in [*fill, *([] if default is None else [default])]:
        empty |= flat == np.asarray(value, dtype=flat.dtype)
    return empty.all(axis=1)


def to_epoch(values, unit):
    """datetime64 values as the int64 count the stores hold.

    Args:
        values (numpy.ndarray): datetime64, already in ``unit``.
        unit (str): numpy datetime64 unit code, from the key, e.g. 'ms'.

    Returns:
        numpy.ndarray: int64 ``unit`` since 1900-01-01.
    """
    return (values.astype(f'datetime64[{unit}]') - np.datetime64(TIME_EPOCH, unit)).astype('int64')


def read_expected(granule, reader_name, items, time, unit, location, allowed, declared=None, masks=()):
    """Read every file of one granule with h5py and compute what it contributes.

    A top-level function of picklable arguments, so it runs in a process pool.
    Each file is read on its own: in a multi-file granule, where each file's
    observations sit along the store's obs axis is worked out afterwards, by
    matching them to the stored geolocation, rather than by repeating the
    build's merge.

    Args:
        granule (Granule): The granule.
        reader_name (str): The product, whose reader supplies the time decoding
            and the layout check.
        items (list): ``(source, fill, factor, absent)`` per source to read.
        time (str): The time coordinate's source path.
        unit (str): The datetime64 unit the key stores time in.
        location (tuple): Source paths of time, lat and lon: a row is an
            observation only if all three are written (user decision
            2026-10-17).
        allowed (tuple): Sources that may hold values on a row left out.
        declared (DeclaredRows | None): Rows the config leaves out of this
            granule. They are left out here too, but only after this reads
            for itself that they match as declared.
        masks (tuple): The config's ``declared_masked_values``; the reader's
            ``declared_masks`` finds and confirms them in each file.

    Returns:
        list: Per file, a dict with ``path``, ``n_rows``, ``n_obs``,
            ``masked`` (source -> bool over the file's observations, the
            values declared defects) and ``mask_problems``,
            ``declared`` (rows left out as declared), ``declared_problems``
            (where they do not match their declaration),
            ``timed`` (rows left out although their time is written),
            ``leaked`` (values on rows left out that may not be lost),
            ``version``, ``platform`` (None unless the reader names a
            ``PLATFORM_ATTR``),
            ``problems`` (layout), and ``sources``: per source present in the
            file, the ``expected`` stored values, the ``dtype`` as published,
            its ``attrs``, how many values matched a declared ``fill``, how many
            matched an ``undeclared`` netCDF default fill, and how many equal
            the declared ``absent`` value, which must be none.
    """
    reader = __import__(f'products.{reader_name}', fromlist=['decode_time'])
    files = []
    for path in granule.paths:
        out = {'path': path, 'sources': {}}
        with h5py.File(path, 'r') as handle:
            version = handle.attrs.get(reader.VERSION_ATTR, '')
            # a reader whose version attribute is not text says how to read it
            out['version'] = (
                reader.file_version(version) if hasattr(reader, 'file_version')
                else str(decode_text(version))
            )
            platform_attr = getattr(reader, 'PLATFORM_ATTR', None)
            out['platform'] = (
                str(decode_text(handle.attrs.get(platform_attr, ''))) if platform_attr else None
            )
            out['problems'] = reader.check_granule(handle)
            # a row is an observation only if its time, lat and lon are all
            # written; the rest are not stored, as long as nothing else that
            # may not be lost is written on them. Worked out here from raw,
            # not taken from the build
            fills = {source: fill for source, fill, _, _ in items}
            raw_location = {source: handle[source][...] for source in location}
            processed = np.ones(raw_location[time].shape[0], dtype=bool)
            for source, values in raw_location.items():
                processed &= ~missing_rows(values, fills.get(source, ()))
            # rows the config declares as repeats of others: observations,
            # but left out once their declared match is seen here in raw
            dropped = declared_mask(processed.size, declared)
            kept = processed & ~dropped
            out['n_rows'] = int(processed.size)
            out['n_obs'] = int(kept.sum())
            out['declared'] = int(dropped.sum())
            out['declared_problems'] = (
                declared_problems(handle, declared, location, items) if declared else []
            )
            out['timed'] = int(
                (~processed & ~missing_rows(raw_location[time], fills.get(time, ()))).sum()
            )
            out['masked'], out['mask_problems'] = (
                reader.declared_masks(handle, path, masks, kept) if masks else ({}, [])
            )
            out['leaked'] = 0
            for source, fill, factor, absent in items:
                if source not in handle:
                    continue
                dataset = handle[source]
                raw = raw_location[source] if source in raw_location else dataset[...]
                if not processed.all() and source not in location and source not in allowed:
                    out['leaked'] += int((~missing_rows(raw[~processed], fill)).sum())
                if not kept.all():
                    raw = raw[kept]
                # the style guide's squeeze, done here without the build's helper
                raw = raw.reshape(
                    [size for axis, size in enumerate(raw.shape) if axis == 0 or size != 1]
                )
                attrs = {
                    key: decode_text(value) for key, value in dataset.attrs.items()
                    if key not in ('DIMENSION_LIST', 'REFERENCE_LIST', 'CLASS', 'NAME', '_Netcdf4Dimid')
                }
                entry = {'dtype': str(raw.dtype), 'attrs': attrs}
                if source == time:
                    entry.update(
                        expected=to_epoch(reader.decode_time(raw), unit),
                        fill=0, undeclared=0, absent=0,
                    )
                    out['sources'][source] = entry
                    continue

                masked = np.zeros(raw.shape, dtype=bool)
                for value in fill:
                    masked |= raw == np.asarray(value, dtype=raw.dtype)
                default = netCDF4.default_fillvals.get(raw.dtype.str[1:])
                undeclared = 0
                if default is not None and not any(
                    np.asarray(value, dtype=raw.dtype) == np.asarray(default, dtype=raw.dtype)
                    for value in fill
                ):
                    undeclared = int((raw == np.asarray(default, dtype=raw.dtype)).sum())
                clashes = 0
                if absent is not None:
                    clashes = int((raw == np.asarray(absent, dtype=raw.dtype)).sum())

                if raw.dtype.kind == 'f':
                    expected = raw.astype('float64')
                    expected[masked] = np.nan
                    if factor is not None:
                        expected = expected * factor
                    with np.errstate(over='ignore'):
                        expected = expected.astype(raw.dtype)
                else:
                    expected = raw
                entry.update(
                    expected=expected, fill=int(masked.sum()), undeclared=undeclared,
                    absent=clashes,
                )
                out['sources'][source] = entry
        files.append(out)
    return files


def declared_problems(handle, declared, location, items):
    """Where a granule's declared rows do not match their declaration, from raw.

    Read with h5py, apart from the build's check in the reader: a repeat must
    equal its block bit for bit in every source read except those the
    declaration exempts; an overlap must have exactly the other granule's
    time, latitude and longitude.

    Args:
        handle (h5py.File): The granule's open file.
        declared (DeclaredRows): Its declaration.
        location (tuple): Source paths of time, lat and lon.
        items (list): ``(source, fill, factor, absent)`` per source read.

    Returns:
        list: Problems, empty if the declaration holds.
    """
    rows = slice(declared.start, declared.stop)
    problems = []
    if declared.repeat_of is not None:
        first, last = declared.repeat_of
        sources = dict.fromkeys([*location, *(source for source, _, _, _ in items)])
        for source in sources:
            if source in declared.repeat_except or source not in handle:
                continue
            values = handle[source][...]
            block = values[first:last]
            copies = values[rows].reshape((-1,) + block.shape)
            if not all(
                np.array_equal(copy.view(np.uint8), block.view(np.uint8)) for copy in copies
            ):
                problems.append(
                    f'{source} rows {declared.start}-{declared.stop - 1} are not copies of '
                    f'rows {first}-{last - 1}'
                )
    if declared.location_of is not None:
        other, first, last, path = declared.location_of
        with h5py.File(path, 'r') as theirs:
            for source in location:
                ours = handle[source][rows].view(np.uint8)
                if not np.array_equal(ours, theirs[source][first:last].view(np.uint8)):
                    problems.append(f'{source} differs from orbit {other} rows {first}-{last - 1}')
    return problems


def same_values(stored, expected):
    """Count observations where a store differs from what raw says.

    Args:
        stored (numpy.ndarray): The stored values, undecoded.
        expected (numpy.ndarray): From ``read_expected``.

    Returns:
        int: The number of mismatching elements.
    """
    if stored.shape != expected.shape:
        return max(stored.size, expected.size)
    if stored.dtype.kind == 'f':
        nan_stored, nan_expected = np.isnan(stored), np.isnan(expected)
        # bit patterns, so -0.0 against 0.0 or a one-ulp difference counts
        unequal = stored.view(f'u{stored.itemsize}') != expected.view(f'u{expected.itemsize}')
        return int(((nan_stored != nan_expected) | (unequal & ~nan_stored & ~nan_expected)).sum())
    return int((stored != expected).sum())


def open_groups(settings, stores):
    """Open each store's root group read only.

    Args:
        settings (dict): The loaded configuration.
        stores (list): Store variable slots.

    Returns:
        dict: Store -> ``(repository, zarr.Group)``.
    """
    opened = {}
    for store in stores:
        path = store_path(settings, store)
        LOG.info(f'verifying {path}')
        repository = open_existing_repository(path)
        session = repository.readonly_session(branch=BRANCH)
        opened[store] = (repository, zarr.open_group(session.store, mode='r'))
    return opened


def check_structure(report, settings, store, group, chunks, codecs):
    """Check one store's layout, encoding and attributes from metadata.

    Args:
        report (Report): Where to record outcomes.
        settings (dict): The loaded configuration.
        store (str): The store's variable slot.
        group (zarr.Group): Its root group.
        chunks (dict): The configured chunks.
        codecs (dict): The configured codecs, from ``resolve_compression``.
    """
    source_name = source_product(settings)
    names = set(group.array_keys())
    expected_vars = set(store_sources(source_name, store))
    fields = set(index_fields(load_reader(settings)))
    report.check(
        f'{store}: holds exactly its variables and the granule index',
        names == expected_vars | fields,
        f'{sorted(names)}',
    )

    for name in sorted(names & (expected_vars | fields)):
        array = group[name]
        dims = array.metadata.dimension_names or ()
        leading = 'obs' if name in expected_vars else GRANULE_DIM
        length = chunks[leading]
        if leading == 'obs':
            length = obs_chunk(length, array.dtype.itemsize, tuple(array.shape[1:]))
        report.check(
            f'{store}/{name}: leading dimension {leading}, chunked {length}, '
            f'secondary dimensions whole',
            bool(dims) and dims[0] == leading
            and array.chunks == (length,) + tuple(array.shape[1:]),
            f'{dims} {array.chunks}',
        )
        ok, detail = codecs_match(array, codecs)
        report.check(f'{store}/{name}: compressed and sharded as the config sets', ok, detail)

    for name in sorted(expected_vars & names):
        array, attrs = group[name], dict(group[name].attrs)
        dims = array.metadata.dimension_names or ()
        if set(dims) & set(VERTICAL_DIMS):
            order = vertical_order(settings)
            report.check(
                f'{store}/{name}: vertical_order is {order!r}',
                attrs.get('vertical_order') == order, f'{attrs.get("vertical_order")!r}',
            )
        if name == 'time' or name.startswith('granule_time'):
            units = time_units(source_name)[0]
            report.check(
                f'{store}/{name}: int64 {units!r}, {TIME_CALENDAR}',
                str(array.dtype) == 'int64' and attrs.get('units') == units
                and attrs.get('calendar') == TIME_CALENDAR,
                f'{array.dtype} {attrs.get("units")!r} {attrs.get("calendar")!r}',
            )
            continue
        source = store_sources(source_name, store)[name]
        fill = declared_fill(settings, source)
        if np.dtype(str(array.dtype)).kind == 'f':
            # the attribute is xarray's base64 encoding of the float, so the
            # array's own fill value is what is read
            report.check(
                f'{store}/{name}: floating, NaN fill',
                bool(np.isnan(array.fill_value)) and '_FillValue' in attrs,
                f'{array.dtype} {array.fill_value}',
            )
        else:
            expected_fill = fill[0] if fill else absent_fill(settings, source)
            report.check(
                f'{store}/{name}: integer, _FillValue is the declared fill',
                attrs.get('_FillValue') == expected_fill,
                f'{array.dtype} {attrs.get("_FillValue")!r} against declared {expected_fill!r}',
            )

        if store == GEOLOCATION:
            entry = coordinates(source_name)[name]
            report.check(
                f'{store}/{name}: units {entry.units!r}',
                attrs.get('units') == entry.units, f'{attrs.get("units")!r}',
            )
            report.check(
                f'{store}/{name}.unit_conversion records {entry.unit_conversion!r}',
                str(attrs.get('unit_conversion', '')).startswith(entry.unit_conversion),
                f'{attrs.get("unit_conversion")!r}',
            )
            continue
        entry = key_variable(source_name, name)
        for key, value in (
            ('units', entry.units),
            ('long_name', entry.long_name),
            ('original_variable_name', entry.original),
        ):
            report.check(
                f'{store}/{name}.{key} is {value!r}', attrs.get(key) == value, f'{attrs.get(key)!r}'
            )
        report.check(
            f'{store}/{name}.unit_conversion records {entry.unit_conversion!r}',
            str(attrs.get('unit_conversion', '')).startswith(entry.unit_conversion),
            f'{attrs.get("unit_conversion")!r}',
        )

    attrs = dict(group.attrs)
    missing = [key for key in REQUIRED_ATTRS if not attrs.get(key)]
    report.check(f'{store}: carries every required global attribute', not missing, f'missing {missing}')
    frequency = canonical_frequency(source_name, settings['temporal_resolution'])
    for key, value in (
        ('cdm_data_type', 'Point'),
        ('temporal_frequency', frequency),
        ('source_processor_version', str(settings['version'])),
    ):
        report.check(f'{store}: {key} is {value!r}', attrs.get(key) == value, f'{attrs.get(key)!r}')
    report.check(
        f'{store}: quality_filtering says none applied',
        str(attrs.get('quality_filtering', '')).startswith('none applied'),
    )
    stem = os.path.basename(store_path(settings, store))
    report.check(
        f'{store}: store name carries the version, frequency and variable',
        f'.{version_token(settings)}.{frequency}.' in stem
        and stem.endswith(f'.{store}.zarr'),
        stem,
    )
    report.check(
        f'{store}: layout states the time order {time_order(settings)!r}',
        str(attrs.get('layout', '')).endswith(
            'time never decreases along obs.' if time_order(settings) == 'sorted'
            else '(granule_time_start, granule_time_end).'
        ),
        f'{str(attrs.get("layout", ""))[-80:]!r}',
    )


def read_index(group, fields):
    """A store's granule index, undecoded.

    Args:
        group (zarr.Group): The store's root group.
        fields (tuple): The index fields, from ``index_fields``.

    Returns:
        dict: Index field -> numpy array.
    """
    return {field: np.asarray(group[field][...]) for field in fields}


def check_index(report, settings, groups, granules):
    """Check every store carries one identical index matching the listing.

    Args:
        report (Report): Where to record outcomes.
        settings (dict): The loaded configuration.
        groups (dict): Store -> zarr.Group.
        granules (list): The raw listing.

    Returns:
        dict: The geolocation store's index, for the values phase.
    """
    try:
        check_order(granules)
        frequency = getattr(load_reader(settings), 'COVERAGE_FREQUENCY', 'D')
        missing = check_coverage(granules, settings, frequency)
        report.check('raw listing: unique granules, missing days as declared', True,
                     f'{len(granules)} granules, {len(missing)} declared missing periods')
    except ValueError as error:
        report.check('raw listing: unique granules, missing days as declared', False, str(error))

    fields = index_fields(load_reader(settings))
    reference = read_index(groups[GEOLOCATION], fields)
    for store, group in groups.items():
        index = read_index(group, fields)
        report.check(
            f'{store}: granule index identical to the geolocation store',
            all(np.array_equal(index[field], reference[field]) for field in fields),
        )
        n_obs = group[next(iter(store_sources(source_product(settings), store)))].shape[0]
        report.check(
            f'{store}: obs length is the sum of the index counts',
            n_obs == int(index['granule_obs_count'].sum()),
            f'{n_obs} against {int(index["granule_obs_count"].sum())}',
        )

    report.check(
        'index: granule ids and files are the raw listing, in order',
        [str(value) for value in reference['granule_id']] == [g.id for g in granules]
        and [str(value) for value in reference['granule_file']]
        == [FILE_SEPARATOR.join(os.path.basename(path) for path in g.paths) for g in granules],
        f'{len(reference["granule_id"])} indexed, {len(granules)} listed',
    )
    counts = reference['granule_obs_count'].astype('int64')
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]])
    report.check(
        'index: obs starts are the running sum of the counts',
        np.array_equal(reference['granule_obs_start'], starts),
    )
    return reference


class ChunkSpans:
    """Reads granule slices of stored arrays, decoding each chunk once.

    The values phase reads one granule at a time, and a granule can be far
    smaller than a chunk: a SCIAMACHY orbit is ~1,900 obs, a 1-D chunk
    4,194,304. Reading each slice straight from zarr decoded the whole chunk
    every time, ~1.5 cpu-s per orbit over 22 stores (TESTING.md finding 14).
    This keeps, per array, the last chunk-aligned span it decoded, and serves
    every later slice that falls inside it. Granules come in order, so each
    chunk is decoded about once. Values are returned exactly as zarr reads
    them, undecoded, so the comparison is unchanged.

    Attributes:
        spans (dict): Array key -> ``(start, stop, values)`` last decoded.
    """

    def __init__(self):
        self.spans = {}

    def read(self, key, array, lo, hi):
        """The stored values ``array[lo:hi]``.

        Args:
            key (tuple): Identifies the array, e.g. ``(store, name)``.
            array (zarr.Array): The stored array, ``obs`` first.
            lo (int): First obs.
            hi (int): One past the last.

        Returns:
            numpy.ndarray: The slice, a read-only view of the span.
        """
        span = self.spans.get(key)
        if span is None or not span[0] <= lo <= hi <= span[1]:
            chunk = array.chunks[0]
            start = lo // chunk * chunk
            stop = min(array.shape[0], max(-(-hi // chunk) * chunk, start + chunk))
            values = np.asarray(array[start:stop])
            # every later slice is a view of this, so nothing may write to it
            values.flags.writeable = False
            span = self.spans[key] = (start, stop, values)
        return span[2][lo - span[0]:hi - span[0]]


class Pass:
    """Accumulates the values phase over every granule.

    Attributes:
        mismatches (dict): ``(store, name)`` -> mismatching values.
        fill (dict): Source -> values matching a declared fill.
        undeclared (dict): Source -> values matching an undeclared default fill.
        absent (dict): Source -> raw values equal to its declared absent fill.
        missing (dict): Source -> granules where no file holds it.
        problems (list): ``(granule id, problem)`` from the layout check.
        declared (int): Rows left out as the config declares.
        declared_problems (list): ``(granule id, problem)`` where declared
            rows do not match their declaration.
        index (dict): Index field -> mismatching granules.
        placement (dict): Merge failures in multi-file granules, by kind.
        versions (set): Processor versions seen.
        platforms (set): Platforms seen; None where the reader names none.
        bounds (list): ``[lat_min, lat_max, lon_min, lon_max]``.
        decreasing (int): Places where time decreases.
        dtypes (dict): Source -> dtypes seen.
        attrs (dict): Source -> the first granule's attributes.
        standard_names (dict): Source -> the ``standard_name`` attributes any
            file holding it carries.
        masked (dict): Source -> values found and confirmed as declared
            defects.
        first_time, last_time: The stored times at either end of a range.
    """

    def __init__(self):
        self.mismatches = {}
        self.fill = {}
        self.undeclared = {}
        self.absent = {}
        self.missing = {}
        self.problems = []
        self.index = {
            'granule_obs_count': 0, 'granule_source_rows': 0,
            'granule_time_start': 0, 'granule_time_end': 0,
        }
        self.leaked = 0
        self.unprocessed = 0
        self.declared = 0
        self.declared_problems = []
        self.timed = 0
        self.placement = {'unmatched': 0, 'reordered': 0, 'unaccounted': 0}
        self.versions = set()
        self.platforms = set()
        self.bounds = [np.inf, -np.inf, np.inf, -np.inf]
        self.decreasing = 0
        self.dtypes = {}
        self.attrs = {}
        self.standard_names = {}
        self.masked = {}
        self.first_time = None
        self.last_time = None


def observation_keys(columns):
    """Rows of matching columns as hashable keys, bit for bit.

    Args:
        columns (list): Equal-length 1-D arrays.

    Returns:
        list: One tuple of raw integers per row. Floats are compared by their
            bit patterns, so a key matches only the identical value.
    """
    views = [
        column.view(f'u{column.dtype.itemsize}') if column.dtype.kind == 'f' else column
        for column in columns
    ]
    return list(zip(*(view.tolist() for view in views)))


def place_files(files, stored_keys, match_sources, seen):
    """Where each file's observations sit in one stored granule.

    A single file fills the granule in order. A multi-file granule was merged
    by the build; here each file's observations are found again by matching
    their identifying coordinates to the stored ones, so the merge is checked
    without repeating it: every observation must be found exactly once, keep
    its file's order, and every stored observation must come from some file.

    Args:
        files (list): From ``read_expected``.
        stored_keys (list): ``observation_keys`` of the stored granule.
        match_sources (tuple): The source paths that identify an observation.
        seen (Pass): Where to count failures.

    Returns:
        list: Per file, an int array of store positions within the granule,
            or None where its observations could not all be placed.
    """
    if len(files) == 1:
        return [np.arange(files[0]['n_obs'])]

    lookup = {}
    for position, key in enumerate(stored_keys):
        lookup.setdefault(key, position)
    covered = np.zeros(len(stored_keys), dtype=bool)
    placed = []
    for entry in files:
        keys = observation_keys([entry['sources'][source]['expected'] for source in match_sources])
        positions = np.array([lookup.get(key, -1) for key in keys], dtype='int64')
        if (positions < 0).any():
            seen.placement['unmatched'] += int((positions < 0).sum())
            placed.append(None)
            continue
        if (np.diff(positions) <= 0).any():
            seen.placement['reordered'] += 1
        covered[positions] = True
        placed.append(positions)
    seen.placement['unaccounted'] += int((~covered).sum())
    return placed


def value_targets(settings, stores):
    """Every array whose values are compared: ``(store, name, source, factor)``.

    Args:
        settings (dict): The loaded configuration.
        stores (list): The stores compared.

    Returns:
        list: The targets, in store order.
    """
    source_name = source_product(settings)
    targets = []
    for store in stores:
        for name, source in store_sources(source_name, store).items():
            factor = (
                coordinate_factor(coordinates(source_name)[name]) if store == GEOLOCATION
                else conversion_factor(key_variable(source_name, name).unit_conversion)
            )
            targets.append((store, name, source, factor))
    return targets


def value_items(settings, targets):
    """The sources a scan reads: ``(source, fill, factor, absent)``.

    The targets' sources, plus time, lat, lon and the reader's match sources,
    which the index, bounds and placement checks need for every granule
    whether or not the geolocation store's values are compared.

    Args:
        settings (dict): The loaded configuration.
        targets (list): From ``value_targets``.

    Returns:
        list: Sorted by source.
    """
    source_name = source_product(settings)
    key = coordinates(source_name)
    by_source = {entry.original: entry for entry in key.values()}
    match_sources = tuple(getattr(load_reader(settings), 'MATCH_SOURCES', ()))
    factors = {source: factor for _, _, source, factor in targets}
    for source in [key[name].original for name in LOCATION_COORDINATES] + list(match_sources):
        factors.setdefault(source, coordinate_factor(by_source[source]))
    return [
        (source, declared_fill(settings, source), factors[source], absent_fill(settings, source))
        for source in sorted(factors)
    ]


def value_groups(settings, stores):
    """The compared stores, grouped for scanning.

    A store in ``own_process_stores`` is scanned on its own, as it is built
    (TESTING.md finding 12): its sources are read only for it. The others are
    scanned together, each file read once for all of them.

    Args:
        settings (dict): The loaded configuration.
        stores (list): The stores compared.

    Returns:
        list: Lists of stores; the shared group, if any, first.
    """
    own = [store for store in settings.get('own_process_stores') or [] if store in stores]
    shared = [store for store in stores if store not in own]
    return ([shared] if shared else []) + [[store] for store in own]


def scan_values(settings, stores, begin, granules, primary, counted, declared):
    """Compare a group of stores with raw over one range of granules.

    A top-level function of picklable arguments, so it runs in a process
    pool. It reads the raw files and the stored slices itself, and returns
    only what it saw, so no array crosses between processes (TESTING.md
    finding 12).

    Args:
        settings (dict): The loaded configuration.
        stores (list): The stores whose values this scan compares.
        begin (int): The first granule's position in the listing.
        granules (list): The granules of the range, in order.
        primary (bool): Whether this scan also checks what does not depend on
            the stores (the index entries, layout, versions, time order, rows
            left out, merges, bounds), which one group of scans does for all.
        counted (set): The sources whose fill, dtype and attributes this scan
            tallies, so each source is tallied by one group only.
        declared (dict): Granule id -> DeclaredRows, from the config.

    Returns:
        Pass: What the scan saw; ``first_time`` and ``last_time`` are the
            stored times at either end, for the seams between ranges.
    """
    source_name = source_product(settings)
    reader = load_reader(settings)
    time = time_source(source_name)
    _, unit = time_units(source_name)
    coordinate_names = {entry.original: name for name, entry in coordinates(source_name).items()}
    location = tuple(coordinates(source_name)[name].original for name in LOCATION_COORDINATES)
    allowed = tuple(settings.get('allowed_on_rows_left_out') or [])
    targets = value_targets(settings, stores)
    items = value_items(settings, targets)
    match_sources = tuple(getattr(reader, 'MATCH_SOURCES', ()))

    masks = tuple(settings.get('declared_masked_values') or ())
    # a granule the config declares to lack one of its files lacks that
    # file's sources too (TROPESS's one-sided days)
    partial = {str(granule) for granule in settings.get('expected_partial_granules') or {}}
    extra_fields = tuple(getattr(reader, 'INDEX_EXTRA', {}))
    groups = {}
    for store in dict.fromkeys([GEOLOCATION, *stores]):
        session = open_existing_repository(store_path(settings, store)).readonly_session(branch=BRANCH)
        groups[store] = zarr.open_group(session.store, mode='r')
    index = read_index(groups[GEOLOCATION], index_fields(reader))
    starts = index['granule_obs_start']
    counts = index['granule_obs_count']
    stored_start = index['granule_time_start']
    stored_end = index['granule_time_end']
    source_rows = index['granule_source_rows']
    # the geolocation arrays every granule needs, compared or not
    reference = sorted({'time'} | {coordinate_names[source] for source in match_sources})

    seen = Pass()
    spans = ChunkSpans()
    previous = None
    for offset, granule in enumerate(granules):
        position = begin + offset
        files = read_expected(
            granule, source_name, items, time, unit, location, allowed, declared.get(granule.id),
            masks,
        )
        lo = int(starts[position])
        hi = lo + int(counts[position])
        stored = {
            (store, name): spans.read((store, name), groups[store][name], lo, hi)
            for store, name, _, _ in targets
        }
        for name in reference:
            if (GEOLOCATION, name) not in stored:
                stored[(GEOLOCATION, name)] = spans.read(
                    (GEOLOCATION, name), groups[GEOLOCATION][name], lo, hi
                )

        for entry in files:
            seen.leaked += entry['leaked']
            if primary:
                seen.versions.add(entry['version'])
                seen.platforms.add(entry['platform'])
                seen.problems += [(granule.id, problem) for problem in entry['problems']]
                seen.unprocessed += entry['n_rows'] - entry['n_obs'] - entry['declared']
                seen.timed += entry['timed']
                seen.declared += entry['declared']
                seen.declared_problems += [(granule.id, p) for p in entry['declared_problems']]
                seen.problems += [(granule.id, problem) for problem in entry['mask_problems']]
        if primary and sum(entry['n_rows'] for entry in files) != int(source_rows[position]):
            seen.index['granule_source_rows'] += 1
        if primary and hasattr(reader, 'check_files'):
            # what must hold across a granule's files, read here from raw
            seen.problems += [(granule.id, problem) for problem in reader.check_files(granule.paths)]
        if primary and extra_fields:
            expected_extra = reader.index_extra(granule.paths)
            for field in extra_fields:
                if str(index[field][position]) != expected_extra[field]:
                    seen.index[field] = seen.index.get(field, 0) + 1

        # how many observations the granule should hold: every distinct one
        # across its files, found from raw alone
        if len(files) == 1:
            n_expected = files[0]['n_obs']
        else:
            n_expected = len(set().union(*(
                observation_keys([entry['sources'][s]['expected'] for s in match_sources])
                for entry in files
            )))
        if n_expected != int(counts[position]):
            # the values cannot be lined up; the primary scan's count failure
            # says why
            seen.index['granule_obs_count'] += int(primary)
            continue

        stored_time = stored[(GEOLOCATION, 'time')]
        if primary:
            if not stored_time.size:
                # a granule with no observations has no time span
                seen.index['granule_time_start'] += int(stored_start[position] != TIME_FILL)
                seen.index['granule_time_end'] += int(stored_end[position] != TIME_FILL)
            else:
                times = [entry['sources'][time]['expected'] for entry in files]
                seen.index['granule_time_start'] += int(
                    min(t.min() for t in times if t.size) != stored_start[position]
                )
                seen.index['granule_time_end'] += int(
                    max(t.max() for t in times if t.size) != stored_end[position]
                )
                seen.decreasing += int((np.diff(stored_time) < 0).sum())
                if previous is not None and stored_time[0] < previous:
                    seen.decreasing += 1
                previous = stored_time[-1]
                if seen.first_time is None:
                    seen.first_time = stored_time[0]
                seen.last_time = stored_time[-1]

        stored_keys = (
            observation_keys([
                stored[(GEOLOCATION, coordinate_names[source])] for source in match_sources
            ]) if len(files) > 1 else None
        )
        placement = Pass()
        placed = place_files(files, stored_keys, match_sources, placement)
        if primary:
            for kind, count in placement.placement.items():
                seen.placement[kind] += count

        # the store positions of values declared defects, from whichever file
        # found them: the store holds NaN there, whatever any file says
        masked_at = {}
        for entry, positions in zip(files, placed):
            for source, mask in entry['masked'].items():
                if positions is None:
                    continue
                at = masked_at.setdefault(source, np.zeros(int(counts[position]), dtype=bool))
                at[positions[mask]] = True

        for store, name, source, _ in targets:
            key = (store, name)
            values = stored[key]
            covered = np.zeros(values.shape[0], dtype=bool)
            mask = masked_at.get(source)
            holders = 0
            for entry, positions in zip(files, placed):
                if source not in entry['sources'] or positions is None:
                    continue
                holders += 1
                found = entry['sources'][source]
                here = values[positions]
                expected = found['expected']
                if mask is not None:
                    keep = ~mask[positions]
                    here, expected = here[keep], expected[keep]
                seen.mismatches[key] = seen.mismatches.get(key, 0) + same_values(here, expected)
                covered[positions] = True
            if mask is not None and mask.any():
                defects = values[mask]
                seen.mismatches[key] = seen.mismatches.get(key, 0) + int(
                    (~np.isnan(defects)).sum() if defects.dtype.kind == 'f' else defects.size
                )
                if source in counted:
                    seen.masked[source] = seen.masked.get(source, 0) + int(mask.sum())
            if not holders and granule.id not in partial:
                seen.missing[source] = seen.missing.get(source, 0) + 1
                continue
            # where no file holds the observation, the store must say so: NaN,
            # or the declared absent fill for an integer
            rest = values[~covered]
            if rest.size:
                if rest.dtype.kind == 'f':
                    wrong = int((~np.isnan(rest)).sum())
                else:
                    wrong = int((rest != absent_fill(settings, source)).sum())
                seen.mismatches[key] = seen.mismatches.get(key, 0) + wrong

        for entry in files:
            for source, found in entry['sources'].items():
                if source not in counted:
                    continue
                seen.fill[source] = seen.fill.get(source, 0) + found['fill']
                seen.undeclared[source] = seen.undeclared.get(source, 0) + found['undeclared']
                seen.absent[source] = seen.absent.get(source, 0) + found['absent']
                seen.dtypes.setdefault(source, set()).add(found['dtype'])
                seen.attrs.setdefault(source, found['attrs'])
                if found['attrs'].get('standard_name'):
                    seen.standard_names.setdefault(source, set()).add(found['attrs']['standard_name'])
            if primary:
                for name, low, high in (('lat', 0, 1), ('lon', 2, 3)):
                    values = entry['sources'][coordinates(source_name)[name].original]['expected']
                    finite = values[np.isfinite(values)]
                    if finite.size:
                        seen.bounds[low] = min(seen.bounds[low], float(finite.min()))
                        seen.bounds[high] = max(seen.bounds[high], float(finite.max()))
    return seen


def merge_pass(total, part):
    """Fold one scan's ``Pass`` into the running total, in granule order.

    Args:
        total (Pass): The total so far.
        part (Pass): The next range's scan.
    """
    for field in ('mismatches', 'fill', 'undeclared', 'absent', 'missing', 'masked', 'index'):
        tally = getattr(total, field)
        for key, count in getattr(part, field).items():
            tally[key] = tally.get(key, 0) + count
    for key, count in part.placement.items():
        total.placement[key] += count
    for source, names in part.standard_names.items():
        total.standard_names.setdefault(source, set()).update(names)
    total.problems += part.problems
    total.declared += part.declared
    total.declared_problems += part.declared_problems
    total.leaked += part.leaked
    total.unprocessed += part.unprocessed
    total.timed += part.timed
    total.decreasing += part.decreasing
    total.versions |= part.versions
    total.platforms |= part.platforms
    total.bounds = [
        min(total.bounds[0], part.bounds[0]), max(total.bounds[1], part.bounds[1]),
        min(total.bounds[2], part.bounds[2]), max(total.bounds[3], part.bounds[3]),
    ]
    for source, dtypes in part.dtypes.items():
        total.dtypes.setdefault(source, set()).update(dtypes)
    for source, attrs in part.attrs.items():
        total.attrs.setdefault(source, attrs)
    # the seam between two ranges: time must not step back across it
    if part.first_time is not None:
        if total.last_time is not None and part.first_time < total.last_time:
            total.decreasing += 1
        total.first_time = total.first_time if total.first_time is not None else part.first_time
        total.last_time = part.last_time


def check_values(report, settings, groups, compared, granules, index, num_workers, task_granules):
    """Compare every value of every compared store with raw.

    The work is split into scans of one group of stores (``value_groups``)
    over one range of ``task_granules`` granules, run in ``num_workers``
    processes. Each scan reads what it needs itself and returns only counts,
    which are merged here in granule order before the record-wide checks.

    Args:
        report (Report): Where to record outcomes.
        settings (dict): The loaded configuration.
        groups (dict): Store -> zarr.Group, every store opened.
        compared (list): The stores whose values are compared.
        granules (list): The raw listing, which the index phase matched.
        index (dict): The geolocation store's index.
        num_workers (int): Scan processes.
        task_granules (int): Granules per scan.

    Returns:
        Pass: What the scans saw, for the evidence lines.
    """
    counts = index['granule_obs_count']
    targets = value_targets(settings, compared)
    items = value_items(settings, targets)
    scan_groups = value_groups(settings, compared)
    # rows the config leaves out by name, resolved against the listing; each
    # scan confirms them from raw itself
    declared = declared_rows(settings, granules)
    if declared and not getattr(load_reader(settings), 'DECLARED_ROWS', False):
        raise ValueError(
            f'declared_rows_left_out is set, but the {source_product(settings)} reader '
            f'does not apply declared rows'
        )
    if settings.get('declared_masked_values') and not getattr(load_reader(settings), 'DECLARED_MASKS', False):
        raise ValueError(
            f'declared_masked_values is set, but the {source_product(settings)} reader '
            f'does not apply declared masks'
        )
    # each source is tallied by the group that compares it; the coordinates
    # every scan reads, by the first group
    owner = {source: 0 for source, _, _, _ in items}
    for number, stores in enumerate(scan_groups):
        for _, _, source, _ in value_targets(settings, stores):
            owner[source] = number
    counted = [
        {source for source, number in owner.items() if number == group}
        for group in range(len(scan_groups))
    ]
    ranges = [
        (begin, min(begin + task_granules, len(granules)))
        for begin in range(0, len(granules), task_granules)
    ]
    tasks = [
        (number, begin, end) for number in range(len(scan_groups)) for begin, end in ranges
    ]
    LOG.info(
        f'{len(tasks)} scans: {len(scan_groups)} groups {scan_groups} x {len(ranges)} '
        f'ranges of {task_granules} granules, {num_workers} processes'
    )

    def arguments(task):
        number, begin, end = task
        return (settings, scan_groups[number], begin, granules[begin:end], number == 0,
                counted[number], declared)

    parts = {}
    pool = (
        concurrent.futures.ProcessPoolExecutor(
            max_workers=num_workers, mp_context=multiprocessing.get_context('spawn')
        ) if num_workers > 1 else None
    )
    try:
        if pool is None:
            for done, task in enumerate(tasks, 1):
                parts[task] = scan_values(*arguments(task))
                LOG.info(f'scanned {done} of {len(tasks)}: group {task[0]}, granules {task[1]}-{task[2] - 1}')
        else:
            futures = {pool.submit(scan_values, *arguments(task)): task for task in tasks}
            for done, future in enumerate(concurrent.futures.as_completed(futures), 1):
                task = futures[future]
                parts[task] = future.result()
                LOG.info(f'scanned {done} of {len(tasks)}: group {task[0]}, granules {task[1]}-{task[2] - 1}')
    finally:
        if pool is not None:
            pool.shutdown()

    seen = Pass()
    for task in sorted(parts):
        merge_pass(seen, parts[task])

    for store, name, _, _ in targets:
        count = seen.mismatches.get((store, name), 0)
        report.check(
            f'{store}/{name}: every observation matches raw, bit for bit',
            count == 0, f'{count} mismatches over {int(counts.sum())} obs',
        )
    for field, count in seen.index.items():
        report.check(f'index: {field} matches every raw file', count == 0, f'{count} granules differ')
    if any(len(granule.paths) > 1 for granule in granules):
        report.check(
            'merged granules: every file observation placed once, in file '
            'order, and every stored observation from some file',
            not any(seen.placement.values()), f'{seen.placement}',
        )
    report.check(
        f'every file declares processor version {settings["version"]!r}',
        seen.versions == {str(settings['version'])}, f'{sorted(seen.versions)}',
    )
    if getattr(load_reader(settings), 'PLATFORM_ATTR', None):
        # the product token names every store, as the version does
        report.check(
            f'every file declares platform {settings.get("platform")!r}',
            seen.platforms == {settings.get('platform')}, f'{sorted(map(str, seen.platforms))}',
        )
    if time_order(settings) == 'sorted':
        report.check(
            'time never decreases along obs', seen.decreasing == 0, f'{seen.decreasing} decreases'
        )
    else:
        report.note(
            f'time order kept from the source (time_order: source): time decreases '
            f'{seen.decreasing} times along obs, as the files have it'
        )
    for entry in settings.get('declared_masked_values') or []:
        source = entry['source']
        report.check(
            f'{source}: values declared defects confirmed in raw and stored as NaN',
            seen.masked.get(source, 0) > 0 and not seen.problems,
            f'{seen.masked.get(source, 0)} values ({entry.get("reason", "")[:60]})',
        )
    report.check(
        'rows left out (no time, lat or lon) hold no data beyond what the config allows',
        seen.leaked == 0,
        f'{seen.unprocessed} rows left out, {seen.timed} of them with a time; '
        f'{seen.leaked} values on them',
    )
    if declared:
        expected = sum(entry.stop - entry.start for entry in declared.values())
        report.check(
            'declared rows left out: each matches its declaration in raw',
            not seen.declared_problems and seen.declared == expected,
            f'{seen.declared} of {expected} declared rows left out, '
            f'{len(seen.declared_problems)} problems {seen.declared_problems[:3]}',
        )
    report.check(
        'every file has the documented layout', not seen.problems,
        f'{len(seen.problems)} problems, first {seen.problems[:3]}',
    )
    casts = settings.get('source_dtypes') or {}
    partial = settings.get('expected_partial_granules') or {}
    for source, fill, _, absent in items:
        report.check(
            f'{source}: held by a file of every granule'
            + (f' but the {len(partial)} declared partial ones' if partial else ''),
            not seen.missing.get(source), f'{seen.missing.get(source, 0)} granules lack it',
        )
        if fill:
            report.check(
                f'{source}: declared fill {fill} occurs in the record',
                seen.fill.get(source, 0) > 0, f'{seen.fill.get(source, 0)} values',
            )
        if absent is not None:
            report.check(
                f'{source}: absent fill {absent} never occurs in raw',
                seen.absent.get(source, 0) == 0, f'{seen.absent.get(source, 0)} values',
            )
        report.check(
            f'{source}: no undeclared netCDF default fill',
            seen.undeclared.get(source, 0) == 0, f'{seen.undeclared.get(source, 0)} values',
        )
        if source in casts:
            # integer widths that drift between files, cast to one declared
            # dtype; the values phase has compared every value after the cast
            report.check(
                f'{source}: every dtype across the record is an integer the declared '
                f'{casts[source]} holds',
                all(np.dtype(dtype).kind in 'iu' for dtype in seen.dtypes.get(source, ())),
                f'{sorted(seen.dtypes.get(source, ()))}',
            )
        else:
            report.check(
                f'{source}: one dtype across the record',
                len(seen.dtypes.get(source, ())) == 1, f'{sorted(seen.dtypes.get(source, ()))}',
            )

    # a source standard_name is retained unchanged, and none is ever added.
    # In a merged granule it may be on one of the files only (TROPESS's
    # Summary carries one for x_h2o, its Standard file none)
    for store, name, source, _ in targets:
        stored_attrs = dict(groups[store][name].attrs)
        names = seen.standard_names.get(source, set())
        raw = next(iter(names)) if len(names) == 1 else (None if not names else sorted(names))
        report.check(
            f'{store}/{name}: standard_name is the source one, or absent with it',
            stored_attrs.get('standard_name') == raw,
            f'{stored_attrs.get("standard_name")!r} against source {raw!r}',
        )
        if store != GEOLOCATION:
            expected_dtypes = {casts[source]} if source in casts else seen.dtypes.get(source, set())
            report.check(
                f'{store}/{name}: dtype is the source dtype, or the declared cast',
                str(groups[store][name].dtype) in expected_dtypes,
                f'{groups[store][name].dtype} against {sorted(expected_dtypes)}',
            )
    return seen


def check_repository(report, repositories):
    """Check every commit in each store's history is one the pipeline makes.

    Args:
        report (Report): Where to record outcomes.
        repositories (dict): Store -> icechunk.Repository.
    """
    for store, repository in repositories.items():
        messages = [snapshot.message for snapshot in repository.ancestry(branch=BRANCH)]
        unknown = [
            message for message in messages
            if not message.startswith(COMMIT_PREFIX) and message not in KNOWN_MESSAGES
        ]
        report.check(
            f'{store}: every commit is the pipeline\'s own', not unknown,
            f'{len(messages)} commits, unknown {unknown[:3]}',
        )


def main(settings, args):
    """Run the selected phases and return a process exit status.

    Args:
        settings (dict): The loaded configuration.
        args (argparse.Namespace): Parsed arguments.

    Returns:
        int: 0 if every check passed, 1 otherwise.

    Raises:
        ValueError: If --phases or --stores names something unknown.
    """
    phases = [p.strip() for p in args.phases.split(',') if p.strip()]
    unknown = [p for p in phases if p not in PHASES]
    if unknown:
        raise ValueError(f'unknown phases {unknown}; choose from {list(PHASES)}')
    stores = run_stores(settings)
    compared = stores
    if args.stores:
        chosen = [s.strip() for s in args.stores.split(',') if s.strip()]
        bad = [s for s in chosen if s not in stores]
        if bad:
            raise ValueError(f'{bad} are not stores of this config; choose from {stores}')
        # the geolocation store is always opened, since the index and the
        # values are checked against it, but its own values are compared only
        # when it is named (finding 12: not again for every store added)
        compared = [s for s in stores if s in chosen]
        stores = [GEOLOCATION] + [s for s in compared if s != GEOLOCATION]

    LOG.info(f'phases: {phases}')
    # the stores this run verifies, which finalize reads as its evidence
    LOG.info(f'stores: {compared}')
    if compared != stores:
        LOG.info(f'opened besides, for the index and placement: {[s for s in stores if s not in compared]}')
    report = Report()
    chunks = resolve_chunks(settings)
    codecs = resolve_compression(settings)
    opened = open_groups(settings, stores)
    groups = {store: group for store, (_, group) in opened.items()}

    if 'structure' in phases:
        LOG.info('--- structure')
        for store, group in groups.items():
            check_structure(report, settings, store, group, chunks, codecs)

    granules, index = None, None
    if {'index', 'values'} & set(phases):
        reader = load_reader(settings)
        LOG.info(f'listing granules under {settings["directories"]["raw"]}')
        granules = reader.list_granules(
            settings['directories']['raw'],
            expected_empty=settings.get('expected_empty_granules') or [],
            expected_unreadable=settings.get('expected_unreadable_granules') or [],
            **listing_options(settings, reader),
        )
    if 'index' in phases or 'values' in phases:
        LOG.info('--- index')
        index = check_index(report, settings, groups, granules)

    if 'values' in phases:
        LOG.info('--- values')
        if report.failures:
            # a value comparison against a misaligned index would report
            # every observation; the index failures already say what is wrong
            report.check('values phase skipped: the index does not match raw', False)
        else:
            seen = check_values(
                report, settings, groups, compared, granules, index,
                settings.get('verify_num_workers', settings['num_workers']),
                settings.get('verify_granules_per_task', settings['granules_per_commit']),
            )
            LOG.info(
                f'geospatial bounds: lat [{seen.bounds[0]}, {seen.bounds[1]}] '
                f'lon [{seen.bounds[2]}, {seen.bounds[3]}]'
            )

    if 'repository' in phases:
        LOG.info('--- repository')
        check_repository(report, {store: repo for store, (repo, _) in opened.items()})

    log_peak_memory(LOG)
    LOG.info(f'{report.n_checks} checks, {len(report.failures)} failures')
    if report.failures:
        for label in report.failures:
            LOG.error(f'failed: {label}')
        return 1
    LOG.info('stores verified :-)')
    return 0


if __name__ == '__main__':
    arguments = parse_args()
    configuration = load_config(arguments.config)
    os.makedirs(configuration['directories']['logs'], exist_ok=True)
    # one log per config, beside the build's, so finalize reads the evidence
    # for exactly the stores this config names
    setup_logging(log_path(configuration, 'verify_'))
    sys.exit(main(configuration, arguments))
