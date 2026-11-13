"""AIRS footprint polygons from the L2 geometry fields alone: prototype and self-checks.

Evidence for AIRS gridding decision D1 (C2; 1.1-1.5 in
`airs-gridding-decisions.md`, 2026-11-13). A prototype, not the engine code:
the engine's `airs_fov` model and the verifier's independent version follow
it. The L1B comparison (1.6, `airs_fov_l1b.py`, 2026-11-13) settled the
choices below: the orbit model in the inertial frame, the side as written,
and the height from the orbit phase (user decision 2026-11-13); they are
the defaults here.

The model, per target (one AIRS footprint, centre `lat`/`lon`):

1. Signed scan angle: `airs_view_ang` (unsigned), negative for
   `airs_xtrack` <= 44 (1.3).
2. Orbit phase u of its scan, from the scan's place in the AIRS day,
   n = 135 (`airs_granule` - 1) + `airs_atrack`: u = u0 + k (n - n_mid),
   with u0 and k fitted per file to the targets' latitudes (two numbers a
   day; a circular orbit at Aqua's 98.2 degree inclination). `time` is not
   used: v1 RS stores it in 64 s steps.
3. The scan plane holds the satellite's nadir and is perpendicular to its
   velocity (1.2, the orbit model): `--frame inertial` (the orbit's own
   heading; it matches L1B's `satazi` to 2 degrees) or `--frame ground`
   (the ground track's heading, Earth's rotation taken out; off by up to 5).
4. The satellite's height above WGS84 comes from the orbit (1.4, `--height
   phase`): the radius a (1 - e sin u) of a frozen orbit (perigee over the
   north) less the ellipsoid's radius under it, a from the fitted phase
   rate by Kepler's third law; its two constants were set on the L1B
   sample, where the height runs 705-720 km in 2010 and 2022 and 692-700 km
   in 2026. `--height nominal` is the 705.3 km first approved: areas 4.4%
   small to 4.1% large against L1B. The satellite is where a ray leaving it
   at the scan angle in the scan plane meets the target.
5. The footprint is where the 1.1 degree cone about that ray meets the
   WGS84 ellipsoid: 32 vertices on its edge (1.1, 1.5).

The per-granule fit (1.2's other method) is `--orientation fit`: the scan
line's bearing from a least-squares fit, within each AIRS granule, of the
targets' ground positions against `airs_atrack` and the cross-track ground
distance. Not kept: off by up to 32 degrees at high latitudes.

Self-checks, needing no L1B (printed per file):

- the phase fit's latitude residual;
- **same-scan closure:** targets of one scan (same granule and atrack)
  share one satellite position, so the sub-satellite points the model gives
  them must coincide; a wrong side puts them 2x the cross-track distance
  apart, a wrong scan-plane bearing shows as an along-track gap that grows
  with the targets' separation;
- footprint size by cross-track index against the L1B README's 13.5 km at
  nadir and 41 x 21.4 km at the swath edge.

Reads raw TROPESS files: run with the l2 environment, from the repo root:
l2/.venv/bin/python -I gridding/tools/survey/airs_fov_polygon.py [--frame inertial|ground]
    [--orientation orbit|fit] [--height nominal|phase] [--flip-side] <file> [<file> ...]
"""
import argparse

import netCDF4
import numpy as np

# WGS84
A = 6378.137
F = 1 / 298.257223563
B = A * (1 - F)
E2 = F * (2 - F)

HEIGHT = 705.3              # km, nominal (README.AIRIBRAD)
INCLINATION = np.radians(98.2)
HALF_FOV = np.radians(1.1 / 2)
VERTICES = 32
SCANS_PER_GRANULE = 135
# Earth's rotation rate over the orbit's mean motion (16-day, 233-orbit repeat)
ROTATION_RATIO = (16 * 86400 / 233) / 86164.0905
# nominal phase step per scan: 8/3 s of a 5,933 s orbit
K0 = 2 * np.pi * (8 / 3) / (16 * 86400 / 233)
# `--height phase`: orbit radius (km) at the nominal phase step, and the
# eccentricity; both read off L1B `satheight` (2010-06-15 granules)
RADIUS_AT_K0 = 7082.8
ECCENTRICITY = 0.0014


def ecef(lat, lon, height=0.0):
    """Geodetic degrees and km above WGS84 to ECEF km, ``(..., 3)``."""
    lat, lon = np.radians(lat), np.radians(lon)
    n = A / np.sqrt(1 - E2 * np.sin(lat) ** 2)
    return np.stack([(n + height) * np.cos(lat) * np.cos(lon),
                     (n + height) * np.cos(lat) * np.sin(lon),
                     (n * (1 - E2) + height) * np.sin(lat)], axis=-1)


