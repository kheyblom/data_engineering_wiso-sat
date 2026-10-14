"""Verify the stores of one WISO-SAT Level 2 product against the raw files.

Reads the same config the build did, so it checks the stores that config names
and needs no paths of its own. Nothing here writes: every session is read
only.

**Every observation is checked, not a sample** (project rule, 2026-10-14). The
values phase makes one pass over every granule, as the build does, and compares
every value of every store with what the raw file says it should be.

**The raw side is read independently of the build.** The build reads with
netCDF4 through the product's reader; this reads with h5py, straight from the
source paths in the nomenclature key, with no masking and no CF decoding, and
applies the declared fill and the key's conversion itself. Only two
format facts are shared with the build, through the reader: how the product
encodes time (``decode_time``) and its swath layout (``check_granule``).
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
    granule's index entry (observation count, start and end time) against the
    file; time never decreasing; the processor version; the product's swath
    layout; every declared fill value occurring somewhere in the record; and no
    netCDF default fill surviving in a source that does not declare it.
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
    INDEX_FIELDS,
    check_coverage,
    check_order,
    decode_text,
)
from utils.log_utils import log_peak_memory, setup_logging
from utils.nomenclature import (
    canonical_frequency,
    conversion_factor,
    coordinates,
    variable as key_variable,
)
from utils.path_utils import (
    GEOLOCATION,
    format_version,
    load_config,
    load_reader,
    log_path,
    run_stores,
    store_path,
)
from utils.zarr_utils import (
    BRANCH,
    COMMIT_PREFIX,
    TIME_CALENDAR,
    TIME_EPOCH,
    absent_fill,
    declared_fill,
    open_existing_repository,
    resolve_chunks,
    store_sources,
    time_source,
    time_units,
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
        'to all of them; the geolocation store is always included, since the '
        'index check is against it.',
    )
    return parser.parse_args()


def to_epoch(values, unit):
    """datetime64 values as the int64 count the stores hold.

    Args:
        values (numpy.ndarray): datetime64, already in ``unit``.
        unit (str): numpy datetime64 unit code, from the key, e.g. 'ms'.

    Returns:
        numpy.ndarray: int64 ``unit`` since 1900-01-01.
    """
    return (values.astype(f'datetime64[{unit}]') - np.datetime64(TIME_EPOCH, unit)).astype('int64')


def read_expected(granule, reader_name, items, time, unit):
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

    Returns:
        list: Per file, a dict with ``path``, ``n_obs``, ``version``,
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
            out['version'] = str(decode_text(handle.attrs.get(reader.VERSION_ATTR, '')))
            out['n_obs'] = int(handle[time].shape[0])
            out['problems'] = reader.check_granule(handle)
            for source, fill, factor, absent in items:
                if source not in handle:
                    continue
                dataset = handle[source]
                raw = dataset[...]
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


def check_structure(report, settings, store, group, chunks):
    """Check one store's layout, encoding and attributes from metadata.

    Args:
        report (Report): Where to record outcomes.
        settings (dict): The loaded configuration.
        store (str): The store's variable slot.
        group (zarr.Group): Its root group.
        chunks (dict): The configured chunks.
    """
    product = settings['product']
    names = set(group.array_keys())
    expected_vars = set(store_sources(product, store))
    report.check(
        f'{store}: holds exactly its variables and the granule index',
        names == expected_vars | set(INDEX_FIELDS),
        f'{sorted(names)}',
    )

    for name in sorted(names & (expected_vars | set(INDEX_FIELDS))):
        array = group[name]
        dims = array.metadata.dimension_names or ()
        leading = 'obs' if name in expected_vars else GRANULE_DIM
        report.check(
            f'{store}/{name}: leading dimension {leading}, chunked {chunks[leading]}, '
            f'secondary dimensions whole',
            bool(dims) and dims[0] == leading
            and array.chunks == (chunks[leading],) + tuple(array.shape[1:]),
            f'{dims} {array.chunks}',
        )

    for name in sorted(expected_vars & names):
        array, attrs = group[name], dict(group[name].attrs)
        if name == 'time' or name.startswith('granule_time'):
            units = time_units(product)[0]
            report.check(
                f'{store}/{name}: int64 {units!r}, {TIME_CALENDAR}',
                str(array.dtype) == 'int64' and attrs.get('units') == units
                and attrs.get('calendar') == TIME_CALENDAR,
                f'{array.dtype} {attrs.get("units")!r} {attrs.get("calendar")!r}',
            )
            continue
        source = store_sources(product, store)[name]
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
            entry = coordinates(product)[name]
            report.check(
                f'{store}/{name}: units {entry.units!r}',
                attrs.get('units') == entry.units, f'{attrs.get("units")!r}',
            )
            continue
        entry = key_variable(product, name)
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
    frequency = canonical_frequency(product, settings['temporal_resolution'])
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
        f'.{format_version(settings["version"])}.{frequency}.' in stem
        and stem.endswith(f'.{store}.zarr'),
        stem,
    )


def read_index(group):
    """A store's granule index, undecoded.

    Args:
        group (zarr.Group): The store's root group.

    Returns:
        dict: Index field -> numpy array.
    """
    return {field: np.asarray(group[field][...]) for field in INDEX_FIELDS}


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
        missing = check_coverage(granules, settings)
        report.check('raw listing: unique granules, missing days as declared', True,
                     f'{len(granules)} granules, {len(missing)} declared missing days')
    except ValueError as error:
        report.check('raw listing: unique granules, missing days as declared', False, str(error))

    reference = read_index(groups[GEOLOCATION])
    for store, group in groups.items():
        index = read_index(group)
        report.check(
            f'{store}: granule index identical to the geolocation store',
            all(np.array_equal(index[field], reference[field]) for field in INDEX_FIELDS),
        )
        n_obs = group[next(iter(store_sources(settings['product'], store)))].shape[0]
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


class Pass:
    """Accumulates the values phase over every granule.

    Attributes:
        mismatches (dict): ``(store, name)`` -> mismatching values.
        fill (dict): Source -> values matching a declared fill.
        undeclared (dict): Source -> values matching an undeclared default fill.
        absent (dict): Source -> raw values equal to its declared absent fill.
        missing (dict): Source -> granules where no file holds it.
        problems (list): ``(granule id, problem)`` from the layout check.
        index (dict): Index field -> mismatching granules.
        placement (dict): Merge failures in multi-file granules, by kind.
        versions (set): Processor versions seen.
        bounds (list): ``[lat_min, lat_max, lon_min, lon_max]``.
        decreasing (int): Places where time decreases.
        dtypes (dict): Source -> dtypes seen.
        attrs (dict): Source -> the first granule's attributes.
    """

    def __init__(self):
        self.mismatches = {}
        self.fill = {}
        self.undeclared = {}
        self.absent = {}
        self.missing = {}
        self.problems = []
        self.index = {'granule_obs_count': 0, 'granule_time_start': 0, 'granule_time_end': 0}
        self.placement = {'unmatched': 0, 'reordered': 0, 'unaccounted': 0}
        self.versions = set()
        self.bounds = [np.inf, -np.inf, np.inf, -np.inf]
        self.decreasing = 0
        self.dtypes = {}
        self.attrs = {}


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


def check_values(report, settings, groups, granules, index, num_workers, batch):
    """Compare every value of every store with raw, one granule batch at a time.

    Args:
        report (Report): Where to record outcomes.
        settings (dict): The loaded configuration.
        groups (dict): Store -> zarr.Group.
        granules (list): The raw listing, which the index phase matched.
        index (dict): The geolocation store's index.
        num_workers (int): Read processes.
        batch (int): Granules per batch.

    Returns:
        Pass: What the pass saw, for the evidence lines.
    """
    product = settings['product']
    reader = load_reader(settings)
    time = time_source(product)
    _, unit = time_units(product)
    coordinate_names = {entry.original: name for name, entry in coordinates(product).items()}
    targets = []
    for store in groups:
        for name, source in store_sources(product, store).items():
            factor = None if store == GEOLOCATION else conversion_factor(
                key_variable(product, name).unit_conversion
            )
            targets.append((store, name, source, factor))
    items = sorted(
        {(source, tuple(declared_fill(settings, source)), factor, absent_fill(settings, source))
         for _, _, source, factor in targets},
        key=lambda item: item[0],
    )
    items = [(source, list(fill), factor, absent) for source, fill, factor, absent in items]
    match_sources = tuple(getattr(reader, 'MATCH_SOURCES', ()))
    starts = index['granule_obs_start']
    counts = index['granule_obs_count']
    stored_start = index['granule_time_start']
    stored_end = index['granule_time_end']

    seen = Pass()
    previous = None
    pool = (
        concurrent.futures.ProcessPoolExecutor(
            max_workers=num_workers, mp_context=multiprocessing.get_context('spawn')
        ) if num_workers > 1 else None
    )
    try:
        for begin in range(0, len(granules), batch):
            end = min(begin + batch, len(granules))
            chunk = granules[begin:end]
            arguments = (chunk, [product] * len(chunk), [items] * len(chunk),
                         [time] * len(chunk), [unit] * len(chunk))
            results = list((pool.map if pool else map)(read_expected, *arguments))
            obs0 = int(starts[begin])
            obs1 = int(starts[end - 1] + counts[end - 1])
            stored = {
                (store, name): np.asarray(groups[store][name][obs0:obs1])
                for store, name, _, _ in targets
            }
            for offset, (granule, files) in enumerate(zip(chunk, results)):
                position = begin + offset
                lo = int(starts[position]) - obs0
                hi = lo + int(counts[position])
                for entry in files:
                    seen.versions.add(entry['version'])
                    seen.problems += [(granule.id, problem) for problem in entry['problems']]

                # how many observations the granule should hold: every
                # distinct one across its files, found from raw alone
                if len(files) == 1:
                    n_expected = files[0]['n_obs']
                else:
                    n_expected = len(set().union(*(
                        observation_keys([entry['sources'][s]['expected'] for s in match_sources])
                        for entry in files
                    )))
                if n_expected != int(counts[position]):
                    seen.index['granule_obs_count'] += 1
                    continue

                stored_time = stored[(GEOLOCATION, 'time')][lo:hi]
                if stored_time.size:
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

                stored_keys = (
                    observation_keys([
                        stored[(GEOLOCATION, coordinate_names[source])][lo:hi]
                        for source in match_sources
                    ]) if len(files) > 1 else None
                )
                placed = place_files(files, stored_keys, match_sources, seen)

                for store, name, source, _ in targets:
                    key = (store, name)
                    values = stored[key][lo:hi]
                    covered = np.zeros(values.shape[0], dtype=bool)
                    holders = 0
                    for entry, positions in zip(files, placed):
                        if source not in entry['sources'] or positions is None:
                            continue
                        holders += 1
                        found = entry['sources'][source]
                        seen.mismatches[key] = seen.mismatches.get(key, 0) + same_values(
                            values[positions], found['expected']
                        )
                        covered[positions] = True
                        seen.dtypes.setdefault(source, set()).add(found['dtype'])
                        seen.attrs.setdefault(source, found['attrs'])
                    if not holders:
                        seen.missing[source] = seen.missing.get(source, 0) + 1
                        continue
                    # where no file holds the observation, the store must say
                    # so: NaN, or the declared absent fill for an integer
                    rest = values[~covered]
                    if rest.size:
                        if rest.dtype.kind == 'f':
                            wrong = int((~np.isnan(rest)).sum())
                        else:
                            wrong = int((rest != absent_fill(settings, source)).sum())
                        seen.mismatches[key] = seen.mismatches.get(key, 0) + wrong

                for entry in files:
                    for source, found in entry['sources'].items():
                        seen.fill[source] = seen.fill.get(source, 0) + found['fill']
                        seen.undeclared[source] = seen.undeclared.get(source, 0) + found['undeclared']
                        seen.absent[source] = seen.absent.get(source, 0) + found['absent']
                    for name, low, high in (('lat', 0, 1), ('lon', 2, 3)):
                        values = entry['sources'][coordinates(product)[name].original]['expected']
                        finite = values[np.isfinite(values)]
                        if finite.size:
                            seen.bounds[low] = min(seen.bounds[low], float(finite.min()))
                            seen.bounds[high] = max(seen.bounds[high], float(finite.max()))
            LOG.info(f'checked granules {begin}-{end - 1} of {len(granules)}')
    finally:
        if pool is not None:
            pool.shutdown()

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
    report.check(
        'time never decreases along obs', seen.decreasing == 0, f'{seen.decreasing} decreases'
    )
    report.check(
        'every file has the documented layout', not seen.problems,
        f'{len(seen.problems)} problems, first {seen.problems[:3]}',
    )
    for source, fill, _, absent in items:
        report.check(
            f'{source}: held by a file of every granule',
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
        report.check(
            f'{source}: one dtype across the record',
            len(seen.dtypes.get(source, ())) == 1, f'{sorted(seen.dtypes.get(source, ()))}',
        )

    # attributes against the first granule: a source standard_name is
    # retained unchanged, and none is ever added
    for store, name, source, _ in targets:
        stored_attrs = dict(groups[store][name].attrs)
        raw = seen.attrs.get(source, {}).get('standard_name')
        report.check(
            f'{store}/{name}: standard_name is the source one, or absent with it',
            stored_attrs.get('standard_name') == raw,
            f'{stored_attrs.get("standard_name")!r} against source {raw!r}',
        )
        if store != GEOLOCATION:
            report.check(
                f'{store}/{name}: dtype is the source dtype',
                str(groups[store][name].dtype) in seen.dtypes.get(source, set()),
                f'{groups[store][name].dtype} against {sorted(seen.dtypes.get(source, ()))}',
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
    if args.stores:
        chosen = [s.strip() for s in args.stores.split(',') if s.strip()]
        bad = [s for s in chosen if s not in stores]
        if bad:
            raise ValueError(f'{bad} are not stores of this config; choose from {stores}')
        stores = [GEOLOCATION] + [s for s in chosen if s != GEOLOCATION]

    LOG.info(f'phases: {phases}')
    LOG.info(f'stores: {stores}')
    report = Report()
    chunks = resolve_chunks(settings)
    opened = open_groups(settings, stores)
    groups = {store: group for store, (_, group) in opened.items()}

    if 'structure' in phases:
        LOG.info('--- structure')
        for store, group in groups.items():
            check_structure(report, settings, store, group, chunks)

    granules, index = None, None
    if {'index', 'values'} & set(phases):
        reader = load_reader(settings)
        LOG.info(f'listing granules under {settings["directories"]["raw"]}')
        granules = reader.list_granules(
            settings['directories']['raw'], settings.get('expected_empty_granules') or []
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
                report, settings, groups, granules, index,
                settings.get('verify_num_workers', settings['num_workers']),
                settings['granules_per_commit'],
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
