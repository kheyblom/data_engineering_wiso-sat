"""AIRS footprint polygons from the published L2 geometry fields (model ``airs_fov``).

TROPESS publishes no footprint corners. Each retrieval is one AIRS
footprint, drawn here as the instrument's 1.1 degree circular field of view
projected from the satellite onto WGS84 (user decisions 2026-11-13, D1 in
``airs-gridding-decisions.md``; ``docs/products/tropess.md``, "Footprint
model"). Nothing here reads L1B: the satellite's place comes from the L2
fields alone.

Per target (centre ``lat``/``lon``):

1. **Scan angle.** ``sensor_view_angle`` is unsigned; it is negative, left
   of the flight direction, for ``ground_pixel_index`` <= 44.
2. **Orbit phase.** A target's scan is number
   n = 135 (``granule_number_level_1b`` - 1) + ``scanline_index`` of its
   AIRS day (one L2 granule = one file = one AIRS day, 32,400 scans). The
   phase from the ascending node is u = u0 + k (n - n_mid), with u0 and k
   fitted per AIRS day to the targets' latitudes for a circular orbit at
   Aqua's inclination (``fit_phase``). ``time`` is not used: v1 RS stores it
   in 64 s steps.
3. **Scan plane.** Through the satellite's nadir, perpendicular to the
   orbit's inertial heading at u.
4. **Height.** The radius a (1 - e sin u) of a frozen orbit (perigee over
   the north) less the ellipsoid's radius under the satellite, with a from
   the fitted phase rate by Kepler's third law. ``RADIUS_AT_K0`` and
   ``ECCENTRICITY`` were read off AIRS L1B ``satheight``; the height runs
   705-720 km to 2022 and 692-700 km in 2026.
5. **Polygon.** The satellite is where a ray at the scan angle in the scan
   plane meets the target; the footprint is where the 1.1 degree cone about
   that ray meets the ellipsoid, ``VERTICES`` points on its edge.

Validated once against AIRS L1B (AIRIBRAD.005; eight granules of 2010, 2022
and 2026; 2,548 targets; ``tools/survey/airs_fov_l1b.py``): the side and
the indices exact, the bearing to nadir within 2.1 degrees of ``satazi``,
polygon areas 0.997-1.011 of those drawn from L1B's satellite position.
Left out: the beam's true shape, terrain height, and the satellite's motion
during one scan line (a 0.5 degree skew).

The verifier has its own version of this model (pyproj); the two share only
the constants below.
"""
import numpy as np

# WGS84, km
A = 6378.137
F = 1 / 298.257223563
B = A * (1 - F)
E2 = F * (2 - F)

INCLINATION = np.radians(98.2)   # Aqua, sun-synchronous
HALF_FOV = np.radians(1.1 / 2)   # README.AIRIBRAD: 1.1 degree field of view
VERTICES = 32
SCANS_PER_GRANULE = 135          # scan lines in a six-minute L1B granule
SCANS_PER_DAY = 240 * SCANS_PER_GRANULE
LEFT_PIXELS = 44                 # ground_pixel_index <= this lies left of the flight direction
# nominal phase step per scan: 8/3 s of the 16-day, 233-orbit repeat cycle
K0 = 2 * np.pi * (8 / 3) / (16 * 86400 / 233)
# orbit radius (km) at the nominal phase step, and the eccentricity (L1B satheight, 2010-06-15)
RADIUS_AT_K0 = 7082.8
ECCENTRICITY = 0.0014
# height (km) the phase is fitted at; the fit moves by under 0.01 degrees over the real range
FIT_HEIGHT = 705.3


def ecef(lat, lon, height=0.0):
    """Geodetic degrees and km above WGS84 to ECEF km, ``(..., 3)``."""
    lat, lon = np.radians(lat), np.radians(lon)
    n = A / np.sqrt(1 - E2 * np.sin(lat) ** 2)
    return np.stack([(n + height) * np.cos(lat) * np.cos(lon),
                     (n + height) * np.cos(lat) * np.sin(lon),
                     (n * (1 - E2) + height) * np.sin(lat)], axis=-1)


