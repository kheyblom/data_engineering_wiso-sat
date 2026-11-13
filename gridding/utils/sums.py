"""Per-cell sums of one day, their accumulation over a period, and the statistics.

The method is gridding-method.md, Sections 6 and 8 (decided 2026-11-09):
each (footprint, cell) overlap contributes with weight w = a · H, its
overlap area times its H2O column, here in mol (km² × 1e6 × mol m-2; the
key's unit). Every sum adds exactly over days, so a period's sums are its
days' added, and the statistics are formed only at the end.

Quantity names ('weight_delta_d', 'spread') are the keys of the gridding
key in use (``utils/nomenclature.py``); what each stores is there. Which
sums and statistics are built follows from the key:

- **column group** (every key): the sums of Section 6. A key without the
  standard error has no σ sums, and the build is given no σ (a sensor with
  no valid noise-only σ; method Section 7).
- **level and surface groups** (a key with a ``group`` column; the profile
  method, AIRS decisions D2a, D4 and D9): per vertical level, and at each
  retrieval's surface level, the weight is the overlap area times the H2O
  partial column of that level's layer. Their sums are linear in the
  overlap area. The surface group stores statistics only (D9, 9.2), so its
  sums are kept here for the period and not written.
"""
import numpy as np

from utils import nomenclature

M2_PER_KM2 = 1e6
# the level group's sums, in the order they are held; the key stores those it names
LEVEL_SUMS = ('level_weight', 'level_weight_delta_d', 'level_weight_delta_d_squared',
              'level_weight_delta_d_apriori', 'level_weight_kernel_diagonal', 'level_area', 'level_area_h2o')
# the surface group's sums: held for the period, never stored (D9, 9.2)
SURFACE_SUMS = ('surface_weight', 'surface_weight_delta_d', 'surface_weight_delta_d_apriori',
                'surface_weight_kernel_diagonal', 'surface_weight_pressure', 'surface_area', 'surface_area_h2o')
# σ sums: built only where the key names them
SIGMA_SUMS = ('weight_squared_variance', 'weight_total_variance')


def sum_names():
    """The column group's sums, in key order; with 'count' they are a period's whole column state."""
    return nomenclature.quantity_names('sum', 'column')


def day_sums(footprint, cell, km2, delta_d, sigma, h2o, footprint_area):
    """One day's column sums over its occupied cells.

    Args:
        footprint (numpy.ndarray): For each (footprint, cell) overlap, the
            footprint's position in the per-footprint arrays.
        cell (numpy.ndarray): The flat cell.
        km2 (numpy.ndarray): The overlap area, km².
        delta_d, sigma, h2o, footprint_area (numpy.ndarray): Per footprint:
            δD (1e-3), its random uncertainty (1e-3; None where the key has
            no σ sums), H2O column (mol m-2) and whole area (km²).

    Returns:
        tuple: ``(cells, count, sums)``: the occupied flat cells (sorted),
            the int64 count of contributions per cell, and a float64
            ``(len(sum_names()), cells.size)`` array.

    Raises:
        ValueError: If the key names a σ sum and no σ is given.
    """
    names = sum_names()
    if sigma is None and any(name in SIGMA_SUMS for name in names):
        raise ValueError('the gridding key has σ sums but the config names no delta_d_uncertainty input')
    w = km2 * M2_PER_KM2 * h2o[footprint]
    # W: each footprint's weight over every cell of the grid (option 3)
    total = np.bincount(footprint, weights=w, minlength=delta_d.size)[footprint]
    d, area = delta_d[footprint], footprint_area[footprint]
    terms = {
        'area': km2,
        'weight': w,
        'weight_delta_d': w * d,
        'weight_delta_d_squared': w * d**2,
        'weight_squared': w**2,
        'weight_footprint_area': w * area,
        'weight_total': w * total,
    }
    if sigma is not None:
        variance = sigma[footprint] ** 2
        terms['weight_squared_variance'] = w**2 * variance
        terms['weight_total_variance'] = w * total * variance
    cells, inverse, count = np.unique(cell, return_inverse=True, return_counts=True)
    sums = np.stack([np.bincount(inverse, weights=terms[name], minlength=cells.size) for name in names])
    return cells, count.astype('int64'), sums


