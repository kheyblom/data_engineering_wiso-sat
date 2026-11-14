"""The verifier's own version of the profile method (AIRS), independent of the build.

``verify_grid_wisosat.py`` recomputes sampled periods from L2 with this
module where the config's ``method`` is ``profile``. Nothing here calls the
build's ``utils/columns.py``, ``utils/profiles.py``, ``utils/sums.py``,
``utils/footprints.py`` or the functions of ``utils/airs_fov.py``; it
shares with the build only the footprint model's constants (the orbit and
instrument numbers, and the rule for which days' fits are sound), the
config and the gridding key. What is the same is the method
(``docs/technical/gridding-method.md``; ``docs/products/tropess.md``,
"Gridding inputs, AIRS v1"); how it is computed differs:

- **columns:** each profile on its own, layer by layer, from the
  antiderivative of a mole fraction linear in ln p (the build builds
  vectorized level weights);
- **orbit phase:** ``scipy.optimize.least_squares`` on a residual built
  from 3-D unit vectors (the build: Gauss-Newton on spherical trigonometry).
  Both use central differences and run to the least-squares minimum, so the
  two phases agree far more closely than either's search would by itself;
- **footprints:** unit-vector rotations for the scan plane and the
  satellite's place, the ellipsoid met by solving the quadratic in ECEF,
  and pyproj for every geodetic conversion;
- **sums:** pandas group-bys over the (footprint, cell) pairs shapely gives.

Both orbit-phase fits run to the least-squares minimum (central
differences, steps down to rounding), so the two phases agree to ~1e-9
degrees and the sums to ~1e-10 relative: the verifier's default ``SUM_RTOL``
holds for this method too. With one-sided differences the fits stopped
1e-7 to 6e-5 degrees apart, and statistics of sliver overlaps failed
(gridding/TESTING.md, AIRS bench).
"""
import math

import numpy as np
import pandas as pd
import pyproj  # type: ignore
import scipy.optimize  # type: ignore

from utils import airs_fov as model  # constants only

GEODETIC_TO_ECEF = pyproj.Transformer.from_crs('EPSG:4979', 'EPSG:4978', always_xy=True)
ECEF_TO_GEODETIC = pyproj.Transformer.from_crs('EPSG:4978', 'EPSG:4979', always_xy=True)
GRAVITY = 9.80665           # m s-2 (D4)
DRY_AIR = 0.0289644         # kg mol-1 (D4)
E2 = model.F * (2 - model.F)


# ------------------------------------------------------------------ columns

def integration_weights(pressure, bottom, top):
    """Per level, the weight that integrates a profile over pressure between two cuts.

    One profile: ``pressure`` (Pa, surface first, NaN where missing).
    Between adjacent valid levels f = f_lo + s (ln p - ln p_lo), whose
    integral from b to a is f_lo (a - b) + s [(a ln a - a) - (b ln b - b) -
    ln p_lo (a - b)].
    """
    weights = [0.0] * len(pressure)
    valid = [i for i, p in enumerate(pressure) if math.isfinite(p) and p > 0]
    for lower, upper in zip(valid[:-1], valid[1:]):
        p_lower, p_upper = float(pressure[lower]), float(pressure[upper])
        a, b = min(p_lower, bottom), max(p_upper, top)
        if not (a > b and p_lower > p_upper):
            continue
        bracket = (a * math.log(a) - a) - (b * math.log(b) - b) - math.log(p_lower) * (a - b)
        slope_part = bracket / (math.log(p_upper) - math.log(p_lower))
        weights[upper] += slope_part
        weights[lower] += (a - b) - slope_part
    return weights


