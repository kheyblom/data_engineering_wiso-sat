"""Build the spatial gridded stores of one product from its finalized L2 stores.

    uv run python grid_wisosat.py --config config/<product>/config_grid.yaml

One pass over the UTC days of the record writes every grid and every
frequency the config lists (``grids`` x ``frequencies``), each grid made
straight from L2 (user decision 2026-11-09: never a coarse grid from a fine
one). Each day is read once, in a ``spawn`` process pool, and gridded onto
every grid that still needs it; its sums go into the open period of each
frequency, and a period's statistics are formed only when it closes
(gridding-method.md, Section 8: sums add over days, statistics do not).

Two methods, by the config's ``method``: ``column`` (the default; δD, σ and
the H2O column are L2 variables, the footprint the L2 corners: TROPOMI) and
``profile`` (they are derived here from L2 profiles, per column, per level
and at the surface, and the footprint is drawn by a model: AIRS). The
config's gridding key (``quantity_key``) lists the stores each builds.

Writes are append commits of ``periods_per_commit`` periods to each store
of a (grid, frequency), one icechunk repository per variable
(``utils/stores.py``). A build resumes: each store's stored ``time_bounds``
must be a prefix of the periods the config implies, all 17 stores of a
(grid, frequency) must agree, and the pass restarts at the earliest period
still missing. Rerunning a complete set is a no-op.

Guards, before anything is written:
- gridding/ is committed (``check_clean_tree``), and every commit is
  stamped ``@ <revision>``;
- every quantity and frequency has its nomenclature_data.md row;
- every L2 store read holds the config's tag, its inputs carry the key's
  units, and a resumed store was built from the same L2 snapshots.
"""
import argparse
import collections
import concurrent.futures
import logging
import multiprocessing
import os
import time

import numpy as np

from utils import config, footprints, l2 as l2_utils, nomenclature, periods, profiles, stores, sums
from utils.config import GEOLOCATION
from utils.grids import from_spec

LOG = logging.getLogger('grid_wisosat')
ATTR_SOURCE_SNAPSHOTS = 'source_l2_snapshots'
METHODS = ('column', 'profile')
# the L2 fields each footprint model draws a polygon from (the config's ``footprint`` block)
FOOTPRINT_FIELDS = {'corners': (), 'airs_fov': ('granule', 'scanline', 'pixel', 'view_angle')}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--config', required=True)
    return parser.parse_args()


# ------------------------------------------------------------------ planning

Target = collections.namedtuple('Target', 'grid frequency bounds paths')


def l2_stores(settings, product):
    """Every L2 store a build reads: geolocation, the inputs, the footprint fields, the selection, the thresholds."""
    inputs = [store for name, store in settings['inputs'].items() if name != 'footprint']
    selection = settings['selection']
    names = [GEOLOCATION, *inputs, *l2_utils.footprint_stores(settings), *product.selection_stores(selection),
             *(selection.get('thresholds') or {})]
    return list(dict.fromkeys(names))


def check_inputs(settings, l2, product):
    """The method, key and footprint model agree, and each input carries the key's units."""
    method = settings.get('method', 'column')
    if method not in METHODS:
        raise ValueError(f'method must be one of {METHODS}, got {method!r}')
    if nomenclature.has_levels() != (method == 'profile'):
        raise ValueError(f'method {method!r} does not match the gridding key {nomenclature.key_path().name}: '
                         f'only the profile method grids a level group')
    if method == 'profile':
        missing = [key for key in ('ratio_standard', 'column', 'levels') if key not in (settings.get('profile') or {})]
        if missing:
            raise ValueError(f'the profile method needs profile.{missing}')
    model = settings['inputs'].get('footprint')
    if model not in getattr(product, 'FOOTPRINT_MODELS', ()) or model not in FOOTPRINT_FIELDS:
        raise ValueError(f'footprint model {model!r} is not supported for {settings["product"]}')
    if set(settings.get('footprint') or {}) != set(FOOTPRINT_FIELDS[model]):
        raise ValueError(f'footprint model {model!r} needs the config\'s footprint block to name exactly '
                         f'{FOOTPRINT_FIELDS[model]}')
    if (method == 'profile') != (model == 'airs_fov'):
        raise ValueError(f'method {method!r} with footprint model {model!r} is not built')
    for name, units in nomenclature.input_units().items():
        store = settings['inputs'].get(name)
        if store is None:
            raise ValueError(f'inputs.{name} is not set')
        if l2.units(store) != units:
            raise ValueError(f'inputs.{name}: L2 {store} has units {l2.units(store)!r}, the method needs {units!r}')