def _geocentric(lat):
    """Geocentric latitude (radians) of a geodetic latitude (degrees) on the ellipsoid."""
    return np.arctan((1 - E2) * np.tan(np.radians(lat)))


def _geodetic(lat_c):
    """Geodetic latitude (degrees) of a geocentric latitude (radians) on the ellipsoid."""
    return np.degrees(np.arctan(np.tan(lat_c) / (1 - E2)))


def _destination(lat, lon, bearing, angle):
    """Great-circle destination and the bearing from it back to the start; all radians."""
    sin_lat = np.sin(lat) * np.cos(angle) + np.cos(lat) * np.sin(angle) * np.cos(bearing)
    lat2 = np.arcsin(np.clip(sin_lat, -1, 1))
    lon2 = lon + np.arctan2(np.sin(bearing) * np.sin(angle) * np.cos(lat), np.cos(angle) - np.sin(lat) * sin_lat)
    back = np.arctan2(np.sin(lon - lon2) * np.cos(lat),
                      np.cos(lat2) * np.sin(lat) - np.sin(lat2) * np.cos(lat) * np.cos(lon - lon2))
    return lat2, lon2, back


def _central_angle(scan, radius, height):
    """Earth-central angle from the sub-satellite point to where a ray at ``scan`` lands."""
    return np.arcsin(np.clip((radius + height) * np.sin(scan) / radius, -1, 1)) - scan


def scan_angle(view_angle, pixel):
    """Signed scan angle (radians) from the unsigned view angle (degrees) and the pixel index."""
    return np.radians(np.asarray(view_angle, dtype='float64')) * np.where(np.asarray(pixel) <= LEFT_PIXELS, -1.0, 1.0)


def scan_number(granule_number, scanline):
    """A target's scan within its AIRS day, 0 to 32,399."""
    return SCANS_PER_GRANULE * (np.asarray(granule_number, dtype='int64') - 1) + np.asarray(scanline, dtype='int64')


def orbit_height(u, k):
    """Height above WGS84 (km) at orbit phase ``u`` (radians), for a phase step ``k`` per scan."""
    lat = np.arcsin(np.sin(INCLINATION) * np.sin(u))
    ellipsoid = A * B / np.hypot(B * np.cos(lat), A * np.sin(lat))
    return RADIUS_AT_K0 * (K0 / k) ** (2 / 3) * (1 - ECCENTRICITY * np.sin(u)) - ellipsoid


def _track(u, scan, radius, height):
    """Where a target should lie (geocentric latitude) and the bearing from it back to nadir."""
    lat_p = np.arcsin(np.sin(INCLINATION) * np.sin(u))
    heading = np.arctan2(np.cos(INCLINATION), np.sin(INCLINATION) * np.cos(u))
    # scan < 0 is the left of the heading
    bearing = heading + np.sign(scan) * np.pi / 2
    lat_t, _, back = _destination(lat_p, 0.0, bearing, _central_angle(np.abs(scan), radius, height))
    return lat_t, back


def fit_phase(n, lat, scan):
    """Fit the orbit phase of one AIRS day to its targets' latitudes.

    Args:
        n (numpy.ndarray): Each target's scan number in the day (``scan_number``).
        lat (numpy.ndarray): Geodetic latitude of its centre, degrees.
        scan (numpy.ndarray): Signed scan angle, radians (``scan_angle``).

    Returns:
        dict: ``u0`` (radians, phase at ``n_mid``), ``k`` (radians per
            scan), ``n_mid``, and ``residual`` (degrees: the largest
            distance in latitude between a target and where the fitted
            orbit puts it), ``targets`` and ``span`` (the scans the targets
            cover).
    """
    n = np.asarray(n, dtype='float64')
    lat_c = _geocentric(lat)
    radius = np.linalg.norm(ecef(lat, np.zeros_like(lat_c)), axis=-1)
    n_mid = 0.5 * (n.min() + n.max())
    x = n - n_mid

    def residual(u0, k):
        return _track(u0 + k * x, scan, radius, FIT_HEIGHT)[0] - lat_c

    # the phase is found by a scan first: the misfit has a second minimum half an orbit away
    u0 = min(np.radians(np.arange(0, 360, 2.0)), key=lambda v: np.square(residual(v, K0)).sum())
    k = K0
    for _ in range(30):
        r = residual(u0, k)
        jacobian = np.stack([(residual(u0 + 1e-6, k) - r) / 1e-6, (residual(u0, k + 1e-9) - r) / 1e-9], axis=1)
        step = np.linalg.lstsq(jacobian, -r, rcond=None)[0]
        u0, k = u0 + step[0], k + step[1]
        if abs(step[0]) < 1e-10:
            break
    return {'u0': float(u0), 'k': float(k), 'n_mid': float(n_mid),
            'residual': float(np.degrees(np.abs(residual(u0, k)).max())), 'targets': int(n.size),
            'span': float(n.max() - n.min())}


