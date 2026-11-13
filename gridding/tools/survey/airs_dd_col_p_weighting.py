"""Reproduce TROPESS dd_col_p from the level profiles under several weightings.

Evidence for AIRS gridding decision D2 (`airs-gridding-decisions.md`, 2026-11-13):
the unweighted mean reproduces dd_col_p exactly; H2O weighting is ~+57 per mil.
Reads raw TROPESS files, so run with the l2 environment (it has netCDF4), from the
repo root: l2/.venv/bin/python -I gridding/tools/survey/airs_dd_col_p_weighting.py <files>

Usage: python ddcol_weighting.py <file> [<file> ...] (Summary v1 or Full v2).

Levels kept: 250 <= p < 850 hPa (tropess.md R30). Ratio -> delta D with
3.11e-4, TROPESS's constant (dd_col_p `source`). Weightings:
- unweighted: mean of x (TROPESS's stated formula);
- h2o: sum(x h) / sum(h), h = x_h2o;
- h2o_dp: sum(x h dp) / sum(h dp), dp = each level's pressure thickness
  (half-way to the neighbouring valid levels of the whole profile): the
  HDO/H2O ratio of the partial columns on the level grid.
- dp: sum(x dp) / sum(dp), pressure-weighted (air-mass) mean of the ratio.
"""
import sys

import netCDF4
import numpy as np

R_STD = 3.11e-4


def var(d, name, levels=None):
    a = np.ma.filled(d[name][:].astype('float64'), np.nan)
    a[(a <= -999) | (a == -9999)] = np.nan
    return a if levels is None else a[:, :levels]


for path in sys.argv[1:]:
    d = netCDF4.Dataset(path)
    full = 'pressure_ret' in d.variables
    x = var(d, 'x', 17)
    h = var(d, 'x_h2o', 17)
    p = var(d, 'pressure_ret' if full else 'pressure', 17)
    dd = var(d, 'dd_col_p')
    hc = var(d, 'x_h2o_col_p')
    # pressure thickness of each level over the whole valid profile
    p_up = np.concatenate([p[:, 1:], np.full((p.shape[0], 1), np.nan)], axis=1)
    p_dn = np.concatenate([np.full((p.shape[0], 1), np.nan), p[:, :-1]], axis=1)
    lower = np.where(np.isfinite(p_dn), (p_dn + p) / 2, p)   # surface level: its own pressure
    upper = np.where(np.isfinite(p_up), (p + p_up) / 2, p)
    dp = lower - upper
    sel = (p >= 250) & (p < 850) & np.isfinite(x) & np.isfinite(h)
    ok = np.isfinite(dd) & sel.any(axis=1)
    if full:
        q = np.ma.filled(d['quality'][:], -1)
        ok &= q == 1
    w0 = np.where(sel, 1.0, 0.0)
    xs = np.where(sel, x, 0.0)
    hs = np.where(sel, h, 0.0)
    ds = np.where(sel, dp, 0.0)
    ratios = {
        'unweighted': (xs * w0).sum(1) / w0.sum(1),
        'h2o': (xs * hs).sum(1) / hs.sum(1),
        'h2o_dp': (xs * hs * ds).sum(1) / (hs * ds).sum(1),
        'dp': (xs * ds).sum(1) / ds.sum(1),
    }
    print(f'== {path.rsplit("/", 1)[-1]}: {ok.sum()} rows with dd_col_p'
          + (' (quality == 1)' if full else ''))
    print(f'   levels in range: {np.bincount(sel[ok].sum(1)).nonzero()[0].tolist()}')
    for name, r in ratios.items():
        diff = 1000 * (r / R_STD - 1) - dd
        a = np.abs(diff[ok])
        print(f'   {name:11s} minus dd_col_p (per mil): p50 {np.median(diff[ok]):+8.3f}  '
              f'p95 |d| {np.percentile(a, 95):8.3f}  max |d| {a.max():8.3f}')
    hmean = 1e6 * (hs * w0).sum(1) / w0.sum(1)
    print(f'   x_h2o_col_p vs unweighted mean of x_h2o: max rel diff '
          f'{np.nanmax(np.abs(hmean[ok] / hc[ok] - 1)):.2e}')
    print(f'   dd_col_p p5/p50/p95: {np.percentile(dd[ok], [5, 50, 95]).round(1).tolist()}')
