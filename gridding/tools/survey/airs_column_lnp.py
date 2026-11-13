"""850-250 hPa partial-column delta D: ln p interpolation with exact cuts vs half-way thicknesses.

Evidence for AIRS gridding decision D2, 2.1 (`airs-gridding-decisions.md`, 2026-11-13).
A prototype of the column operator, not the engine code. Reads raw TROPESS files: run
with the l2 environment, from the repo root:
l2/.venv/bin/python -I gridding/tools/survey/airs_column_lnp.py <files>

Usage: python column_lnp.py <file> [<file> ...] (Summary v1 or Full v2).

Scheme A (D2 2.1, approved 2026-11-13): q and R*q linear in ln p between
adjacent valid levels; the column runs from min(850, surface) up to 250 hPa,
integrated in dp (hydrostatic; g and M cancel in the ratio). Numerical: each
segment split into 200 steps in ln p, trapezoid in p.
Scheme B: half-way level thicknesses over levels with 250 <= p < 850 (the
D2 evidence table's H2O x dp row).
"""
import sys

import netCDF4
import numpy as np

R_STD = 3.11e-4
TOP, BOTTOM = 250.0, 850.0


def var(d, name, levels=None):
    a = np.ma.filled(d[name][:].astype('float64'), np.nan)
    a[(a <= -999) | (a == -9999)] = np.nan
    return a if levels is None else a[:, :levels]


def column_lnp(p, q, r):
    """Scheme A for one profile (valid levels only, surface first)."""
    lnp, hdo = np.log(p), r * q
    lo, hi = np.log(min(BOTTOM, p[0])), np.log(TOP)
    if lo <= hi:
        return np.nan
    grid = np.linspace(lo, hi, 2001)
    # np.interp needs increasing x: ln p decreases upward
    qg = np.interp(-grid, -lnp, q)
    hg = np.interp(-grid, -lnp, hdo)
    pg = np.exp(grid)
    dp = -np.diff(pg)
    sq = (0.5 * (qg[1:] + qg[:-1]) * dp).sum()
    sh = (0.5 * (hg[1:] + hg[:-1]) * dp).sum()
    return sh / sq


for path in sys.argv[1:]:
    d = netCDF4.Dataset(path)
    full = 'pressure_ret' in d.variables
    x = var(d, 'x', 17)
    h = var(d, 'x_h2o', 17)
    p = var(d, 'pressure_ret' if full else 'pressure', 17)
    ok = np.isfinite(var(d, 'dd_col_p'))
    if full:
        ok &= np.ma.filled(d['quality'][:], -1) == 1
    rows = np.flatnonzero(ok)
    a = np.full(rows.size, np.nan)
    b = np.full(rows.size, np.nan)
    for i, k in enumerate(rows):
        v = np.isfinite(p[k]) & np.isfinite(x[k]) & np.isfinite(h[k])
        pk, qk, rk = p[k][v], h[k][v], x[k][v]
        a[i] = column_lnp(pk, qk, rk)
        up = np.append(pk[1:], np.nan)
        dn = np.insert(pk[:-1], 0, np.nan)
        lower = np.where(np.isfinite(dn), (dn + pk) / 2, pk)
        upper = np.where(np.isfinite(up), (pk + up) / 2, pk)
        sel = (pk >= TOP) & (pk < BOTTOM)
        w = qk * (lower - upper) * sel
        b[i] = (rk * w).sum() / w.sum() if w.sum() > 0 else np.nan
    da, db = 1000 * (a / R_STD - 1), 1000 * (b / R_STD - 1)
    diff = da - db
    good = np.isfinite(diff)
    print(f'== {path.rsplit("/", 1)[-1]}: {good.sum()} of {rows.size} rows')
    print(f'   A (ln p, exact cuts) p5/p50/p95: {np.percentile(da[good], [5, 50, 95]).round(1).tolist()}')
    print(f'   A minus B (half-way): p50 {np.median(diff[good]):+.2f}  p95 |d| '
          f'{np.percentile(np.abs(diff[good]), 95):.2f}  max |d| {np.abs(diff[good]).max():.2f} per mil')