def record_range(settings, l2):
    """The first and last day to grid: the L2 record, narrowed by the config's ``period``."""
    first, last = l2.record_days()
    limit = settings.get('period') or {}
    if limit.get('start'):
        first = max(first, periods.day_number(limit['start']))
    if limit.get('end'):
        last = min(last, periods.day_number(limit['end']))
    if last < first:
        raise ValueError(f'nothing to grid: period {limit} lies outside the L2 record')
    return first, last


def targets(settings, first, last):
    """One target per (grid, frequency): its periods and its 17 store paths."""
    out = []
    for spec in settings['grids']:
        grid = from_spec(spec)
        for frequency in settings['frequencies']:
            bounds = periods.periods(first, last, frequency)
            paths = {quantity: config.store_path(settings, 'spatial', frequency, grid.name, row['canonical_name'])
                     for quantity, row in nomenclature.quantities().items()}
            out.append(Target(grid, frequency, bounds, paths))
    return out


def resume_state(target, snapshots):
    """How many periods a target's stores already hold, after checking they agree.

    Raises:
        RuntimeError: If the stores disagree, hold periods the config does
            not imply, or were built from other L2 snapshots.
    """
    lengths = {}
    for quantity, path in target.paths.items():
        if not os.path.isdir(path):
            lengths[quantity] = 0
            continue
        repository = stores.open_repository(path)
        stored = stores.stored_times(repository)
        n = len(stored)
        if n > len(target.bounds) or not np.array_equal(stored, target.bounds[:n]):
            raise RuntimeError(f'{path}: its periods are not a prefix of the config\'s; delete it to rebuild')
        if n:
            import zarr  # type: ignore
            group = zarr.open_group(repository.readonly_session(branch=stores.BRANCH).store, mode='r')
            if group.attrs.get(ATTR_SOURCE_SNAPSHOTS) != snapshots:
                raise RuntimeError(f'{path} was built from other L2 snapshots; delete it to rebuild')
        lengths[quantity] = n
    if len(set(lengths.values())) > 1:
        raise RuntimeError(f'{target.grid.name} {target.frequency}: stores hold different numbers of '
                           f'periods {sorted(set(lengths.values()))}; an interrupted commit? Rewind them to agree')
    return next(iter(lengths.values()))


def global_attrs(settings, grid, frequency, layout, snapshots, quantity):
    """A store's global attributes at build time (finalize adds history, verification, coverage)."""
    row = nomenclature.quantities()[quantity]
    fields = {
        'product': settings['product'], 'version': config.gridded_version_token(settings),
        'version_label': str(settings['version']), 'frequency': frequency, 'grid_name': grid.name,
        'variable': row['canonical_name'], 'long_name': nomenclature.authority_attrs(settings, quantity)['long_name'],
        'frequency_long_name': nomenclature.frequency_long_name(settings, frequency),
    }
    attrs = {key: str(value).format(**fields).strip() for key, value in settings['attrs'].items()}
    chunks = stores.store_chunks(settings, grid, quantity, layout)
    chunk_dims = '(time, level, rows, cols)' if stores.has_level(quantity) else '(time, rows, cols)'
    other = 'temporal' if layout == 'spatial' else 'spatial'
    attrs.update({
        'cdm_data_type': 'Grid',
        'temporal_frequency': frequency,
        'temporal_frequency_long_name': fields['frequency_long_name'],
        'time_coverage_resolution': periods.coverage_resolution(frequency),
        'period_anchor': ('periods are consecutive blocks counted from 1900-01-01; n-month periods start '
                          'in January'),
        'grid_name': grid.name,
        'grid': _grid_description(grid),
        'geospatial_lat_min': float(grid.lat_edges.min()), 'geospatial_lat_max': float(grid.lat_edges.max()),
        'geospatial_lon_min': -180.0, 'geospatial_lon_max': 180.0,
        'layout': (f'{layout}: chunks {chunk_dims} = {chunks}' if layout == 'spatial' else
                   f'{layout}: the whole record in each chunk of a tile of cells'),
        'related_store': config.store_path(settings, other, frequency, grid.name, row['canonical_name']),
        'gridding_method': 'docs/technical/gridding-method.md (data_engineering_wiso-sat)',
        'gridding_inputs': _inputs_text(settings),
        'gridding_selection': _selection_text(settings),
        'gridding_quantity': f'{quantity}: {row["formula"]} ({row["kind"]})',
        'empty_cells': ('statistics are NaN, sums are 0 and observation_count is 0 where no footprint '
                        'touched the cell'),
        'source_l2_tag': config.l2_tag_text(settings),
        ATTR_SOURCE_SNAPSHOTS: snapshots,
        'source_l2_stores': settings['l2']['directory'],
    })
    return attrs