def derive(frame, settings):
    """Every per-footprint quantity of the three groups, from the L2 profiles of one day.

    Returns:
        dict: As the build's, by the same names (they are the key's
            quantities' inputs): ``delta_d``, ``h2o``; ``level_valid`` and
            the level arrays; ``surface_valid`` and the surface arrays.
    """
    inputs, spec = settings['inputs'], settings['profile']
    pressure = frame[inputs['pressure']].astype('float64')
    ratio = frame[inputs['ratio']].astype('float64')
    h2o = frame[inputs['h2o']].astype('float64')
    apriori = frame[inputs['apriori']].astype('float64')
    kernel = np.array([np.diag(matrix) for matrix in frame[inputs['kernel']]], dtype='float64').reshape(len(pressure), -1)
    levels = [float(value) for value in spec['levels']]
    standard = float(spec['ratio_standard'])
    bottom, top = float(spec['column']['bottom']), float(spec['column']['top'])
    n, slots = pressure.shape
    per_pa = 1.0 / (GRAVITY * DRY_AIR)
    out = {name: np.full(n, np.nan) for name in ('delta_d', 'h2o', 'surface_share', 'surface_delta_d',
                                                  'surface_delta_d_apriori', 'surface_kernel_diagonal',
                                                  'surface_h2o', 'surface_pressure')}
    out.update({name: np.full((n, len(levels)), np.nan) for name in ('level_share', 'level_delta_d',
                                                                     'level_delta_d_apriori',
                                                                     'level_kernel_diagonal', 'level_h2o')})
    out['level_valid'] = np.zeros((n, len(levels)), dtype=bool)
    out['surface_valid'] = np.zeros(n, dtype=bool)

    def delta(value):
        return 1000.0 * (value / standard - 1.0)

    for i in range(n):
        p, r, q = pressure[i], ratio[i], h2o[i] * 1e-6
        written = [k for k in range(slots) if math.isfinite(p[k])]
        if not written:
            continue
        surface = written[0]
        cut = integration_weights(p, bottom, top)
        used = [k for k in range(slots) if cut[k] != 0]
        if used and all(math.isfinite(r[k]) and math.isfinite(q[k]) for k in used):
            column_h2o = sum(cut[k] * q[k] for k in used) * per_pa
            column_hdo = sum(cut[k] * r[k] * q[k] for k in used) * per_pa
            out['h2o'][i] = column_h2o
            out['delta_d'][i] = delta(column_hdo / column_h2o)
        whole = integration_weights(p, math.inf, 0.0)
        used = [k for k in range(slots) if whole[k] != 0]
        if not used or not all(math.isfinite(r[k]) and math.isfinite(q[k]) for k in used):
            continue
        for k in range(slots):
            complete = all(math.isfinite(x) for x in (r[k], h2o[i, k], apriori[i, k], kernel[i, k]))
            share = whole[k] * q[k] * per_pa
            if k == surface:
                out['surface_valid'][i] = complete
                out['surface_share'][i] = share
                out['surface_delta_d'][i] = delta(r[k])
                out['surface_delta_d_apriori'][i] = delta(apriori[i, k])
                out['surface_kernel_diagonal'][i] = kernel[i, k]
                out['surface_h2o'][i] = h2o[i, k]
                out['surface_pressure'][i] = p[k]
            elif k > surface and k >= 1:
                level = k - 1
                if not math.isclose(p[k], levels[level], rel_tol=1e-4):
                    raise ValueError(f'level slot {k} holds {p[k]} Pa above a surface, not {levels[level]} Pa')
                out['level_valid'][i, level] = complete
                out['level_share'][i, level] = share
                out['level_delta_d'][i, level] = delta(r[k])
                out['level_delta_d_apriori'][i, level] = delta(apriori[i, k])
                out['level_kernel_diagonal'][i, level] = kernel[i, k]
                out['level_h2o'][i, level] = h2o[i, k]
    return out


# ---------------------------------------------------------- the orbit model

def _unit(lat, lon):
    """Unit vectors of spherical latitude and longitude (radians), ``(..., 3)``."""
    return np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=-1)


def _east_north(lat, lon):
    east = np.stack([-np.sin(lon), np.cos(lon), np.zeros_like(lon)], axis=-1)
    north = np.stack([-np.sin(lat) * np.cos(lon), -np.sin(lat) * np.sin(lon), np.cos(lat)], axis=-1)
    return east, north


def _geocentric(lat_degrees):
    return np.arctan((1 - E2) * np.tan(np.radians(lat_degrees)))


def _target_radius(lat, lon):
    x, y, z = GEODETIC_TO_ECEF.transform(lon, lat, np.zeros_like(lat))
    return np.sqrt(x * x + y * y + z * z) / 1000.0


