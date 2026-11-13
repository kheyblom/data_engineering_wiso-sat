"""TROPESS v2 published dry-air partial columns against a hydrostatic column.

Evidence for AIRS gridding decisions D2 (2.1) and D4 (`airs-gridding-decisions.md`,
2026-11-13): `retrieval/column_air` (molecules cm-2) over each column type's
`characterization/column_pressure_max` .. `column_pressure_min` equals
dp / (g M_air) to ~0.3% (median ratio 1.003 on AIRS 2026-06-01), so MUSES forms
columns hydrostatically and a partial-column delta D is sum(R q dp) / sum(q dp).

Reads a raw v2 Full file: run with the l2 environment, from the repo root:
l2/.venv/bin/python -I gridding/tools/survey/tropess_column_air.py <Full file> [...]
"""
import sys

import netCDF4
import numpy as np

LABELS = ('Total', 'Total Troposphere', 'Upper Troposphere', 'Lower Troposphere', 'Stratosphere')
N_A = 6.02214076e23
M_AIR = 28.9644e-3  # kg mol-1, dry air
G0 = 9.80665


def filled(variable):
    a = np.ma.filled(variable[:].astype('float64'), np.nan)
    a[a <= -999] = np.nan
    return a


for path in sys.argv[1:]:
    d = netCDF4.Dataset(path)
    column_air = filled(d['retrieval/column_air'])
    p_max = filled(d['characterization/column_pressure_max'])
    p_min = filled(d['characterization/column_pressure_min'])
    phi = np.radians(d['latitude'][:].astype('float64'))
    # WGS84 normal gravity at the surface (Somigliana)
    g_lat = 9.7803253359 * (1 + 0.00193185265241 * np.sin(phi) ** 2) / np.sqrt(1 - 0.00669437999013 * np.sin(phi) ** 2)
    print(f'== {path.rsplit("/", 1)[-1]}')
    for k, label in enumerate(LABELS):
        dp = (p_max[:, k] - p_min[:, k]) * 100
        ok = np.isfinite(column_air[:, k]) & np.isfinite(dp)
        for name, g in (('g0', G0), ('g(lat)', g_lat)):
            ratio = column_air[ok, k] / (dp / (g * M_AIR) * N_A / 1e4)[ok]
            print(f'  {label:18s} {name:6s} n={ok.sum():6d}  column_air / hydrostatic p1 {np.percentile(ratio, 1):.4f} '
                  f'p50 {np.median(ratio):.4f} p99 {np.percentile(ratio, 99):.4f}')