def surface_latlon(p):
    """Geodetic degrees of ECEF points lying on the ellipsoid."""
    lat = np.degrees(np.arctan2(p[..., 2], (1 - E2) * np.hypot(p[..., 0], p[..., 1])))
    return lat, np.degrees(np.arctan2(p[..., 1], p[..., 0]))


def geocentric(lat):
    """Geocentric latitude (radians) of a geodetic latitude (degrees) on the ellipsoid."""
    return np.arctan((1 - E2) * np.tan(np.radians(lat)))


def geodetic(lat_c):
    """Geodetic latitude (degrees) of a geocentric latitude (radians) on the ellipsoid."""
    return np.degrees(np.arctan(np.tan(lat_c) / (1 - E2)))


def destination(lat, lon, bearing, angle):
    """Great-circle destination and arrival bearing on a sphere; all radians."""
    sin_lat = np.sin(lat) * np.cos(angle) + np.cos(lat) * np.sin(angle) * np.cos(bearing)
    lat2 = np.arcsin(np.clip(sin_lat, -1, 1))
    lon2 = lon + np.arctan2(np.sin(bearing) * np.sin(angle) * np.cos(lat),
                            np.cos(angle) - np.sin(lat) * sin_lat)
    # the bearing on arrival is the reverse of the bearing back to the start
    back = np.arctan2(np.sin(lon - lon2) * np.cos(lat),
                      np.cos(lat2) * np.sin(lat) - np.sin(lat2) * np.cos(lat) * np.cos(lon - lon2))
    return lat2, lon2, back + np.pi


def central_angle(scan, radius, height=HEIGHT):
    """Earth-central angle from the sub-satellite point to where a ray at ``scan`` lands."""
    return np.arcsin(np.clip((radius + height) * np.sin(scan) / radius, -1, 1)) - scan


def orbit_height(u, k):
    """Height above WGS84 (km) at orbit phase ``u``, for a phase step ``k`` per scan."""
    lat = np.arcsin(np.sin(INCLINATION) * np.sin(u))
    ellipsoid = A * B / np.hypot(B * np.cos(lat), A * np.sin(lat))
    return RADIUS_AT_K0 * (K0 / k) ** (2 / 3) * (1 - ECCENTRICITY * np.sin(u)) - ellipsoid


def heading(u, frame):
    """Sub-satellite latitude (geocentric) and the heading the scan plane is perpendicular to.

    Args:
        u (numpy.ndarray): Orbit phase from the ascending node, radians.
        frame (str): ``inertial`` or ``ground``.

    Returns:
        tuple: ``(latitude, heading)``, radians; heading clockwise from north.
    """
    lat = np.arcsin(np.sin(INCLINATION) * np.sin(u))
    east, north = np.cos(INCLINATION), np.sin(INCLINATION) * np.cos(u)
    if frame == 'ground':
        # the unit above is the speed over a non-rotating Earth times cos(lat)
        east = east - ROTATION_RATIO * np.cos(lat) ** 2
    return lat, np.arctan2(east, north)


def predicted_latitude(u, scan, radius, frame, side, height=HEIGHT):
    """Geocentric latitude where each target should be, and the bearing from it back to nadir."""
    lat_p, head = heading(u, frame)
    # scan < 0 is the left of the heading when side is +1
    bearing = head + side * np.sign(scan) * np.pi / 2
    lat_t, _, arrival = destination(lat_p, 0.0, bearing, central_angle(np.abs(scan), radius, height))
    return lat_t, arrival + np.pi


def fit_phase(n, lat_c, scan, radius, frame, side):
    """Fit u = u0 + k (n - n_mid) to the targets' latitudes: a scan of u0, then Gauss-Newton."""
    n_mid = 0.5 * (n.min() + n.max())
    x = n - n_mid

    def residual(u0, k):
        return predicted_latitude(u0 + k * x, scan, radius, frame, side)[0] - lat_c

    u0 = min(np.radians(np.arange(0, 360, 2.0)), key=lambda v: np.square(residual(v, K0)).sum())
    k = K0
    for _ in range(20):
        r = residual(u0, k)
        jac = np.stack([(residual(u0 + 1e-6, k) - r) / 1e-6, (residual(u0, k + 1e-9) - r) / 1e-9], axis=1)
        step = np.linalg.lstsq(jac, -r, rcond=None)[0]
        u0, k = u0 + step[0], k + step[1]
        if np.abs(step[0]) < 1e-10:
            break
    return u0 + k * x, np.degrees(residual(u0, k)), np.degrees(u0), k