def _model_track(u, scan, radius, height):
    """Where the orbit puts a target (unit vector, satellite's nadir at longitude 0) and that nadir."""
    lat_p = np.arcsin(np.sin(model.INCLINATION) * np.sin(u))
    nadir = _unit(lat_p, np.zeros_like(lat_p))
    east, north = _east_north(lat_p, np.zeros_like(lat_p))
    head = np.arctan2(np.cos(model.INCLINATION), np.sin(model.INCLINATION) * np.cos(u))
    heading = np.sin(head)[:, None] * east + np.cos(head)[:, None] * north
    # the right of the heading; a negative scan angle looks left
    across = np.sign(scan)[:, None] * np.cross(heading, nadir)
    angle = np.arcsin(np.clip((radius + height) * np.sin(np.abs(scan)) / radius, -1, 1)) - np.abs(scan)
    return np.cos(angle)[:, None] * nadir + np.sin(angle)[:, None] * across, nadir, angle


def signed_scan(view_angle, pixel):
    return np.radians(view_angle.astype('float64')) * np.where(pixel <= model.LEFT_PIXELS, -1.0, 1.0)


def scan_count(granule_number, scanline):
    return model.SCANS_PER_GRANULE * (granule_number.astype('int64') - 1) + scanline.astype('int64')


def fit(n, lat, scan):
    """The orbit phase of one AIRS day from its targets' latitudes, by scipy.

    Returns:
        dict: ``u0``, ``k``, ``n_mid``, ``targets``, ``span``, ``residual``
            (degrees), as the build's fit reports them.
    """
    n = n.astype('float64')
    target_lat = _geocentric(lat)
    radius = _target_radius(lat, np.zeros_like(lat))
    n_mid = 0.5 * (n.min() + n.max())
    height = np.full(n.shape, model.FIT_HEIGHT)

    # the phase rate is fitted as its phase over the half-span of the scans, so both parameters
    # move the targets by about as much per unit and the solver's steps are well scaled
    reach = max(float(np.abs(n - n_mid).max()), 1.0)

    def residual(parameters):
        placed, _, _ = _model_track(parameters[0] + parameters[1] * (n - n_mid) / reach, scan, radius, height)
        return np.arcsin(np.clip(placed[:, 2], -1, 1)) - target_lat

    start = min(np.radians(np.arange(0, 360, 2.0)),
                key=lambda u0: float(np.square(residual((u0, model.K0 * reach))).sum()))
    # central differences and the tightest tolerances, twice: the least-squares minimum itself,
    # which the build's fit also reaches, not wherever a looser search would stop
    best = np.array([start, model.K0 * reach])
    for _ in range(2):
        best = scipy.optimize.least_squares(residual, best, jac='3-point', xtol=1e-15, ftol=1e-15, gtol=1e-15,
                                            max_nfev=2000).x
    return {'u0': float(best[0]), 'k': float(best[1] / reach), 'n_mid': float(n_mid), 'targets': int(n.size),
            'span': float(n.max() - n.min()), 'residual': float(np.degrees(np.abs(residual(best)).max()))}


def sound(result):
    return (result is not None and result['targets'] >= model.MIN_TARGETS and result['span'] >= model.MIN_SPAN
            and result['residual'] <= model.MAX_RESIDUAL)


