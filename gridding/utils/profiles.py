"""The profile method's per-footprint quantities, derived from L2 profiles.

For a product whose gridded δD is computed here from its retrieval levels
(AIRS v1: user decisions 2026-11-13, D2, D4 and D9 in
``airs-gridding-decisions.md``; ``docs/products/tropess.md``, "Gridding
inputs, AIRS v1"). The L2 stores hold only published values; everything
below is derived here, and the verifier derives it again on its own.

From each retrieval's HDO/H2O ratio, H2O dry-air mole fraction, a priori
ratio, kernel diagonal and pressure, on the L2 ``level`` axis (surface
first; levels below the surface missing; the lowest valid level is the
surface, R10):

- **column group:** δD and the H2O partial column between the config's two
  pressures (``profile.column``), H2O and HDO each linear in ln p with exact
  cuts (``utils/columns.py``);
- **level group:** on each of the config's fixed pressure levels
  (``profile.levels``) that lies above the retrieval's surface level: δD, the
  a priori δD, the kernel diagonal, the H2O mole fraction, and the level's
  share of the whole H2O column (its gridding weight per unit area);
- **surface group:** the same at the surface level, with its pressure.

The fixed levels are L2 slots 1 on: slot 0 is only ever a surface. A slot
above the surface must hold its fixed pressure, or the read fails: one
gridded level never mixes pressures (D2, 2.5).
"""
import numpy as np

from utils import columns

# how closely an L2 slot above the surface must hold its fixed pressure
LEVEL_RTOL = 1e-4
H2O_UNIT = 1e-6  # the L2 mole fraction's unit (canonical 1e-6), to mol mol-1


def derive(values, spec):
    """Every per-footprint quantity the profile method grids.

    Args:
        values (dict): Per footprint, float64: ``pressure`` (Pa), ``ratio``,
            ``h2o`` (1e-6), ``apriori`` (ratio), ``kernel`` (the kernel's
            diagonal), each ``(n, slots)``.
        spec (dict): The config's ``profile``: ``ratio_standard``,
            ``column`` (``bottom`` and ``top``, Pa) and ``levels`` (Pa).

    Returns:
        dict: ``delta_d`` and ``h2o`` (the column group, NaN where the
            retrieval has no such column); ``level_valid`` and the
            ``level_*`` arrays, ``(n, levels)``; ``surface_valid`` and the
            ``surface_*`` arrays, ``(n,)``.

    Raises:
        ValueError: If the L2 level axis is not the fixed levels plus one
            surface slot, or a slot above a surface holds another pressure.
    """
    pressure, ratio, apriori, kernel = (np.asarray(values[name], dtype='float64')
                                        for name in ('pressure', 'ratio', 'apriori', 'kernel'))
    h2o = np.asarray(values['h2o'], dtype='float64')
    levels = np.asarray(spec['levels'], dtype='float64')
    standard = float(spec['ratio_standard'])
    n, slots = pressure.shape
    if slots != levels.size + 1:
        raise ValueError(f'L2 has {slots} level slots; profile.levels names {levels.size} fixed levels plus the '
                         f'surface slot')
    q = h2o * H2O_UNIT
    column_h2o, column_ratio, _ = columns.partial_columns(pressure, q, ratio, float(spec['column']['bottom']),
                                                          float(spec['column']['top']))
    _, _, shares = columns.partial_columns(pressure, q, ratio)
    surface = columns.surface_level(pressure)
    complete = np.isfinite(ratio) & np.isfinite(h2o) & np.isfinite(apriori) & np.isfinite(kernel) & np.isfinite(shares)

    above = np.arange(1, slots)[None, :] > surface[:, None]
    above &= surface[:, None] >= 0
    off_level = above & ~np.isclose(pressure[:, 1:], levels[None, :], rtol=LEVEL_RTOL, atol=0)
    if off_level.any():
        row, level = np.argwhere(off_level)[0]
        raise ValueError(f'a level above the surface holds {pressure[row, level + 1]:.2f} Pa, not its fixed '
                         f'{levels[level]:.2f} Pa ({int(off_level.sum())} values): the levels would mix pressures')
    out = {
        'delta_d': columns.delta(column_ratio, standard),
        'h2o': column_h2o,
        'level_valid': above & complete[:, 1:],
        'level_share': shares[:, 1:],
        'level_delta_d': columns.delta(ratio[:, 1:], standard),
        'level_delta_d_apriori': columns.delta(apriori[:, 1:], standard),
        'level_kernel_diagonal': kernel[:, 1:],
        'level_h2o': h2o[:, 1:],
    }
    rows = np.arange(n)
    at = np.maximum(surface, 0)
    out.update({
        'surface_valid': (surface >= 0) & complete[rows, at],
        'surface_share': shares[rows, at],
        'surface_delta_d': columns.delta(ratio[rows, at], standard),
        'surface_delta_d_apriori': columns.delta(apriori[rows, at], standard),
        'surface_kernel_diagonal': kernel[rows, at],
        'surface_h2o': h2o[rows, at],
        'surface_pressure': pressure[rows, at],
    })
    return out
