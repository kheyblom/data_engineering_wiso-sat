"""Measured AIRS v1 sampling per grid cell, by day and by month, after D5's selection.

Evidence for AIRS gridding decision D6 (`airs-gridding-decisions.md`, 2026-11-13).
Reads the finalized L2 stores; from gridding/: uv run python tools/survey/airs_cell_fill.py
(~1 GB read, ~1 min, ~3 GB memory).

Every v1 row (L2 stores at v1-verified-20261023) passing D5 (DOF > 1.1, or DOF
missing and dd_col_p written) is binned by its centre into lat/lon cells of
0.25, 1 and 2 degrees. Per period (UTC day, calendar month): cells holding at
least one retrieval, as a share of all cells and of the cells in the stream's
latitude band; retrievals per filled cell. Reported as p5/p50/p95 over the
periods of the record (months with < 20 days of data left out).
Centre binning only: with D1's polygons a footprint touches 1-4 cells, so fill
is a little higher.
"""
import icechunk
import numpy as np
import zarr

icechunk.set_logs_filter('error')
BASE = ('/glade/derecho/scratch/kheyblom/data/wisosat/zarr/airs/l2/'
        'wisosat.airs.v_1.{}.inst.native_swath.{}.zarr')
TAG = 'v1-verified-20261023'
BLOCK = 4_194_304
RES = (0.25, 1.0, 2.0)
BAND = {'rs': (-50.0, 70.0), 'fs': (-67.0, 85.0)}


def group(stream, store):
    repo = icechunk.Repository.open(icechunk.local_filesystem_storage(BASE.format(stream, store)))
    return zarr.open_group(repo.readonly_session(tag=TAG).store, mode='r')


def pct(a):
    return '/'.join(f'{v:.3g}' for v in np.percentile(a, [5, 50, 95]))


for stream in ('rs', 'fs'):
    geo = group(stream, 'geolocation')
    dof = group(stream, 'water_vapor_hdo_h2o_ratio_degrees_of_freedom_for_signal')['water_vapor_hdo_h2o_ratio_degrees_of_freedom_for_signal']
    dd = group(stream, 'water_vapor_delta_d_850_250hpa')['water_vapor_delta_d_850_250hpa']
    n = geo['time'].shape[0]
    days, lats, lons = [], [], []
    for i in range(0, n, BLOCK):
        d = dof[i:i + BLOCK]
        keep = (d > np.float32(1.1)) | (~np.isfinite(d) & np.isfinite(dd[i:i + BLOCK]))
        days.append((geo['time'][i:i + BLOCK][keep] // 86400).astype('int64'))
        lats.append(geo['lat'][i:i + BLOCK][keep].astype('float64'))
        lons.append(geo['lon'][i:i + BLOCK][keep].astype('float64'))
    day = np.concatenate(days)
    lat = np.concatenate(lats)
    lon = np.concatenate(lons)
    month = (np.datetime64('1900-01-01') + day.astype('timedelta64[D]')).astype('datetime64[M]').astype('int64')
    # days with data per month, to drop partial months
    um, md = np.unique(np.unique(np.stack([month, day]), axis=1)[0], return_counts=True)
    full_months = um[md >= 20]
    print(f'== {stream}: {day.size:,} retrievals, {np.unique(day).size:,} days, {full_months.size} months with >= 20 days')
    lo, hi = BAND[stream]
    for res in RES:
        nrow, ncol = int(round(180 / res)), int(round(360 / res))
        row = np.clip(((90 - lat) // res).astype('int64'), 0, nrow - 1)
        col = np.clip(((lon + 180) // res).astype('int64'), 0, ncol - 1)
        cell = row * ncol + col
        band_cells = int(round((hi - lo) / res)) * ncol
        out = []
        for label, period, select in (('day', day, None), ('month', month, np.isin(month, full_months))):
            p, c = (period, cell) if select is None else (period[select], cell[select])
            key = p * (nrow * ncol) + c
            uk, per_cell = np.unique(key, return_counts=True)
            up, filled = np.unique(uk // (nrow * ncol), return_counts=True)
            # retrievals per filled cell: pooled over all (period, cell) pairs
            out.append(f'{label}: filled {pct(100 * filled / (nrow * ncol))}% of all cells, '
                       f'{pct(100 * filled / band_cells)}% of band cells; '
                       f'per filled cell p5/p50/p95 {pct(per_cell)}, mean {per_cell.mean():.2f}')
        print(f'  {res:g} deg ({nrow * ncol:,} cells; {band_cells:,} in {lo:g}..{hi:g}):')
        for line in out:
            print(f'    {line}')