def polygons(lat, lon, scan, n, result, days_ahead):
    """Each target's footprint polygon, ``(targets, VERTICES)`` geodetic latitude and longitude."""
    u = result['u0'] + result['k'] * (n.astype('float64') + days_ahead * model.SCANS_PER_DAY - result['n_mid'])
    lat_p = np.arcsin(np.sin(model.INCLINATION) * np.sin(u))
    b_axis = model.A * (1 - model.F)
    ellipsoid = model.A * b_axis / np.hypot(b_axis * np.cos(lat_p), model.A * np.sin(lat_p))
    height = (model.RADIUS_AT_K0 * (model.K0 / result['k']) ** (2 / 3) * (1 - model.ECCENTRICITY * np.sin(u))
              - ellipsoid)
    radius = _target_radius(lat, lon)
    placed, nadir, angle = _model_track(u, scan, radius, height)
    # the bearing, at where the orbit puts the target, back along the scan line to nadir
    toward = nadir - (nadir * placed).sum(-1, keepdims=True) * placed
    toward /= np.linalg.norm(toward, axis=-1, keepdims=True)
    placed_lat, placed_lon = np.arcsin(np.clip(placed[:, 2], -1, 1)), np.arctan2(placed[:, 1], placed[:, 0])
    east, north = _east_north(placed_lat, placed_lon)
    bearing = np.arctan2((toward * east).sum(-1), (toward * north).sum(-1))
    # the same bearing and distance from the real target give the real nadir
    here_lat, here_lon = _geocentric(lat), np.radians(lon)
    here = _unit(here_lat, here_lon)
    east, north = _east_north(here_lat, here_lon)
    step = np.sin(bearing)[:, None] * east + np.cos(bearing)[:, None] * north
    below = np.cos(angle)[:, None] * here + np.sin(angle)[:, None] * step
    nadir_lat = np.degrees(np.arctan(np.tan(np.arcsin(np.clip(below[:, 2], -1, 1))) / (1 - E2)))
    nadir_lon = np.degrees(np.arctan2(below[:, 1], below[:, 0]))
    satellite = np.stack(GEODETIC_TO_ECEF.transform(nadir_lon, nadir_lat, height * 1000.0), axis=-1) / 1000.0
    target = np.stack(GEODETIC_TO_ECEF.transform(lon, lat, np.zeros_like(lat)), axis=-1) / 1000.0
    sight = target - satellite
    sight /= np.linalg.norm(sight, axis=-1, keepdims=True)
    side = np.cross(sight, satellite)
    flat = np.linalg.norm(side, axis=-1) < 1e-9 * np.linalg.norm(satellite, axis=-1)
    side[flat] = np.cross(sight[flat], [0.0, 0.0, 1.0])
    side /= np.linalg.norm(side, axis=-1, keepdims=True)
    up = np.cross(side, sight)
    out_lat = np.empty((lat.size, model.VERTICES))
    out_lon = np.empty((lat.size, model.VERTICES))
    for vertex in range(model.VERTICES):
        turn = 2 * math.pi * vertex / model.VERTICES
        ray = (math.cos(model.HALF_FOV) * sight
               + math.sin(model.HALF_FOV) * (math.cos(turn) * up + math.sin(turn) * side))
        # x²/A² + y²/A² + z²/B² = 1 along satellite + t ray: the nearer root
        qa = (ray[:, 0] ** 2 + ray[:, 1] ** 2) / model.A**2 + ray[:, 2] ** 2 / b_axis**2
        qb = (satellite[:, 0] * ray[:, 0] + satellite[:, 1] * ray[:, 1]) / model.A**2 + satellite[:, 2] * ray[:, 2] / b_axis**2
        qc = (satellite[:, 0] ** 2 + satellite[:, 1] ** 2) / model.A**2 + satellite[:, 2] ** 2 / b_axis**2 - 1
        t = (-qb - np.sqrt(qb * qb - qa * qc)) / qa
        ground = (satellite + t[:, None] * ray) * 1000.0
        out_lon[:, vertex], out_lat[:, vertex], _ = ECEF_TO_GEODETIC.transform(ground[:, 0], ground[:, 1], ground[:, 2])
    return out_lat, out_lon