def phase(fit, n, days_ahead=0):
    """The orbit phase (radians) of scans ``n``, from a fit of this AIRS day or of another.

    Args:
        fit (dict): From ``fit_phase``.
        n (numpy.ndarray): Scan numbers in their own AIRS day.
        days_ahead (int): The scans' AIRS day less the fitted day: scans
            follow on without a break across days (240 granules of 360 s).
    """
    return fit['u0'] + fit['k'] * (np.asarray(n, dtype='float64') + days_ahead * SCANS_PER_DAY - fit['n_mid'])


def polygons(lat, lon, scan, u, k):
    """Each target's footprint: ``(n, VERTICES)`` geodetic latitude and longitude, degrees.

    Args:
        lat, lon (numpy.ndarray): The targets' centres, degrees.
        scan (numpy.ndarray): Signed scan angle, radians.
        u (numpy.ndarray): Orbit phase of each target's scan, radians.
        k (float): The fitted phase step per scan (sets the orbit's radius).

    Returns:
        tuple: ``(lat, lon)`` of the vertices, going round the line of
            sight from the point farthest from nadir. Longitudes are in
            -180..180 and are not unwrapped across the antimeridian
            (``utils.footprints.unwrap`` does that).
    """
    lat = np.asarray(lat, dtype='float64')
    lon = np.asarray(lon, dtype='float64')
    target = ecef(lat, lon)
    radius = np.linalg.norm(target, axis=-1)
    height = orbit_height(u, k)
    _, back = _track(u, scan, radius, height)
    lat_p, lon_p, _ = _destination(_geocentric(lat), np.radians(lon), back,
                                   _central_angle(np.abs(scan), radius, height))
    satellite = ecef(_geodetic(lat_p), np.degrees(lon_p), height)
    sight = target - satellite
    sight /= np.linalg.norm(sight, axis=-1, keepdims=True)
    side = np.cross(sight, satellite)
    # at nadir the line of sight runs along the satellite's position: any perpendicular will do
    flat = np.linalg.norm(side, axis=-1) < 1e-9 * np.linalg.norm(satellite, axis=-1)
    side[flat] = np.cross(sight[flat], [0.0, 0.0, 1.0])
    side /= np.linalg.norm(side, axis=-1, keepdims=True)
    up = np.cross(side, sight)
    angle = 2 * np.pi * np.arange(VERTICES) / VERTICES
    ray = (np.cos(HALF_FOV) * sight[:, None, :]
           + np.sin(HALF_FOV) * (np.cos(angle)[None, :, None] * up[:, None, :]
                                 + np.sin(angle)[None, :, None] * side[:, None, :]))
    # stretch z so the ellipsoid is a sphere of radius A; the nearer root is the ground
    stretch = np.array([1.0, 1.0, A / B])
    origin, direction = satellite[:, None, :] * stretch, ray * stretch
    dd, od, oo = (direction**2).sum(-1), (origin * direction).sum(-1), (origin**2).sum(-1)
    distance = (-od - np.sqrt(od * od - dd * (oo - A * A))) / dd
    ground = satellite[:, None, :] + distance[..., None] * ray
    vertex_lat = np.degrees(np.arctan2(ground[..., 2], (1 - E2) * np.hypot(ground[..., 0], ground[..., 1])))
    return vertex_lat, np.degrees(np.arctan2(ground[..., 1], ground[..., 0]))
