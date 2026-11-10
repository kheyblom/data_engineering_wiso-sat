"""Verify the gridded stores of one config, read only.

    uv run python verify_grid_wisosat.py --config config/<product>/config_grid.yaml --layout spatial
    uv run python verify_grid_wisosat.py --config ... --layout temporal

**Sampled, by decision** (user, 2026-11-10): gridding is an approved
exception to the project rule that verification covers every observation.
Every store's structure is checked in full; values are checked on samples.

Phases:
- ``structure`` (every store): dims, dtype, chunks and fill as the config
  and the key say; the grid's coordinates against an independent
  computation (pyproj for EASE-Grid 2.0); ``time_bounds`` against periods
  worked out independently with pandas; the 17 stores of a target agree;
  required attributes; ``source_l2_snapshots`` equals what the L2 tag names
  today.
- ``samples`` (spatial): for sampled periods of each (grid, frequency) --
  the first, the last and ``verify.samples`` more drawn with
  ``verify.seed`` -- every cell is recomputed from L2 by code independent of
  the build: its own L2 read, its own selection, footprint geometry and
  clipping by shapely, projection by pyproj, sums by pandas. Occupied cells
  and counts must match exactly, sums to ``SUM_RTOL``, statistics to float32
  rounding.
- ``samples`` (temporal): sampled tiles x sampled periods compared bit for
  bit with the spatial store at ``temporal.source_tag``, which it was made
  from.

The log ends with ``N checks, M failures`` and, on success, ``stores
verified``; ``finalize_grid_wisosat.py --attrs`` reads that.
"""
import argparse
import logging
import os
import sys

import icechunk  # type: ignore
import numpy as np
import pandas as pd
import pyproj  # type: ignore
import shapely  # type: ignore
import zarr  # type: ignore

from utils import config, nomenclature
from utils.grids import from_spec

LOG = logging.getLogger('verify_grid_wisosat')
PHASES = ('structure', 'samples')
REQUIRED_ATTRS = ('title', 'summary', 'Conventions', 'source', 'cdm_data_type', 'temporal_frequency', 'grid_name',
                  'gridding_method', 'gridding_selection', 'source_l2_tag', 'source_l2_snapshots')
PASSED = 'stores verified'
SUM_RTOL = 1e-9
# float32 statistics against float64 recomputed: rounding, and the spread's
# cancellation where one footprint fills a cell (true value 0)
STAT_RTOL = 2e-5
STAT_ATOL = {'spread': 1e-3, 'standard_error': 1e-6}
EARTH_KM = 6371.0
EPSG_6933 = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:6933', always_xy=True)
EPSG_6933_INVERSE = pyproj.Transformer.from_crs('EPSG:6933', 'EPSG:4326', always_xy=True)

icechunk.set_logs_filter('error')


class Report:
    """Counts checks and failures, logging each failure."""

    def __init__(self):
        self.checks = self.failures = 0

    def check(self, ok, what):
        self.checks += 1
        if not ok:
            self.failures += 1
            LOG.error(f'FAIL {what}')
        return ok


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--config', required=True)
    parser.add_argument('--layout', choices=('spatial', 'temporal'), required=True)
    parser.add_argument('--phases', default=','.join(PHASES))
    return parser.parse_args()


# ------------------------------------------------- independent expectations

