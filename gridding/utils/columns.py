"""Partial columns from a retrieval's profiles: the column operator.

For sensors whose gridded quantities are computed here from L2 profiles
(user decision 2026-11-13, CLAUDE.md "Derived inputs are computed here";
AIRS decisions D2 and D4 in ``airs-gridding-decisions.md``).

A profile is given on levels, surface first, with missing (NaN) levels below
the surface; the lowest valid level holds the surface pressure
(``docs/products/tropess.md`` R10). Between adjacent valid levels a mole
fraction is taken linear in ln p (D2, 2.1), and a column between two
pressures is its integral over pressure (hydrostatic):

    column = (1 / (g M)) ∫ f dp,   f = f_i + (f_i+1 - f_i) ln(p / p_i) / ln(p_i+1 / p_i)

The integral of each layer is exact (no quadrature), and it is linear in the
level values, so a column is ``(weights * f).sum(level)`` with weights that
depend only on the pressures and the two cuts: ``layer_weights``. That
gives, from one set of weights:

- the H2O partial column, ``weights @ q`` (mol m-2 with ``MOL_M2_PER_PA``);
- the HDO partial column the same way from ``r * q``, so the column δD is
  the ratio of the two (g and M cancel);
- each level's share of the column, ``weights * q``: the H2O partial column
  of that level's layer, the weight of the per-level sums (D2, 2.7). The
  shares add to the column exactly.

The cuts are exact: a column from 850 to 250 hPa starts at 850 hPa (or at
the surface where that is higher up) wherever the levels fall.

Convention for the absolute column (D4): q is the dry-air mole fraction,
integrated with standard gravity and the dry-air molar mass; TROPESS
documents neither. MUSES's own v2 ``column_air`` equals Δp / (g M) to 0.3%.
"""
import numpy as np

STANDARD_GRAVITY = 9.80665      # m s-2
DRY_AIR_MOLAR_MASS = 0.0289644  # kg mol-1
# mol m-2 of air per Pa of pressure thickness
MOL_M2_PER_PA = 1.0 / (STANDARD_GRAVITY * DRY_AIR_MOLAR_MASS)


def layer_weights(pressure, bottom=np.inf, top=0.0):
    """Weights that integrate a profile over pressure between two cuts.

    Args:
        pressure (numpy.ndarray): ``(n, levels)``, surface first, any
            pressure unit; NaN on levels below the surface (and anywhere a
            level is missing).
        bottom (float): The lower cut, in ``pressure``'s unit; the surface
            where that lies above it. Default: the surface.
        top (float): The upper cut. Default: the highest level.

    Returns:
        numpy.ndarray: ``(n, levels)`` float64 in ``pressure``'s unit:
            ``(weights * f).sum(axis=1)`` is ∫ f dp from the lower cut to
            the upper for f linear in ln p between adjacent valid levels.
            Zero on missing levels; all zero where the cuts hold no layer.
    """
    p = np.asarray(pressure, dtype='float64')
    n, levels = p.shape
    weights = np.zeros((n, levels))
    valid = np.isfinite(p) & (p > 0)
    # each valid level's next valid level above it (a missing level between two valid ones is skipped)
    index = np.where(valid, np.arange(levels), levels)
    above = np.minimum.accumulate(index[:, ::-1], axis=1)[:, ::-1]
    above = np.concatenate([above[:, 1:], np.full((n, 1), levels)], axis=1)
    rows, lower = np.nonzero(valid & (above < levels))
    upper = above[rows, lower]
    p_low, p_up = p[rows, lower], p[rows, upper]
    a = np.minimum(p_low, bottom)
    b = np.maximum(p_up, top)
    inside = (a > b) & (p_low > p_up)
    rows, lower, upper, p_low, p_up, a, b = (x[inside] for x in (rows, lower, upper, p_low, p_up, a, b))
    # f = f_low + (f_up - f_low) t, t = ln(p / p_low) / ln(p_up / p_low); ∫ t dp is exact
    span = np.log(p_up / p_low)
    with np.errstate(divide='ignore', invalid='ignore'):
        t_integral = (a * np.log(a / p_low) - a - b * np.log(b / p_low) + b) / span
    np.add.at(weights, (rows, upper), t_integral)
    np.add.at(weights, (rows, lower), (a - b) - t_integral)
    return weights


def surface_level(pressure):
    """The index of each profile's lowest valid level (its surface), -1 if it has none."""
    valid = np.isfinite(np.asarray(pressure, dtype='float64'))
    return np.where(valid.any(axis=1), valid.argmax(axis=1), -1)


def partial_columns(pressure_pa, q, ratio, bottom_pa=np.inf, top_pa=0.0):
    """H2O partial column and its δD-forming ratio between two pressures.

    Args:
        pressure_pa (numpy.ndarray): ``(n, levels)`` in Pa, surface first.
        q (numpy.ndarray): H2O dry-air mole fraction, mol mol-1 (not 1e-6).
        ratio (numpy.ndarray): HDO/H2O mole ratio on the same levels.
        bottom_pa, top_pa (float): The cuts, Pa.

    Returns:
        tuple: ``(h2o, ratio_column, shares)``: the H2O partial column
            (mol m-2), the ratio of the HDO and H2O partial columns, and
            each level's share of the H2O column (``(n, levels)``, mol m-2).
            NaN where the cuts hold no layer or a level inside them lacks
            q or the ratio.
    """
    weights = layer_weights(pressure_pa, bottom_pa, top_pa)
    used = weights != 0
    q0 = np.where(used, q, 0.0)
    hdo0 = np.where(used, np.asarray(ratio, dtype='float64') * q, 0.0)
    shares = weights * q0 * MOL_M2_PER_PA
    h2o = shares.sum(axis=1)
    hdo = (weights * hdo0).sum(axis=1) * MOL_M2_PER_PA
    bad = ~used.any(axis=1) | (used & ~(np.isfinite(q) & np.isfinite(ratio))).any(axis=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        column_ratio = np.where(bad, np.nan, hdo / h2o)
    h2o = np.where(bad, np.nan, h2o)
    shares = np.where(bad[:, None], np.nan, shares)
    return h2o, column_ratio, shares


def delta(ratio, standard):
    """δ in 1e-3 of a ratio against a standard ratio."""
    return 1000.0 * (np.asarray(ratio, dtype='float64') / standard - 1.0)
