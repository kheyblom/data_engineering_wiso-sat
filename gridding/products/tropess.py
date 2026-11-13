"""TROPESS (MUSES HDO L2: AIRS v1; CrIS later): which observations are gridded.

TROPESS v1 publishes no quality variable; the L2 stores keep every Standard
observation (filtering belongs to gridding). The quality levels are the
user's decisions of 2026-11-13 for AIRS v1 (``airs-gridding-decisions.md``
D5 and D7; ``docs/products/tropess.md``, "Gridding inputs, AIRS v1"). They
apply to AIRS v1 only until the user says otherwise:

- 'summary': TROPESS's Summary rule, in two halves. A row is kept if its
  degrees of freedom for signal exceed 1.1, or if they are missing and the
  Summary product's 850-250 hPa delta D is written (the days upstream has
  no Standard file for, where DOF is absent; R23). Measured on every v1 row:
  no row has that delta D written with DOF <= 1.1, so the two halves never
  disagree. No cloud limit.
- 'summary_daytime': 'summary' and ``day_night_flag`` == 1 as published
  (TROPESS's ``sunlit_binary_mask``). Rows with the flag's fill (-999) fall
  in 'summary' only.

**Every value falls in a row:** the comparison is strict and made at the
stored float32 (five rows hold exactly 1.1 and are not in Summary, R31), so
a row is either kept or has DOF <= 1.1, or has neither DOF nor the marker.

The 850-250 hPa delta D is only the marker of a Summary row here; it is
never gridded (it is an unweighted mean of the level ratios, D2).

Footprints are the 1.1 degree AIRS field of view drawn from the published
footprint indices and scan angle (``utils/airs_fov.py``).
"""
import numpy as np

QUALITY_LEVELS = ('summary', 'summary_daytime')
DOF = 'water_vapor_hdo_h2o_ratio_degrees_of_freedom_for_signal'
SUMMARY_MARKER = 'water_vapor_delta_d_850_250hpa'
DAY_NIGHT = 'day_night_flag'
# TROPESS's Summary threshold, compared strictly at the stores' float32 (R31)
SUMMARY_DOF = np.float32(1.1)
FOOTPRINT_MODELS = ('airs_fov',)


def _level(selection):
    level = selection.get('quality_level')
    if level not in QUALITY_LEVELS:
        raise ValueError(f'TROPESS quality_level must be one of {QUALITY_LEVELS}, got {level!r}')
    return level


def selection_stores(selection):
    """The L2 stores the configured quality level reads."""
    stores = [DOF, SUMMARY_MARKER]
    return stores + [DAY_NIGHT] if _level(selection) == 'summary_daytime' else stores


def select(values, fills, selection):
    """True where an observation passes the configured quality level.

    Args:
        values (dict): store -> numpy array over one block.
        fills (dict): store -> integer ``_FillValue`` (None for floats).
        selection (dict): The config's ``selection`` (``quality_level``).

    Returns:
        numpy.ndarray: Boolean mask.
    """
    level = _level(selection)
    dof = values[DOF]
    if dof.dtype != np.float32:
        raise ValueError(f'{DOF} is {dof.dtype}; the Summary threshold is compared at float32')
    with np.errstate(invalid='ignore'):
        passed = (dof > SUMMARY_DOF) | (np.isnan(dof) & np.isfinite(values[SUMMARY_MARKER]))
    if level == 'summary_daytime':
        # the flag's fill (-999) is not 1, so those rows are in 'summary' only
        passed &= values[DAY_NIGHT] == 1
    return passed