def expected_periods(first, last, frequency):
    """Periods by pandas, independently of utils/periods.py: day numbers since 1900-01-01."""
    epoch = pd.Timestamp('1900-01-01')
    unit = 'month' if frequency.endswith('month') else 'day'
    n = int(frequency[:-len(unit)] or 1)
    first_date, last_date = epoch + pd.Timedelta(days=first), epoch + pd.Timedelta(days=last)
    if unit == 'day':
        start = epoch + pd.Timedelta(days=(first // n) * n)
        starts = pd.date_range(start, last_date, freq=f'{n}D')
        ends = starts + pd.Timedelta(days=n)
    else:
        months = (first_date.year - 1900) * 12 + first_date.month - 1
        block = (months // n) * n
        start = pd.Timestamp(year=1900 + block // 12, month=block % 12 + 1, day=1)
        starts = pd.date_range(start, last_date, freq=f'{n}MS')
        ends = starts + pd.DateOffset(months=n)
    days = lambda stamps: ((stamps - epoch) // pd.Timedelta(days=1)).to_numpy().astype('int64')  # noqa: E731
    return np.stack([days(starts), days(ends)], axis=1)


def expected_coords(grid):
    """Cell centres, edges and areas computed independently of utils/grids.py."""
    rows, cols = grid.shape
    if grid.kind == 'latlon':
        size = 180 / rows
        lat_edges = np.linspace(90, -90, rows + 1)
        lon_edges = np.linspace(-180, 180, cols + 1)
        area = EARTH_KM**2 * np.deg2rad(size) * (np.sin(np.deg2rad(lat_edges[:-1])) - np.sin(np.deg2rad(lat_edges[1:])))
        return {'lat': (lat_edges[:-1] + lat_edges[1:]) / 2, 'lon': (lon_edges[:-1] + lon_edges[1:]) / 2,
                'cell_area': area}
    size = grid.size
    x = (np.arange(cols) - cols / 2 + 0.5) * size
    y = (rows / 2 - np.arange(rows) - 0.5) * size
    lon, _ = EPSG_6933_INVERSE.transform(x, np.zeros(cols))
    _, lat = EPSG_6933_INVERSE.transform(np.zeros(rows), y)
    return {'lat': lat, 'lon': lon, 'x': x, 'y': y, 'cell_area': np.full(rows, (size / 1000) ** 2)}


# ----------------------------------------------- independent L2 and selection

class IndependentL2:
    """Reads a day straight from the L2 zarr arrays, without utils/l2.py."""

    def __init__(self, settings):
        self.settings = settings
        self.groups = {}

    def group(self, store):
        if store not in self.groups:
            repository = icechunk.Repository.open(icechunk.local_filesystem_storage(config.l2_store_path(self.settings, store)))
            self.groups[store] = zarr.open_group(repository.readonly_session(tag=self.settings['l2']['tag']).store, mode='r')
        return self.groups[store]

    def snapshots(self, stores):
        out = []
        for store in stores:
            repository = icechunk.Repository.open(icechunk.local_filesystem_storage(config.l2_store_path(self.settings, store)))
            out.append(f'{store}={repository.lookup_tag(self.settings["l2"]["tag"])}')
        return '; '.join(out)

    def day(self, day, stores, keep=None):
        """Every row whose time falls on the day, with the named stores' values.

        Float stores keep their stored dtype, so every threshold is compared at
        the stored precision, as the published values mean it: a float32 0.3
        is 0.3, not 0.300000012 (TROPOMI T24). Integer stores become float64
        with their fill as NaN, which is exact.

        Read one geolocation chunk at a time, and only the rows ``keep``
        accepts are held, so memory follows the selected rows rather than
        the ~12 M rows of a TROPOMI day.
        """
        geo = self.group(config.GEOLOCATION)
        units = geo['time'].attrs['units'].split(' since ')[0]
        per_day = pd.Timedelta(days=1) / pd.Timedelta(1, unit={'milliseconds': 'ms', 'seconds': 's',
                                                                  'microseconds': 'us', 'nanoseconds': 'ns'}[units])
        begin, end = day * per_day, (day + 1) * per_day
        index = pd.DataFrame({name: geo[f'granule_{name}'][:] for name in ('obs_start', 'obs_count', 'time_start', 'time_end')})
        index = index[(index.obs_count > 0) & (index.time_end >= begin) & (index.time_start < end)]
        if index.empty:
            return None
        first, stop = int(index.obs_start.min()), int((index.obs_start + index.obs_count).max())
        step = geo['time'].chunks[0]
        parts = []
        for edge in range(first - first % step, stop, step):
            window = slice(max(edge, first), min(edge + step, stop))
            time = geo['time'][window]
            rows = np.flatnonzero((time >= begin) & (time < end))
            if rows.size == 0:
                continue
            frame = {}
            for store in stores:
                array = self.group(store)[store]
                values = array[window][rows]
                if np.issubdtype(array.dtype, np.integer):
                    fill = array.attrs.get('_FillValue')
                    values = values.astype('float64')
                    if fill is not None:
                        values[values == fill] = np.nan
                frame[store] = values
            chosen = np.ones(rows.size, dtype=bool) if keep is None else keep(frame)
            rows = rows[chosen]
            frame = {store: values[chosen] for store, values in frame.items()}
            frame['lat_corners'] = geo['lat_corners'][window][rows]
            frame['lon_corners'] = geo['lon_corners'][window][rows]
            parts.append(frame)
        if not parts:
            return None
        return {name: np.concatenate([part[name] for part in parts]) for name in parts[0]}


def tropomi_passes(v, level):
    """Schneider et al. (2022) Table 1, written again for the verifier (integer fill is NaN here)."""
    with np.errstate(invalid='ignore', divide='ignore'):
        ok = v['quality_flags_retrieval'] == 0
        if level == 'success':
            return ok
        ok = ok & (v['iterations_retrieval'] >= 0) & (v['iterations_retrieval'] <= 10)
        ok = ok & (v['spectral_point_count_retrieval'] > 0) & (v['spectral_point_count_prefit'] > 0)
        ok = ok & (v['chi_squared_retrieval'] <= 150 * v['spectral_point_count_retrieval'])
        ok = ok & (v['chi_squared_prefit'] <= 150 * v['spectral_point_count_prefit'])
        ok = ok & (v['solar_zenith_angle'] <= 70)
        tau, albedo = v['optical_thickness_scattering_layer'], v['albedo_surface_2365nm']
        clear = (tau < 0.3) & (albedo >= 0.02)
        if level == 'clear':
            return ok & clear
        return ok & (clear | ((v['height_scattering_layer'] <= 2000) & (tau > 0.3)))


SELECTIONS = {'tropomi': (tropomi_passes, {
    'success': ['quality_flags_retrieval'],
    'clear': ['quality_flags_retrieval', 'iterations_retrieval', 'spectral_point_count_retrieval',
              'spectral_point_count_prefit', 'chi_squared_retrieval', 'chi_squared_prefit', 'solar_zenith_angle',
              'optical_thickness_scattering_layer', 'albedo_surface_2365nm'],
})}
SELECTIONS['tropomi'][1]['clear_or_low_cloud'] = SELECTIONS['tropomi'][1]['clear'] + ['height_scattering_layer']


# ----------------------------------------------------- independent geometry

def regrid_day(frame, settings, grid):
    """One day's per-cell sums, recomputed with shapely, pyproj and pandas.

    Returns:
        pandas.DataFrame: indexed by flat cell, a ``count`` column and one
            column per key sum.
    """
    inputs, selection = settings['inputs'], settings['selection']
    passes, stores_for = SELECTIONS[settings.get('source', settings['product'])]
    level = selection['quality_level']
    keep = passes(frame, level)
    for store, bounds in (selection.get('thresholds') or {}).items():
        if 'max' in bounds:
            keep &= ~(frame[store] > bounds['max'])
        if 'min' in bounds:
            keep &= ~(frame[store] < bounds['min'])
    # the sums in float64, as the build's
    delta, sigma, h2o = (frame[inputs[name]].astype('float64') for name in ('delta_d', 'delta_d_uncertainty', 'weight'))
    keep &= np.isfinite(delta) & np.isfinite(sigma) & np.isfinite(h2o)
    lat, lon = frame['lat_corners'][keep].astype('float64'), frame['lon_corners'][keep].astype('float64')
    delta, sigma, h2o = delta[keep], sigma[keep], h2o[keep]
    ok = np.isfinite(lat).all(1) & np.isfinite(lon).all(1)
    # one side of the antimeridian, then drop what still spans a pole
    wide = (np.nanmax(lon, 1) - np.nanmin(lon, 1)) > 180
    lon = np.where(wide[:, None] & (lon < 0), lon + 360, lon)
    ok &= (lon.max(1) - lon.min(1)) <= 90
    lat, lon, delta, sigma, h2o = lat[ok], lon[ok], delta[ok], sigma[ok], h2o[ok]
    rows, cols = grid.shape
    # the footprint's whole area, km2, in EPSG:6933 (x is periodic in longitude)
    x, y = _ease_xy(lat, lon)
    whole = shapely.area(shapely.polygons(np.stack([x, y], -1))) / 1e6
    if grid.kind == 'latlon':
        size = 180 / rows
        u, v = lon, lat
        polygons = shapely.polygons(np.stack([u, v], -1))
        col0 = np.floor((u.min(1) + 180) / size).astype(int)
        col1 = np.floor((u.max(1) + 180) / size).astype(int)
        row0 = np.clip(np.floor((90 - v.max(1)) / size).astype(int), 0, rows - 1)
        row1 = np.clip(np.floor((90 - v.min(1)) / size).astype(int), 0, rows - 1)
    else:
        size = grid.size
        polygons = shapely.polygons(np.stack([x, y], -1))
        x0, y0 = -cols * size / 2, rows * size / 2
        col0 = np.floor((x.min(1) - x0) / size).astype(int)
        col1 = np.floor((x.max(1) - x0) / size).astype(int)
        row0 = np.clip(np.floor((y0 - y.max(1)) / size).astype(int), 0, rows - 1)
        row1 = np.clip(np.floor((y0 - y.min(1)) / size).astype(int), 0, rows - 1)
    n_pairs = (row1 - row0 + 1) * (col1 - col0 + 1)
    # whole footprints per block, about verify.max_pairs candidate pairs each, so
    # memory stays bounded (shapely objects are large); a footprint's W is
    # complete within its block
    limit = int((settings.get('verify') or {}).get('max_pairs', 2_000_000))
    ends = np.cumsum(n_pairs)
    parts, first = [], 0
    while first < lat.shape[0]:
        last = max(first + 1, int(np.searchsorted(ends, ends[first] - n_pairs[first] + limit, side='right')))
        block = np.arange(first, last)
        parts.append(_block_sums(block, n_pairs, row0, col0, col1, polygons, grid, size, delta, sigma, h2o, whole,
                                 x0y0=None if grid.kind == 'latlon' else (x0, y0)))
        first = last
    if not parts:
        return pd.DataFrame(columns=['count', *nomenclature.quantity_names('sum')], dtype='float64')
    return pd.concat(parts).groupby(level=0).sum()


def _block_sums(block, n_pairs, row0, col0, col1, polygons, grid, size, delta, sigma, h2o, whole, x0y0):
    """The per-cell sums of one block of whole footprints (``regrid_day``)."""
    rows, cols = grid.shape
    counts = n_pairs[block]
    foot = np.repeat(block, counts)
    within = np.arange(counts.sum()) - np.repeat(np.cumsum(counts) - counts, counts)
    width = (col1 - col0 + 1)[foot]
    row = row0[foot] + within // width
    col = col0[foot] + within % width
    if x0y0 is None:
        boxes = shapely.box(-180 + col * size, 90 - (row + 1) * size, -180 + (col + 1) * size, 90 - row * size)
    else:
        x0, y0 = x0y0
        boxes = shapely.box(x0 + col * size, y0 - (row + 1) * size, x0 + (col + 1) * size, y0 - row * size)
    piece = shapely.area(shapely.intersection(polygons[foot], boxes))
    del boxes
    hit = piece > 0
    foot, row, col, piece = foot[hit], row[hit], col[hit] % cols, piece[hit]
    if x0y0 is None:
        north, south = np.deg2rad(90 - row * size), np.deg2rad(90 - (row + 1) * size)
        km2 = piece / size**2 * EARTH_KM**2 * np.deg2rad(size) * (np.sin(north) - np.sin(south))
    else:
        km2 = piece / 1e6
    pairs = pd.DataFrame({'cell': row * cols + col, 'foot': foot, 'area': km2})
    pairs['weight'] = pairs['area'] * 1e6 * h2o[foot]
    big_w = pairs.groupby('foot')['weight'].transform('sum')
    d, var, a = delta[foot], sigma[foot] ** 2, whole[foot]
    w = pairs['weight']
    pairs = pairs.assign(weight_delta_d=w * d, weight_delta_d_squared=w * d * d, weight_squared=w * w,
                         weight_squared_variance=w * w * var, weight_footprint_area=w * a,
                         weight_total=w * big_w, weight_total_variance=w * big_w * var, count=1)
    return pairs.drop(columns='foot').groupby('cell').sum()


def _ease_xy(lat, lon):
    """EPSG:6933 x, y by pyproj; longitudes past 180 are shifted back and x moved by one period."""
    beyond = lon > 180
    x, y = EPSG_6933.transform(np.where(beyond, lon - 360, lon), lat)
    x_period = 2 * EPSG_6933.transform(180.0, 0.0)[0]
    return np.where(beyond, x + x_period, x), y



def recompute(l2, settings, grid, start, end):
    """A period's sums and statistics on the whole grid, independently."""
    passes, stores_for = SELECTIONS[settings.get('source', settings['product'])]
    needed = list(dict.fromkeys([*stores_for[settings['selection']['quality_level']],
                                 *(settings['selection'].get('thresholds') or {}),
                                 *(settings['inputs'][name] for name in ('delta_d', 'delta_d_uncertainty', 'weight'))]))
    inputs, selection = settings['inputs'], settings['selection']

    def keep(frame):
        # the selection again, applied while reading so only kept rows are held
        ok = passes(frame, selection['quality_level'])
        for store, bounds in (selection.get('thresholds') or {}).items():
            ok &= ~(frame[store] > bounds.get('max', np.inf)) & ~(frame[store] < bounds.get('min', -np.inf))
        for name in ('delta_d', 'delta_d_uncertainty', 'weight'):
            ok &= np.isfinite(frame[inputs[name]])
        return ok

    parts = []
    for day in range(start, end):
        frame = l2.day(day, needed, keep)
        if frame is not None and len(frame['lat_corners']):
            parts.append(regrid_day(frame, settings, grid))
    names = nomenclature.quantity_names('sum')
    if parts:
        total = pd.concat(parts).groupby(level=0).sum()
    else:
        total = pd.DataFrame(columns=['count', *names], dtype='float64')
    n = grid.shape[0] * grid.shape[1]
    out = {name: np.zeros(n) for name in names}
    count = np.zeros(n, dtype='int64')
    cells = total.index.to_numpy().astype('int64')
    count[cells] = total['count'].to_numpy()
    for name in names:
        out[name][cells] = total[name].to_numpy()
    area = expected_coords(grid)['cell_area'][np.arange(n) // grid.shape[1]]
    with np.errstate(invalid='ignore', divide='ignore'):
        w = np.where(count > 0, out['weight'], np.nan)
        mean = out['weight_delta_d'] / w
        stats = {
            'delta_d': mean, 'standard_error': np.sqrt(out['weight_squared_variance']) / w,
            'spread': np.sqrt(np.clip(out['weight_delta_d_squared'] / w - mean**2, 0, None)),
            'n_eff': w**2 / out['weight_squared'], 'count': count, 'h2o': w / out['area'] / 1e6,
            'coverage': np.where(count > 0, out['area'], np.nan) / area, 'footprint_area': out['weight_footprint_area'] / w,
        }
    return {**out, **stats}


# ------------------------------------------------------------------- phases

def target_paths(settings, layout, grid, frequency):
    return {quantity: config.store_path(settings, layout, frequency, grid.name, row['canonical_name'])
            for quantity, row in nomenclature.quantities().items()}


def open_group(path, tag=None):
    repository = icechunk.Repository.open(icechunk.local_filesystem_storage(path))
    session = repository.readonly_session(tag=tag) if tag else repository.readonly_session(branch='main')
    return zarr.open_group(session.store, mode='r')


def check_structure(report, settings, layout, grid, frequency, paths, first, last, snapshots):
    from utils import stores as store_utils  # chunk shapes are the config's, read through the same helper
    bounds = expected_periods(first, last, frequency)
    coords = expected_coords(grid)
    row_dim, col_dim = ('lat', 'lon') if grid.kind == 'latlon' else ('y', 'x')
    times = None
    for quantity, path in paths.items():
        what = f'{os.path.basename(path)}'
        if not report.check(os.path.isdir(path), f'{what}: exists'):
            continue
        group = open_group(path)
        row = nomenclature.quantities()[quantity]
        name = row['canonical_name']
        array = group[name]
        report.check(tuple(array.metadata.dimension_names) == ('time', row_dim, col_dim), f'{what}: dims')
        report.check(array.dtype == np.dtype(row['dtype']), f'{what}: dtype {array.dtype} != {row["dtype"]}')
        report.check(array.shape == (len(bounds), *grid.shape), f'{what}: shape {array.shape}')
        report.check(tuple(array.chunks) == store_utils.layout_chunks(settings, grid, layout, len(bounds)),
                     f'{what}: chunks {array.chunks}')
        report.check(array.attrs.get('units') == row['canonical_units'], f'{what}: units')
        stored = group['time_bounds'][:]
        report.check(np.array_equal(stored, bounds), f'{what}: time_bounds are not the expected periods')
        times = stored if times is None else times
        report.check(np.array_equal(stored, times), f'{what}: time axis differs from its siblings')
        for coord, values in coords.items():
            report.check(np.allclose(group[coord][:], values, rtol=0, atol=1e-7 if coord in ('lat', 'lon') else 1e-6 * np.abs(values).max()),
                         f'{what}: coordinate {coord}')
        attrs = group.attrs
        for key in REQUIRED_ATTRS:
            report.check(key in attrs, f'{what}: attribute {key}')
        report.check(attrs.get('cdm_data_type') == 'Grid', f'{what}: cdm_data_type')
        report.check(attrs.get('source_l2_snapshots') == snapshots, f'{what}: L2 tag no longer names the snapshots it was built from')
        report.check(attrs.get('temporal_frequency') == frequency and attrs.get('grid_name') == grid.name, f'{what}: tokens')


def sample_periods(settings, n_periods, frequency):
    spec = settings.get('verify') or {}
    rng = np.random.default_rng(int(spec.get('seed', 20261110)))
    extra = int((spec.get('samples') or {}).get(frequency, spec.get('samples_default', 2)))
    chosen = {0, n_periods - 1}
    pool = [k for k in range(n_periods) if k not in chosen]
    chosen.update(rng.choice(pool, size=min(extra, len(pool)), replace=False).tolist() if pool else [])
    return sorted(chosen)


def check_spatial_samples(report, settings, grid, frequency, paths, l2, first, last):
    bounds = expected_periods(first, last, frequency)
    groups = {quantity: open_group(path) for quantity, path in paths.items()}
    for k in sample_periods(settings, len(bounds), frequency):
        start, end = int(bounds[k][0]), int(bounds[k][1])
        # the build grids days inside the record only; so does the recomputation
        expected = recompute(l2, settings, grid, max(start, first), min(end, last + 1))
        label = f'{grid.name} {frequency} {pd.Timestamp("1900-01-01") + pd.Timedelta(days=start):%Y-%m-%d}'
        occupied = int((expected['count'] > 0).sum())
        for quantity, group in groups.items():
            row = nomenclature.quantities()[quantity]
            stored = group[row['canonical_name']][k].reshape(-1)
            want = expected[quantity]
            if quantity == 'count':
                ok = np.array_equal(stored, want)
            elif row['kind'] == 'sum':
                ok = np.allclose(stored, want, rtol=SUM_RTOL, atol=SUM_RTOL * max(np.abs(want).max(), 1e-300))
            else:
                ok = (np.array_equal(np.isnan(stored), np.isnan(want))
                      and np.allclose(stored, want, rtol=STAT_RTOL, atol=STAT_ATOL.get(quantity, 0), equal_nan=True))
            if not report.check(ok, f'{label} {quantity}'):
                diff = np.abs(stored.astype('float64') - want)
                LOG.error(f'  max |diff| {np.nanmax(diff):.3g} at cell {int(np.nanargmax(diff))}; stored occupied '
                          f'{int(np.isfinite(stored).sum()) if stored.dtype.kind == "f" else int((stored > 0).sum())}')
        LOG.info(f'{label}: {occupied:,} occupied cells recomputed and compared')


def check_temporal_samples(report, settings, grid, frequency, spatial, temporal):
    spec = settings.get('verify') or {}
    rng = np.random.default_rng(int(spec.get('seed', 20261110)))
    tag = settings['temporal']['source_tag']
    for quantity, path in temporal.items():
        name = nomenclature.quantities()[quantity]['canonical_name']
        target = open_group(path)[name]
        source = open_group(spatial[quantity], tag=tag)[name]
        n_time, rows, cols = target.shape
        _, tile_rows, tile_cols = target.chunks
        tiles = [(r, c) for r in range(0, rows, tile_rows) for c in range(0, cols, tile_cols)]
        picks = [tiles[0], tiles[-1], *(tiles[i] for i in rng.choice(len(tiles), size=min(int(spec.get('tiles', 6)), len(tiles)), replace=False))]
        times = sorted({0, n_time - 1, *rng.choice(n_time, size=min(int(spec.get('times', 6)), n_time), replace=False).tolist()})
        planes = {t: source[t] for t in times}
        for r, c in picks:
            block = target[:, r:r + tile_rows, c:c + tile_cols]
            for t in times:
                report.check(np.array_equal(block[t], planes[t][r:r + tile_rows, c:c + tile_cols], equal_nan=block.dtype.kind == 'f'),
                             f'{os.path.basename(path)}: tile ({r},{c}) period {t} differs from the spatial store')
        LOG.info(f'{os.path.basename(path)}: {len(picks)} tiles x {len(times)} periods equal to spatial@{tag}')


def main():
    args = parse_args()
    settings = config.load_config(args.config)
    config.setup_logging(settings, prefix='verify_')
    phases = args.phases.split(',')
    report = Report()
    l2 = IndependentL2(settings)
    from grid_wisosat import l2_stores  # which stores a build reads: their snapshots are recorded
    snapshots = l2.snapshots(l2_stores(settings, config.source_module(settings)))
    geo = l2.group(config.GEOLOCATION)
    unit = geo['time'].attrs['units'].split(' since ')[0]
    per_day = {'milliseconds': 86_400_000, 'seconds': 86_400, 'microseconds': 86_400_000_000,
               'nanoseconds': 86_400_000_000_000}[unit]
    counts = geo['granule_obs_count'][:]
    first = int(geo['granule_time_start'][:][counts > 0].min() // per_day)
    last = int(geo['granule_time_end'][:][counts > 0].max() // per_day)
    limit = settings.get('period') or {}
    epoch = pd.Timestamp('1900-01-01')
    if limit.get('start'):
        first = max(first, (pd.Timestamp(limit['start']) - epoch).days)
    if limit.get('end'):
        last = min(last, (pd.Timestamp(limit['end']) - epoch).days)
    names = []
    for spec in settings['grids']:
        grid = from_spec(spec)
        for frequency in settings['frequencies']:
            paths = target_paths(settings, args.layout, grid, frequency)
            names += [os.path.basename(path) for path in paths.values()]
            if 'structure' in phases:
                check_structure(report, settings, args.layout, grid, frequency, paths, first, last, snapshots)
            if 'samples' in phases:
                if args.layout == 'spatial':
                    check_spatial_samples(report, settings, grid, frequency, paths, l2, first, last)
                else:
                    check_temporal_samples(report, settings, grid, frequency,
                                           target_paths(settings, 'spatial', grid, frequency), paths)
    LOG.info(f'layout: {args.layout}; phases: [{", ".join(phases)}]; stores: [{", ".join(names)}]')
    LOG.info(f'{report.checks} checks, {report.failures} failures')
    if report.failures:
        sys.exit(1)
    LOG.info(PASSED)


if __name__ == '__main__':
    main()
