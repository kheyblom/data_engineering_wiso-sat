"""TROPOMI (SRON HDO L2, processor 8.1): which observations are gridded.

The quality levels are Schneider et al. (2022), Table 1, as recorded in every
L2 store's ``quality_filtering`` attribute (the L2 stores keep every
observation; filtering belongs to gridding). Each level adds to the one
before:
- 'success': ``processing_quality_flags == 0``;
- 'clear': success, the all-scene rows (iterations <= 10, reduced
  chi-squared of the fit and of the pre-fit <= 150, SZA <= 70°) and the
  clear-sky row (optical thickness < 0.3, albedo >= 0.02), which is what
  Sarkar et al. (2026) apply;
- 'clear_or_low_cloud': success, the all-scene rows, and clear sky or the
  cloudy row (cloud height <= 2000 m and optical thickness >= 0.3), as
  Schneider et al. recommend. The decided level (user, 2026-11-09).

**One change to Table 1** (user decision 2026-11-10, TROPOMI T24): the
cloudy row is optical thickness >= 0.3, not > 0.3. Table 1's clear (< 0.3)
and cloudy (> 0.3) rows leave a value of exactly 0.3 in neither, and the
stores hold such values; every value must fall in a row. Thresholds are
compared at the stored precision (float32), so < 0.3 and >= 0.3 are exact
complements.

Reduced chi-squared is inferred as chi-squared over the spectral point
count; no source defines it. Integer fill is excluded explicitly:
-2147483647 would otherwise pass ``iterations <= 10``, and as a point count
it would make reduced chi-squared negative. NaN fails every comparison.

Footprints are the four L2 corners; 0-1 is the back edge and 2-3 the front,
so 0-1-2-3 runs round the footprint (``docs/products/tropomi.md``,
"Gridding inputs").
"""
import numpy as np

QUALITY_LEVELS = ('success', 'clear', 'clear_or_low_cloud')
_STORES = {
    'success': ['quality_flags_retrieval'],
    'clear': [
        'quality_flags_retrieval', 'iterations_retrieval', 'solar_zenith_angle',
        'chi_squared_retrieval', 'spectral_point_count_retrieval',
        'chi_squared_prefit', 'spectral_point_count_prefit',
        'optical_thickness_scattering_layer', 'albedo_surface_2365nm',
    ],
}
_STORES['clear_or_low_cloud'] = _STORES['clear'] + ['height_scattering_layer']
FOOTPRINT_MODELS = ('corners',)


def _level(selection):
    level = selection.get('quality_level')
    if level not in QUALITY_LEVELS:
        raise ValueError(f'TROPOMI quality_level must be one of {QUALITY_LEVELS}, got {level!r}')
    return level


def selection_stores(selection):
    """The L2 stores the configured quality level reads."""
    return list(_STORES[_level(selection)])


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

    def written(store):
        fill = fills.get(store)
        return values[store] != fill if fill is not None else np.isfinite(values[store])

    passed = (values['quality_flags_retrieval'] == 0) & written('quality_flags_retrieval')
    if level == 'success':
        return passed
    iterations = values['iterations_retrieval']
    points = values['spectral_point_count_retrieval']
    points_prefit = values['spectral_point_count_prefit']
    thickness = values['optical_thickness_scattering_layer']
    with np.errstate(divide='ignore', invalid='ignore'):
        passed &= written('iterations_retrieval') & (iterations >= 0) & (iterations <= 10)
        passed &= written('spectral_point_count_retrieval') & (points > 0)
        passed &= values['chi_squared_retrieval'] / points <= 150
        passed &= written('spectral_point_count_prefit') & (points_prefit > 0)
        passed &= values['chi_squared_prefit'] / points_prefit <= 150
        passed &= values['solar_zenith_angle'] <= 70
        clear = (thickness < 0.3) & (values['albedo_surface_2365nm'] >= 0.02)
        if level == 'clear':
            return passed & clear
        low_cloud = (values['height_scattering_layer'] <= 2000) & (thickness >= 0.3)
        return passed & (clear | low_cloud)