def profile_sums(footprint, cell, km2, derived, n_cells):
    """One day's level and surface sums (the profile method).

    Args:
        footprint, cell, km2 (numpy.ndarray): As ``day_sums``.
        derived (dict): Per footprint, from ``utils.profiles.derive``:
            ``level_valid`` (n, levels) and the level arrays; ``surface_valid``
            (n,) and the surface arrays.
        n_cells (int): Cells in the grid.

    Returns:
        dict: ``level_index`` (level * n_cells + cell, sorted),
            ``level_count``, ``level_sums`` (``(len(LEVEL_SUMS), index.size)``);
            ``surface_cells``, ``surface_count``, ``surface_sums``.
    """
    pair, level = np.nonzero(derived['level_valid'][footprint])
    f, a = footprint[pair], km2[pair]
    w = a * M2_PER_KM2 * derived['level_share'][f, level]
    d = derived['level_delta_d'][f, level]
    terms = {
        'level_weight': w,
        'level_weight_delta_d': w * d,
        'level_weight_delta_d_squared': w * d**2,
        'level_weight_delta_d_apriori': w * derived['level_delta_d_apriori'][f, level],
        'level_weight_kernel_diagonal': w * derived['level_kernel_diagonal'][f, level],
        'level_area': a,
        'level_area_h2o': a * derived['level_h2o'][f, level],
    }
    index, inverse, count = np.unique(level.astype('int64') * n_cells + cell[pair], return_inverse=True,
                                      return_counts=True)
    level_sums = np.stack([np.bincount(inverse, weights=terms[name], minlength=index.size) for name in LEVEL_SUMS])

    pair = np.flatnonzero(derived['surface_valid'][footprint])
    f, a = footprint[pair], km2[pair]
    w = a * M2_PER_KM2 * derived['surface_share'][f]
    terms = {
        'surface_weight': w,
        'surface_weight_delta_d': w * derived['surface_delta_d'][f],
        'surface_weight_delta_d_apriori': w * derived['surface_delta_d_apriori'][f],
        'surface_weight_kernel_diagonal': w * derived['surface_kernel_diagonal'][f],
        'surface_weight_pressure': w * derived['surface_pressure'][f],
        'surface_area': a,
        'surface_area_h2o': a * derived['surface_h2o'][f],
    }
    cells, inverse, surface_count = np.unique(cell[pair], return_inverse=True, return_counts=True)
    surface_sums = np.stack([np.bincount(inverse, weights=terms[name], minlength=cells.size)
                             for name in SURFACE_SUMS])
    return {'level_index': index, 'level_count': count.astype('int64'), 'level_sums': level_sums,
            'surface_cells': cells, 'surface_count': surface_count.astype('int64'), 'surface_sums': surface_sums}


class Accumulator:
    """A period's sums on the whole grid, added day by day.

    Dense: ``(len(sum_names()), n_cells)`` float64 plus an int64 count. At
    0.1° that is ~0.5 GB per (grid, frequency), at 1° ~5 MB. With levels,
    also ``(len(LEVEL_SUMS), n_levels, n_cells)`` and the surface sums.

    Args:
        n_cells (int): Cells in the grid.
        n_levels (int): Vertical levels of the level group; 0 for a key
            without one.
    """

    def __init__(self, n_cells, n_levels=0):
        self.n_cells, self.n_levels = n_cells, n_levels
        self.reset()

    def reset(self):
        self.count = np.zeros(self.n_cells, dtype='int64')
        self.sums = np.zeros((len(sum_names()), self.n_cells))
        self.days = 0
        if self.n_levels:
            self.level_count = np.zeros(self.n_levels * self.n_cells, dtype='int64')
            self.level_sums = np.zeros((len(LEVEL_SUMS), self.n_levels * self.n_cells))
            self.surface_count = np.zeros(self.n_cells, dtype='int64')
            self.surface_sums = np.zeros((len(SURFACE_SUMS), self.n_cells))

    def add(self, cells, count, sums, profile=None):
        """Add one day's ``day_sums``, and its ``profile_sums`` where the key has levels.

        Each day's cells are unique, so plain indexing adds.
        """
        self.count[cells] += count
        self.sums[:, cells] += sums
        self.days += 1
        if self.n_levels:
            self.level_count[profile['level_index']] += profile['level_count']
            self.level_sums[:, profile['level_index']] += profile['level_sums']
            self.surface_count[profile['surface_cells']] += profile['surface_count']
            self.surface_sums[:, profile['surface_cells']] += profile['surface_sums']