def _inputs_text(settings):
    """The inputs, and for the profile method what is derived from them and how."""
    parts = [f'{name}: {value}' for name, value in settings['inputs'].items()]
    parts += [f'footprint {name}: {store}' for name, store in (settings.get('footprint') or {}).items()]
    text = '; '.join(parts)
    spec = settings.get('profile')
    if not spec:
        return text
    return (f'{text}. Derived in gridding from the profiles (L2 holds only published values): delta D against '
            f'the standard ratio {spec["ratio_standard"]:g}; the column between {spec["column"]["bottom"]:g} and '
            f'{spec["column"]["top"]:g} Pa (or the surface where it is higher) with H2O and HDO each linear in '
            f'ln p and exact cuts; H2O partial columns as the integral of the dry-air mole fraction over pressure '
            f'with g = 9.80665 m s-2 and a dry-air molar mass of 28.9644 g mol-1')


def _grid_description(grid):
    if grid.kind == 'latlon':
        return (f'regular global latitude-longitude grid, {grid.size} degree cells, {grid.shape[0]} x '
                f'{grid.shape[1]} (lat x lon), rows north to south')
    return (f'EASE-Grid 2.0 global {grid.nsidc_name} (EPSG:6933), cell side {grid.size} m, {grid.shape[0]} x '
            f'{grid.shape[1]} (rows x cols), row 0 north, latitudes {grid.lat_edges[-1]:.2f} to '
            f'{grid.lat_edges[0]:.2f}')


def _selection_text(settings):
    selection = settings['selection']
    parts = [f'quality_level {selection.get("quality_level")}']
    for store, bounds in (selection.get('thresholds') or {}).items():
        for key, symbol in (('min', '>='), ('max', '<=')):
            if key in bounds:
                parts.append(f'{store} {symbol} {bounds[key]:g}')
    parts.append('every input must hold a value; footprints with a missing corner or that enclose a pole '
                 'are not gridded')
    text = '; '.join(parts)
    note = selection.get('description')
    return f'{text}. {note.strip()}' if note else text


# --------------------------------------------------------------- the workers

_WORKER = {}


def _init_worker(config_path):
    """Per process: the config, the L2 stores and the grids, opened once."""
    settings = config.load_config(config_path)
    _WORKER.update(settings=settings, l2=l2_utils.L2(settings), product=config.source_module(settings),
                   grids={from_spec(spec).name: from_spec(spec) for spec in settings['grids']})
    if settings['inputs'].get('footprint') == 'airs_fov':
        _WORKER['phases'] = l2_utils.AirsPhases(_WORKER['l2'], settings['footprint'])


def grid_day(day, grid_names):
    """Read one UTC day and grid it onto each named grid.

    Returns:
        tuple: ``(day, results, counts)``; ``results`` maps grid name ->
            ``(cells, count, sums)`` from ``sums.day_sums``, and for the
            profile method ``sums.profile_sums`` as a fourth item.
    """
    settings, l2 = _WORKER['settings'], _WORKER['l2']
    if settings.get('method', 'column') == 'profile':
        return _grid_profile_day(day, grid_names)
    values, counts = l2_utils.read_day(l2, day, settings, _WORKER['product'])
    lat, lon, usable = footprints.unwrap(values['lat_corners'], values['lon_corners'])
    counts['not_griddable'] = int((~usable).sum())
    lat, lon = lat[usable], lon[usable]
    inputs = {name: values[name][usable].astype('float64') for name in ('delta_d', 'delta_d_uncertainty', 'weight')}
    area = footprints.footprint_area_km2(lat, lon)
    counts['gridded'] = int(usable.sum())
    results = {}
    for name in grid_names:
        footprint, cell, km2 = footprints.overlaps(lat, lon, _WORKER['grids'][name],
                                                   int(settings.get('max_pairs', 500_000)))
        results[name] = sums.day_sums(footprint, cell, km2, inputs['delta_d'], inputs['delta_d_uncertainty'],
                                      inputs['weight'], area)
    return day, results, counts