def fitted_bearing(granule, atrack, lat, lon, scan, radius, side):
    """Bearing from each target back to nadir, from a per-granule fit (1.2's other method).

    Within a granule the ground positions, in a local plane (km east, km
    north of the granule's mean), are fitted as a quadratic in ``atrack``
    plus the signed cross-track ground distance times one vector e; the scan
    line's bearing is e's. A granule whose targets do not spread across the
    track gives no e: NaN.
    """
    out = np.full(lat.shape, np.nan)
    distance = radius * central_angle(np.abs(scan), radius) * np.sign(scan) * side
    for g in np.unique(granule):
        m = granule == g
        if m.sum() < 5 or np.ptp(distance[m]) < 50:
            continue
        lat0, lon0 = lat[m].mean(), lon[m][0]
        dlon = (lon[m] - lon0 + 180) % 360 - 180
        east = np.radians(dlon) * radius[m] * np.cos(np.radians(lat[m]))
        north = np.radians(lat[m] - lat0) * radius[m]
        a = atrack[m] - atrack[m].mean()
        design = np.stack([np.ones(a.size), a, a * a, distance[m]], axis=1)
        coef = np.linalg.lstsq(design, np.stack([east, north], axis=1), rcond=None)[0]
        # e points from nadir to a target at positive distance: back to nadir is the reverse
        out[m] = np.arctan2(coef[3, 0], coef[3, 1]) + np.where(distance[m] > 0, np.pi, 0.0)
    return out


def satellite(lat, lon, scan, back_bearing, radius, height=HEIGHT):
    """Satellite ECEF position: ``height`` over the point one central angle back along the scan line."""
    lat_p, lon_p, _ = destination(geocentric(lat), np.radians(lon), back_bearing,
                                  central_angle(np.abs(scan), radius, height))
    return ecef(geodetic(lat_p), np.degrees(lon_p), height), geodetic(lat_p), np.degrees(lon_p)


def polygons(lat, lon, sat):
    """The 1.1 degree cone about the line of sight, met with WGS84: ``(n, VERTICES)`` lat and lon.

    Vertex 0 lies in the plane of the line of sight and the satellite's
    geocentric nadir, on the far side from nadir; the vertices then go round
    the line of sight.
    """
    target = ecef(lat, lon)
    sight = target - sat
    sight /= np.linalg.norm(sight, axis=-1, keepdims=True)
    side = np.cross(sight, sat)
    # at nadir the line of sight is along the satellite's position: any perpendicular will do
    flat = np.linalg.norm(side, axis=-1) < 1e-9 * np.linalg.norm(sat, axis=-1)
    side[flat] = np.cross(sight[flat], [0.0, 0.0, 1.0])
    side /= np.linalg.norm(side, axis=-1, keepdims=True)
    up = np.cross(side, sight)
    phi = 2 * np.pi * np.arange(VERTICES) / VERTICES
    ray = (np.cos(HALF_FOV) * sight[:, None, :]
           + np.sin(HALF_FOV) * (np.cos(phi)[None, :, None] * up[:, None, :]
                                 + np.sin(phi)[None, :, None] * side[:, None, :]))
    # stretch z so the ellipsoid is a sphere of radius A; the nearer root is the ground
    scale = np.array([1.0, 1.0, A / B])
    o, d = sat[:, None, :] * scale, ray * scale
    dd, od, oo = (d * d).sum(-1), (o * d).sum(-1), (o * o).sum(-1)
    t = (-od - np.sqrt(od * od - dd * (oo - A * A))) / dd
    return surface_latlon(sat[:, None, :] + t[..., None] * ray)


def extents(lat, lon, plat, plon, back_bearing):
    """Cross-track and along-track extent (km) of each polygon, in the target's local plane."""
    radius = np.linalg.norm(ecef(lat, lon), axis=-1)[:, None]
    dlon = (plon - lon[:, None] + 180) % 360 - 180
    east = np.radians(dlon) * radius * np.cos(np.radians(lat))[:, None]
    north = np.radians(plat - lat[:, None]) * radius
    cross = east * np.sin(back_bearing)[:, None] + north * np.cos(back_bearing)[:, None]
    along = east * np.cos(back_bearing)[:, None] - north * np.sin(back_bearing)[:, None]
    area = 0.5 * np.abs((east * np.roll(north, -1, 1) - np.roll(east, -1, 1) * north).sum(1))
    return np.ptp(cross, axis=1), np.ptp(along, axis=1), area


def read(path):
    """The geometry fields of one raw TROPESS AIRS file, rows with any missing dropped."""
    with netCDF4.Dataset(path) as d:
        g = d['geolocation']
        out = {'lat': d['latitude'][:], 'lon': d['longitude'][:], 'granule': g['airs_granule'][:],
               'atrack': g['airs_atrack'][:], 'xtrack': g['airs_xtrack'][:], 'view': g['airs_view_ang'][:]}
    keep = ~np.any([np.ma.getmaskarray(v) for v in out.values()], axis=0)
    return {k: np.ma.getdata(v)[keep].astype('float64' if k in ('lat', 'lon', 'view') else 'int64')
            for k, v in out.items()}