class Phases:
    """Each AIRS day's fit and the carry-over rule, worked out again from the L2 arrays.

    Args:
        l2: The verifier's ``IndependentL2``.
        settings (dict): The config (``footprint`` names the L2 fields).
    """

    def __init__(self, l2, settings):
        self.l2, self.fields = l2, settings['footprint']
        geo = l2.group('geolocation')
        index = pd.DataFrame({'id': [str(value) for value in geo['granule_id'][:]],
                              'start': geo['granule_obs_start'][:], 'count': geo['granule_obs_count'][:]})
        index = index[index['count'] > 0].reset_index(drop=True)
        index['day'] = pd.to_datetime(index['id'], format='%Y%m%d')
        self.index, self.cache = index, {}

    def _own(self, k):
        if k not in self.cache:
            row = self.index.iloc[k]
            result = None
            if row['count'] >= 3:
                window = slice(int(row['start']), int(row['start'] + row['count']))
                read = {name: self.l2.group(store)[store][window] for name, store in self.fields.items()}
                lat = self.l2.group('geolocation')['lat'][window].astype('float64')
                result = fit(scan_count(read['granule'], read['scanline']), lat,
                             signed_scan(read['view_angle'], read['pixel']))
            self.cache[k] = result
        return self.cache[k]

    def resolve(self, k):
        """The fit day ``k`` uses and how many days ahead of it ``k`` is."""
        if sound(self._own(k)):
            return self._own(k), 0
        gap = (self.index['day'] - self.index['day'].iloc[k]).dt.days
        for j in gap.abs().sort_values(kind='stable').index:
            if j == k or abs(gap[j]) > model.MAX_CARRY_DAYS:
                continue
            if sound(self._own(j)):
                return self._own(j), int(-gap[j])
        raise RuntimeError(f'AIRS day {self.index["id"].iloc[k]}: no sound fit within {model.MAX_CARRY_DAYS} days')

    def polygons(self, frame):
        """The footprint polygons of a day's rows (``frame`` holds ``obs``, ``lat``, ``lon`` and the fields)."""
        obs = frame['obs']
        granule = np.searchsorted(self.index['start'].to_numpy(), obs, side='right') - 1
        scan = signed_scan(frame[self.fields['view_angle']], frame[self.fields['pixel']])
        n = scan_count(frame[self.fields['granule']], frame[self.fields['scanline']])
        lat, lon = frame['lat'].astype('float64'), frame['lon'].astype('float64')
        out_lat = np.empty((obs.size, model.VERTICES))
        out_lon = np.empty((obs.size, model.VERTICES))
        for k in np.unique(granule):
            member = granule == k
            result, days_ahead = self.resolve(int(k))
            out_lat[member], out_lon[member] = polygons(lat[member], lon[member], scan[member], n[member], result,
                                                        days_ahead)
        return out_lat, out_lon


# --------------------------------------------------------------------- sums

LEVEL_TERMS = {'level_weight': None, 'level_weight_delta_d': 'level_delta_d',
               'level_weight_delta_d_apriori': 'level_delta_d_apriori',
               'level_weight_kernel_diagonal': 'level_kernel_diagonal'}
SURFACE_TERMS = {'surface_weight': None, 'surface_weight_delta_d': 'surface_delta_d',
                 'surface_weight_delta_d_apriori': 'surface_delta_d_apriori',
                 'surface_weight_kernel_diagonal': 'surface_kernel_diagonal',
                 'surface_weight_pressure': 'surface_pressure'}


def block_sums(pairs, derived, whole, n_cells):
    """The three groups' per-cell sums of one block of (footprint, cell, area) pairs.

    Returns:
        tuple: ``(column, level, surface)`` DataFrames; ``column`` and
            ``surface`` indexed by flat cell, ``level`` by
            ``level * n_cells + cell``; each with a ``count`` column.
    """
    foot = pairs['foot'].to_numpy()
    column = pairs[['cell', 'foot', 'area']].copy()
    column['weight'] = column['area'] * 1e6 * derived['h2o'][foot]
    total = column.groupby('foot')['weight'].transform('sum')
    w, d = column['weight'], derived['delta_d'][foot]
    column = column.assign(weight_delta_d=w * d, weight_delta_d_squared=w * d * d, weight_squared=w * w,
                           weight_footprint_area=w * whole[foot], weight_total=w * total, count=1)
    column = column.drop(columns='foot').groupby('cell').sum()

    levels = []
    for level in range(derived['level_valid'].shape[1]):
        member = pairs[derived['level_valid'][foot, level]]
        f = member['foot'].to_numpy()
        part = pd.DataFrame({'index': level * n_cells + member['cell'].to_numpy(), 'level_area': member['area'].to_numpy()})
        weight = part['level_area'] * 1e6 * derived['level_share'][f, level]
        for name, source in LEVEL_TERMS.items():
            part[name] = weight if source is None else weight * derived[source][f, level]
        part['level_weight_delta_d_squared'] = weight * derived['level_delta_d'][f, level] ** 2
        part['level_area_h2o'] = part['level_area'] * derived['level_h2o'][f, level]
        part['count'] = 1
        levels.append(part)
    level = pd.concat(levels).groupby('index').sum()

    member = pairs[derived['surface_valid'][foot]]
    f = member['foot'].to_numpy()
    surface = pd.DataFrame({'cell': member['cell'].to_numpy(), 'surface_area': member['area'].to_numpy()})
    weight = surface['surface_area'] * 1e6 * derived['surface_share'][f]
    for name, source in SURFACE_TERMS.items():
        surface[name] = weight if source is None else weight * derived[source][f]
    surface['surface_area_h2o'] = surface['surface_area'] * derived['surface_h2o'][f]
    surface['count'] = 1
    return column, level, surface.groupby('cell').sum()