def _grid_profile_day(day, grid_names):
    """``grid_day`` for the profile method.

    A retrieval is gridded only if it has the config's column (a δD and an
    H2O partial column between the two pressures): one without is counted
    as missing an input and enters no group, so the three groups describe
    the same retrievals. Within a gridded retrieval, a level or the surface
    counts where its own values are all written.
    """
    settings, l2 = _WORKER['settings'], _WORKER['l2']
    values, counts = l2_utils.read_profile_day(l2, day, settings, _WORKER['product'], _WORKER['phases'])
    derived = profiles.derive(values, settings['profile'])
    has_column = np.isfinite(derived['delta_d']) & np.isfinite(derived['h2o'])
    counts['missing_input'] = int((~has_column).sum())
    lat, lon, usable = footprints.unwrap(values['lat_corners'], values['lon_corners'])
    counts['not_griddable'] = int((has_column & ~usable).sum())
    keep = has_column & usable
    lat, lon = lat[keep], lon[keep]
    derived = {name: array[keep] for name, array in derived.items()}
    area = footprints.footprint_area_km2(lat, lon)
    counts['gridded'] = int(keep.sum())
    results = {}
    for name in grid_names:
        grid = _WORKER['grids'][name]
        footprint, cell, km2 = footprints.overlaps(lat, lon, grid, int(settings.get('max_pairs', 500_000)))
        column = sums.day_sums(footprint, cell, km2, derived['delta_d'], None, derived['h2o'], area)
        results[name] = (*column, sums.profile_sums(footprint, cell, km2, derived, grid.n_cells))
    return day, results, counts


# ------------------------------------------------------------------ the pass

