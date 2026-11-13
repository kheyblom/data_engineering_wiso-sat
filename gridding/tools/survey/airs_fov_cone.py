"""Ground size of the AIRS 1.1 degree field of view projected from 705.3 km.

Evidence for AIRS gridding decision D1 (1.1; `airs-gridding-decisions.md`,
2026-11-13): a circular 1.1 degree cone from the nominal 705.3 km orbit onto a
sphere gives 13.5 km at nadir and 41.0 x 22.4 km (cross x along track) at the
outermost footprint centre (48.95 degrees), against the L1B README's 13.5 km and
41 x 21.4 km. A size check only; the polygon code is still to be written.

Runs anywhere (numpy only): python gridding/tools/survey/airs_fov_cone.py
"""
import numpy as np

HEIGHT = 705.3  # km, nominal (README.AIRIBRAD)
HALF = np.radians(1.1 / 2)

for radius in (6371.0, 6378.137):
    def central(theta):
        """Earth-central angle to where a ray at scan angle theta meets the sphere."""
        return np.arcsin((radius + HEIGHT) * np.sin(theta) / radius) - theta

    def slant(theta):
        g = central(theta)
        return np.sqrt(radius**2 + (radius + HEIGHT) ** 2 - 2 * radius * (radius + HEIGHT) * np.cos(g))

    for scan in (0.0, 24.75, 48.95, 49.5):
        t = np.radians(scan)
        cross = radius * (central(t + HALF) - central(t - HALF))
        along = 2 * slant(t) * np.tan(HALF)
        print(f'R={radius} km, scan {scan:5.2f} deg: cross-track {cross:5.1f} km, along-track {along:5.1f} km')