def model(f, frame='inertial', orientation='orbit', side=1.0, height='phase'):
    """Run the model on one file's fields; returns the pieces the checks and the L1B comparison need."""
    scan = np.radians(f['view']) * np.where(f['xtrack'] <= 44, -1.0, 1.0)
    radius = np.linalg.norm(ecef(f['lat'], f['lon']), axis=-1)
    n = SCANS_PER_GRANULE * (f['granule'] - 1) + f['atrack']
    # the phase is fitted at the nominal height: it moves the fit by under 0.01 degrees
    u, residual, u0, k = fit_phase(n, geocentric(f['lat']), scan, radius, frame, side)
    high = orbit_height(u, k) if height == 'phase' else np.full(u.shape, HEIGHT)
    back = predicted_latitude(u, scan, radius, frame, side, high)[1]
    if orientation == 'fit':
        back = fitted_bearing(f['granule'], f['atrack'], f['lat'], f['lon'], scan, radius, side)
    ok = np.isfinite(back)
    sat, lat_p, lon_p = satellite(f['lat'], f['lon'], scan, np.where(ok, back, 0.0), radius, high)
    plat, plon = polygons(f['lat'], f['lon'], sat)
    return {'scan': scan, 'n': n, 'u': u, 'residual': residual, 'u0': u0, 'k': k, 'back': back, 'ok': ok,
            'height': high, 'sat': sat, 'lat_p': lat_p, 'lon_p': lon_p, 'plat': plat, 'plon': plon}


def closure(f, m):
    """Same-scan closure: each scan's sub-satellite points against their mean, km."""
    order = np.argsort(m['n'], kind='stable')
    n = m['n'][order]
    starts = np.flatnonzero(np.r_[True, np.diff(n) > 0])
    counts = np.diff(np.r_[starts, n.size])
    group = np.repeat(np.arange(starts.size), counts)
    sub = ecef(m['lat_p'], m['lon_p'])[order]
    ok = m['ok'][order]
    sums = np.zeros((starts.size, 3))
    np.add.at(sums, group[ok], sub[ok])
    members = np.bincount(group[ok], minlength=starts.size)
    use = ok & (members[group] >= 2)
    miss = np.linalg.norm(sub[use] - (sums / np.maximum(members, 1)[:, None])[group[use]], axis=-1)
    return miss, (members >= 2).sum()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('files', nargs='+')
    parser.add_argument('--frame', choices=('inertial', 'ground'), default='inertial')
    parser.add_argument('--orientation', choices=('orbit', 'fit'), default='orbit')
    parser.add_argument('--height', choices=('nominal', 'phase'), default='phase')
    parser.add_argument('--flip-side', action='store_true', help='xtrack <= 44 on the right of the heading')
    args = parser.parse_args()
    side = -1.0 if args.flip_side else 1.0
    for path in args.files:
        f = read(path)
        m = model(f, args.frame, args.orientation, side, args.height)
        print(f'{path.rsplit("/", 1)[-1]}: {f["lat"].size} targets; frame {args.frame}, '
              f'orientation {args.orientation}, side {side:+.0f}')
        r = m['residual']
        print(f'  phase fit: u0 {m["u0"] % 360:.3f} deg, k/k0 {m["k"] / K0:.5f}; latitude residual (deg) '
              f'p50 {np.median(np.abs(r)):.4f}, p99 {np.percentile(np.abs(r), 99):.4f}, max {np.abs(r).max():.4f}')
        miss, scans = closure(f, m)
        if miss.size:
            print(f'  same-scan closure: {scans} scans with 2+ targets ({m["ok"].mean():.1%} of targets oriented); '
                  f'sub-satellite point from its scan mean (km) p50 {np.median(miss):.2f}, '
                  f'p95 {np.percentile(miss, 95):.2f}, p99 {np.percentile(miss, 99):.2f}, max {miss.max():.2f}')
        ok = m['ok']
        cross, along, area = extents(f['lat'][ok], f['lon'][ok], m['plat'][ok], m['plon'][ok], m['back'][ok])
        xtrack = f['xtrack'][ok]
        print('  footprint by cross-track index: xtrack n, cross x along (km), area (km2)')
        for x in (0, 10, 22, 36, 44, 45, 60, 75, 89):
            s = xtrack == x
            if s.any():
                print(f'    {x:2d} {s.sum():5d}  {np.median(cross[s]):5.2f} x {np.median(along[s]):5.2f}  '
                      f'{np.median(area[s]):7.1f}')


if __name__ == '__main__':
    main()