def statistics(count, sums, cell_area_km2):
    """Every column statistic of the key from the sums, on the whole grid.

    Cells with no contribution are NaN (count 0). The formulas are the
    key's (and Section 6's).

    Args:
        count (numpy.ndarray): int64 contributions per cell.
        sums (numpy.ndarray): ``(len(sum_names()), n)`` float64.
        cell_area_km2 (numpy.ndarray): Each cell's true area, km².

    Returns:
        dict: quantity -> array (float64, or int64 for 'count'), for the
            key's column statistics.
    """
    s = dict(zip(sum_names(), sums))
    occupied = count > 0
    with np.errstate(divide='ignore', invalid='ignore'):
        weight = np.where(occupied, s['weight'], np.nan)
        mean = s['weight_delta_d'] / weight
        stats = {
            'delta_d': mean,
            'spread': np.sqrt(np.maximum(s['weight_delta_d_squared'] / weight - mean**2, 0)),
            'n_eff': weight**2 / s['weight_squared'],
            'count': count,
            'h2o': weight / s['area'] / M2_PER_KM2,
            'coverage': np.where(occupied, s['area'], np.nan) / cell_area_km2,
            'footprint_area': s['weight_footprint_area'] / weight,
        }
        if 'weight_squared_variance' in s:
            stats['standard_error'] = np.sqrt(s['weight_squared_variance']) / weight
    return {name: stats[name] for name in nomenclature.quantity_names('statistic', 'column')}


def profile_statistics(level_count, level_sums, surface_count, surface_sums):
    """The level and surface statistics from their sums.

    Args:
        level_count (numpy.ndarray): int64, any shape ending in cells.
        level_sums (numpy.ndarray): ``(len(LEVEL_SUMS), ...)`` float64.
        surface_count, surface_sums (numpy.ndarray): The surface group's.

    Returns:
        dict: quantity -> array, for the key's level and surface statistics.
            NaN where nothing contributed; the counts are int64.
    """
    s = dict(zip(LEVEL_SUMS, level_sums))
    t = dict(zip(SURFACE_SUMS, surface_sums))
    with np.errstate(divide='ignore', invalid='ignore'):
        weight = np.where(level_count > 0, s['level_weight'], np.nan)
        surface = np.where(surface_count > 0, t['surface_weight'], np.nan)
        stats = {
            'level_delta_d': s['level_weight_delta_d'] / weight,
            'level_delta_d_apriori': s['level_weight_delta_d_apriori'] / weight,
            'level_kernel_diagonal': s['level_weight_kernel_diagonal'] / weight,
            'level_h2o': s['level_area_h2o'] / np.where(level_count > 0, s['level_area'], np.nan),
            'level_count': level_count,
            'surface_delta_d': t['surface_weight_delta_d'] / surface,
            'surface_delta_d_apriori': t['surface_weight_delta_d_apriori'] / surface,
            'surface_kernel_diagonal': t['surface_weight_kernel_diagonal'] / surface,
            'surface_h2o': t['surface_area_h2o'] / np.where(surface_count > 0, t['surface_area'], np.nan),
            'surface_count': surface_count,
            'surface_pressure': t['surface_weight_pressure'] / surface,
        }
    wanted = nomenclature.quantity_names('statistic', 'level') + nomenclature.quantity_names('statistic', 'surface')
    return {name: stats[name] for name in wanted}


def fields(accumulator, cell_area_km2):
    """Every quantity of the key for a closed period, on the flat grid.

    Returns:
        dict: quantity -> float64 or int64 array: ``(n_cells,)`` for the
            column and surface groups, ``(n_levels, n_cells)`` for the level
            group.
    """
    out = dict(zip(sum_names(), accumulator.sums.copy()))
    out.update(statistics(accumulator.count, accumulator.sums, cell_area_km2))
    if accumulator.n_levels:
        shape = (accumulator.n_levels, accumulator.n_cells)
        stored = nomenclature.quantity_names('sum', 'level')
        unknown = [name for name in stored if name not in LEVEL_SUMS]
        if unknown or nomenclature.quantity_names('sum', 'surface'):
            raise ValueError(f'the gridding key names sums this build does not form: {unknown} '
                             f'{nomenclature.quantity_names("sum", "surface")}')
        for name in stored:
            out[name] = accumulator.level_sums[LEVEL_SUMS.index(name)].reshape(shape).copy()
        stats = profile_statistics(accumulator.level_count, accumulator.level_sums, accumulator.surface_count,
                                   accumulator.surface_sums)
        out.update({name: values.reshape(shape) if name.startswith('level_') else values
                    for name, values in stats.items()})
    return out