COLUMN_SUMS = ('area', 'weight', 'weight_delta_d', 'weight_delta_d_squared', 'weight_squared',
               'weight_footprint_area', 'weight_total')
LEVEL_SUMS = (*LEVEL_TERMS, 'level_weight_delta_d_squared', 'level_area', 'level_area_h2o')
SURFACE_SUMS = (*SURFACE_TERMS, 'surface_area', 'surface_area_h2o')


def empty_groups():
    """The three groups' DataFrames for a period in which nothing was gridded."""
    return tuple(pd.DataFrame({name: pd.Series(dtype='float64') for name in (*names, 'count')})
                 for names in (COLUMN_SUMS, LEVEL_SUMS, SURFACE_SUMS))


def statistics(column, level, surface, cell_area, n_cells, n_levels):
    """Every quantity of the key on the whole grid, from the three groups' summed DataFrames.

    Returns:
        dict: quantity -> flat array (``n_cells``, or ``n_levels * n_cells``
            for the level group, level first).
    """
    def dense(frame, size):
        out = {name: np.zeros(size) for name in frame.columns}
        index = frame.index.to_numpy().astype('int64')
        for name in frame.columns:
            out[name][index] = frame[name].to_numpy()
        return out

    c, lv, s = dense(column, n_cells), dense(level, n_levels * n_cells), dense(surface, n_cells)
    count, level_count, surface_count = (x['count'].astype('int64') for x in (c, lv, s))
    with np.errstate(invalid='ignore', divide='ignore'):
        w = np.where(count > 0, c['weight'], np.nan)
        mean = c['weight_delta_d'] / w
        lw = np.where(level_count > 0, lv['level_weight'], np.nan)
        sw = np.where(surface_count > 0, s['surface_weight'], np.nan)
        out = {
            'delta_d': mean, 'spread': np.sqrt(np.clip(c['weight_delta_d_squared'] / w - mean**2, 0, None)),
            'n_eff': w**2 / c['weight_squared'], 'count': count, 'h2o': w / c['area'] / 1e6,
            'coverage': np.where(count > 0, c['area'], np.nan) / cell_area,
            'footprint_area': c['weight_footprint_area'] / w,
            'level_delta_d': lv['level_weight_delta_d'] / lw,
            'level_delta_d_apriori': lv['level_weight_delta_d_apriori'] / lw,
            'level_kernel_diagonal': lv['level_weight_kernel_diagonal'] / lw,
            'level_h2o': lv['level_area_h2o'] / np.where(level_count > 0, lv['level_area'], np.nan),
            'level_count': level_count,
            'surface_delta_d': s['surface_weight_delta_d'] / sw,
            'surface_delta_d_apriori': s['surface_weight_delta_d_apriori'] / sw,
            'surface_kernel_diagonal': s['surface_weight_kernel_diagonal'] / sw,
            'surface_h2o': s['surface_area_h2o'] / np.where(surface_count > 0, s['surface_area'], np.nan),
            'surface_count': surface_count,
            'surface_pressure': s['surface_weight_pressure'] / sw,
        }
    out.update({name: c[name] for name in COLUMN_SUMS})
    out.update({name: lv[name] for name in LEVEL_SUMS})
    return out
