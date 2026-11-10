"""Per-cell sums of one day, their accumulation over a period, and the statistics.

The method is gridding-method.md, Sections 6 and 8 (decided 2026-11-09):
each (footprint, cell) overlap contributes with weight w = a · H, its
overlap area times its H2O column, here in mol (km² × 1e6 × mol m-2; the
key's unit). Every sum adds exactly over days, so a period's sums are its
days' added, and the statistics are formed only at the end.

Quantity names ('weight_delta_d', 'spread') are the keys of
``nomenclature-key_grid.md``; what each stores is there.
"""
import numpy as np

from utils import nomenclature

M2_PER_KM2 = 1e6


def sum_names():
    """The sums, in key order; with 'count' they are a period's whole state."""
    return nomenclature.quantity_names('sum')


def day_sums(footprint, cell, km2, delta_d, sigma, h2o, footprint_area):
    """One day's sums over its occupied cells.

    Args:
        footprint (numpy.ndarray): For each (footprint, cell) overlap, the
            footprint's position in the per-footprint arrays.
        cell (numpy.ndarray): The flat cell.
        km2 (numpy.ndarray): The overlap area, km².
        delta_d, sigma, h2o, footprint_area (numpy.ndarray): Per footprint:
            δD (1e-3), its random uncertainty (1e-3), H2O column (mol m-2)
            and whole area (km²).

    Returns:
        tuple: ``(cells, count, sums)``: the occupied flat cells (sorted),
            the int64 count of contributions per cell, and a float64
            ``(len(sum_names()), cells.size)`` array.
    """
    w = km2 * M2_PER_KM2 * h2o[footprint]
    # W: each footprint's weight over every cell of the grid (option 3)
    total = np.bincount(footprint, weights=w, minlength=delta_d.size)[footprint]
    d, variance, area = delta_d[footprint], sigma[footprint] ** 2, footprint_area[footprint]
    terms = {
        'area': km2,
        'weight': w,
        'weight_delta_d': w * d,
        'weight_delta_d_squared': w * d**2,
        'weight_squared': w**2,
        'weight_squared_variance': w**2 * variance,
        'weight_footprint_area': w * area,
        'weight_total': w * total,
        'weight_total_variance': w * total * variance,
    }
    cells, inverse, count = np.unique(cell, return_inverse=True, return_counts=True)
    sums = np.stack([np.bincount(inverse, weights=terms[name], minlength=cells.size) for name in sum_names()])
    return cells, count.astype('int64'), sums


class Accumulator:
    """A period's sums on the whole grid, added day by day.

    Dense: ``(len(sum_names()), n_cells)`` float64 plus an int64 count. At
    0.1° that is ~0.5 GB per (grid, frequency), at 1° ~5 MB.
    """

    def __init__(self, n_cells):
        self.n_cells = n_cells
        self.reset()

    def reset(self):
        self.count = np.zeros(self.n_cells, dtype='int64')
        self.sums = np.zeros((len(sum_names()), self.n_cells))
        self.days = 0

    def add(self, cells, count, sums):
        """Add one day's ``day_sums`` (its cells are unique, so plain indexing adds)."""
        self.count[cells] += count
        self.sums[:, cells] += sums
        self.days += 1


def statistics(count, sums, cell_area_km2):
    """Every statistic of the key from the sums, on the whole grid.

    Cells with no contribution are NaN (count 0). The formulas are the
    key's (and Section 6's).

    Args:
        count (numpy.ndarray): int64 contributions per cell.
        sums (numpy.ndarray): ``(len(sum_names()), n)`` float64.
        cell_area_km2 (numpy.ndarray): Each cell's true area, km².

    Returns:
        dict: quantity -> array (float64, or int64 for 'count').
    """
    s = dict(zip(sum_names(), sums))
    occupied = count > 0
    with np.errstate(divide='ignore', invalid='ignore'):
        weight = np.where(occupied, s['weight'], np.nan)
        mean = s['weight_delta_d'] / weight
        return {
            'delta_d': mean,
            'standard_error': np.sqrt(s['weight_squared_variance']) / weight,
            'spread': np.sqrt(np.maximum(s['weight_delta_d_squared'] / weight - mean**2, 0)),
            'n_eff': weight**2 / s['weight_squared'],
            'count': count,
            'h2o': weight / s['area'] / M2_PER_KM2,
            'coverage': np.where(occupied, s['area'], np.nan) / cell_area_km2,
            'footprint_area': s['weight_footprint_area'] / weight,
        }