class Writer:
    """The open period of one target, and the closed periods waiting for a commit."""

    def __init__(self, settings, target, done, snapshots, revision):
        self.settings, self.target, self.revision = settings, target, revision
        self.k = done
        n_levels = len(settings['profile']['levels']) if nomenclature.has_levels() else 0
        self.accumulator = sums.Accumulator(target.grid.n_cells, n_levels) if done < len(target.bounds) else None
        self.buffer = []
        self.attrs = {quantity: global_attrs(settings, target.grid, target.frequency, 'spatial', snapshots, quantity)
                      for quantity in target.paths}
        self.per_commit = int(settings.get('periods_per_commit', 10))
        time_chunk = stores.layout_chunks(settings, target.grid, 'spatial')[0]
        if self.per_commit % time_chunk:
            # correct, but each commit then rewrites a partly filled chunk (as extending the
            # record later does once); production configs align them
            LOG.warning(f'periods_per_commit ({self.per_commit}) is not a multiple of the spatial time '
                        f'chunk ({time_chunk}): commits rewrite partly filled chunks')
        self.area = target.grid.row_area_km2()[np.arange(target.grid.n_cells) // target.grid.shape[1]]

    @property
    def finished(self):
        return self.k >= len(self.target.bounds)

    def needs(self, day):
        return not self.finished and day >= self.target.bounds[self.k][0]

    def add(self, day, result, last_day):
        """Add a day; close the period at its last day (or at the record's), commit when the buffer is full."""
        if not self.needs(day):
            return
        self.accumulator.add(*result)
        start, end = self.target.bounds[self.k]
        if day == end - 1 or day == last_day:
            self._close()

    def _close(self):
        acc = self.accumulator
        shape = self.target.grid.shape
        # (cells,) or (levels, cells) -> (..., rows, cols), in each store's dtype
        fields = {name: values.reshape(*values.shape[:-1], *shape).astype(nomenclature.quantities()[name]['dtype'])
                  for name, values in sums.fields(acc, self.area).items()}
        occupied = int((acc.count > 0).sum())
        start, end = self.target.bounds[self.k]
        LOG.info(f'{self.target.grid.name} {self.target.frequency} period {periods.day_date(start)}..'
                 f'{periods.day_date(end - 1)}: {acc.days} day(s) read, {occupied:,} occupied cells')
        self.buffer.append(fields)
        self.k += 1
        acc.reset()
        if len(self.buffer) >= self.per_commit or self.finished:
            self.flush()

    def flush(self):
        if not self.buffer:
            return
        n = len(self.buffer)
        first_index = self.k - n
        bounds = self.target.bounds[first_index:self.k]
        message = stores.APPEND_MESSAGE.format(first=periods.day_date(bounds[0][0]),
                                               last=periods.day_date(bounds[-1][1] - 1), count=n,
                                               revision=self.revision)
        started = time.time()
        for quantity, path in self.target.paths.items():
            data = np.stack([fields[quantity] for fields in self.buffer])
            first = first_index == 0
            ds = stores.dataset(self.settings, self.target.grid, quantity, data, bounds, self.attrs[quantity],
                                static=first)
            enc = stores.encoding(self.settings, self.target.grid, quantity, 'spatial') if first else None
            repository = stores.open_repository(path, create=first)
            stores.write_append(repository, ds, enc, first, message)
        LOG.info(f'{self.target.grid.name} {self.target.frequency}: committed {message!r} to '
                 f'{len(self.target.paths)} stores in {time.time() - started:.1f} s')
        self.buffer = []


def run(settings):
    """The whole build: guards, plan, one pass over the days."""
    revision = config.check_clean_tree(settings)
    nomenclature.check(settings, settings['frequencies'])
    product = config.source_module(settings)
    l2 = l2_utils.L2(settings)
    check_inputs(settings, l2, product)
    read = l2_stores(settings, product)
    snapshots = '; '.join(f'{store}={snapshot}' for store, snapshot in l2.provenance(read).items())
    first_day, last_day = record_range(settings, l2)
    LOG.info(f'{settings["product"]} L2 at tag {settings["l2"]["tag"]}: days {periods.day_date(first_day)}..'
             f'{periods.day_date(last_day)}; revision {revision}')
    writers = []
    for target in targets(settings, first_day, last_day):
        done = resume_state(target, snapshots)
        LOG.info(f'{target.grid.name} {target.frequency}: {done} of {len(target.bounds)} periods stored')
        writers.append(Writer(settings, target, done, snapshots, revision))
    pending = [writer for writer in writers if not writer.finished]
    if not pending:
        LOG.info('every store is complete; nothing to do')
        return
    start_day = min(int(writer.target.bounds[writer.k][0]) for writer in pending)
    days = list(range(start_day, last_day + 1))
    num_workers = int(settings.get('num_workers', 0))
    LOG.info(f'gridding {len(days)} day(s) from {periods.day_date(start_day)} with {num_workers or "no"} '
             f'worker process(es)')
    started = time.time()
    for day, results, counts in _results(settings, days, writers, num_workers):
        for writer in writers:
            if writer.needs(day):
                writer.add(day, results[writer.target.grid.name], last_day)
        LOG.info(f'{periods.day_date(day)}: {counts["rows"]:,} rows, {counts["quality"]:,} pass quality, '
                 f'{counts["over_threshold"]:,} over a threshold, {counts["missing_input"]:,} missing an input, '
                 f'{counts["not_griddable"]:,} not griddable, {counts["gridded"]:,} gridded')
    for writer in writers:
        writer.flush()
    LOG.info(f'build complete in {(time.time() - started) / 60:.1f} min')


def _results(settings, days, writers, num_workers):
    """Each day's ``grid_day``, in day order; at most ``2 * num_workers`` in flight."""
    def needed(day):
        return sorted({writer.target.grid.name for writer in writers if writer.needs(day)})

    if num_workers == 0:
        _init_worker(settings['config_path'])
        for day in days:
            yield grid_day(day, needed(day))
        return
    context = multiprocessing.get_context('spawn')
    with concurrent.futures.ProcessPoolExecutor(num_workers, mp_context=context, initializer=_init_worker,
                                                initargs=(settings['config_path'],)) as pool:
        queue = collections.deque()
        iterator = iter(days)
        for day in iterator:
            # asked when submitted, ahead of the writers: a writer only moves on, so a grid
            # needed now is still needed when the day comes back (or its writer has finished)
            queue.append(pool.submit(grid_day, day, needed(day)))
            if len(queue) >= 2 * num_workers:
                break
        while queue:
            yield queue.popleft().result()
            for day in iterator:
                queue.append(pool.submit(grid_day, day, needed(day)))
                break


def main():
    args = parse_args()
    settings = config.load_config(args.config)
    config.setup_logging(settings)
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    run(settings)


if __name__ == '__main__':
    main()
