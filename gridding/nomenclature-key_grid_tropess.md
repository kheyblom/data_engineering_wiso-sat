# Nomenclature key: gridded WISO-SAT stores, TROPESS profile method (AIRS v1)

Machine read by `utils/nomenclature.py`, for configs that set
`quantity_key: nomenclature-key_grid_tropess.md` (`method: profile`). The
tables map each gridded quantity to its row in the authoritative
`/glade/u/home/kheyblom/work/style_guides/nomenclature_data.md`. The build
refuses a config whose quantities, units or frequencies have no exact row
there. Never restate this mapping in Python.

**Decided for AIRS v1 only** (user, 2026-11-13: D2, D3, D4 and D9 in
`airs-gridding-decisions.md`; `docs/products/tropess.md`, "Gridding inputs,
AIRS v1"). Using this key for another product or collection needs the
user's approval.

Three groups of stores, each derived in gridding from the L2 profiles
(`utils/profiles.py`):

- **column:** the partial column between 850 and 250 hPa (the config's
  `profile.column`). The weight is *w* = *a* · *H*: a footprint's overlap
  area with the cell times its H2O partial column there, in mol. *W* is a
  footprint's *w* over every cell, *A* its whole area. There is no standard
  error and no σ sum: AIRS v1 has no valid noise-only σ (method Section 7).
- **level:** each fixed pressure level of the retrieval grid, on a `level`
  dimension. A footprint counts at a level only where the level lies above
  its surface level. The weight *w* is *a* times the H2O partial column of
  the level's layer (the level's share of the whole column, H2O and HDO
  linear in ln p); *δ*, *δa*, *K* and *q* are the footprint's δD, a priori
  δD, kernel diagonal and H2O mole fraction at the level.
- **surface:** each footprint's surface level (its lowest valid one),
  weighted the same way; statistics only (D9, 9.2), *p* its pressure.

## Quantity Key

`group` sets a store's dimensions: `column` and `surface` are (time, lat,
lon); `level` is (time, level, lat, lon). `kind`, `dtype` and `formula` are
as in `nomenclature-key_grid.md`.

| quantity | canonical_name | canonical_units | kind | dtype | group | formula |
| --- | --- | --- | --- | --- | --- | --- |
| delta_d | `water_vapor_column_delta_d_850_250hpa` | 1e-3 | statistic | float32 | column | Σwδ / Σw |
| spread | `water_vapor_column_delta_d_850_250hpa_standard_deviation` | 1e-3 | statistic | float32 | column | √(max(Σwδ² / Σw − δD², 0)) |
| n_eff | `observation_count_effective` | unitless | statistic | float32 | column | (Σw)² / Σw² |
| count | `observation_count` | unitless | statistic | int32 | column | N |
| h2o | `water_vapor_column_h2o_850_250hpa` | mol m-2 | statistic | float32 | column | Σw / Σa / 1e6 |
| coverage | `footprint_coverage` | unitless | statistic | float32 | column | Σa / A_c |
| footprint_area | `footprint_area` | km2 | statistic | float32 | column | ΣwA / Σw |
| area | `footprint_overlap_area_sum` | km2 | sum | float64 | column | Σa |
| weight | `gridding_weight_850_250hpa_sum` | mol | sum | float64 | column | Σw |
| weight_delta_d | `gridding_weight_850_250hpa_delta_d_sum` | mol 1e-3 | sum | float64 | column | Σwδ |
| weight_delta_d_squared | `gridding_weight_850_250hpa_delta_d_squared_sum` | mol 1e-6 | sum | float64 | column | Σwδ² |
| weight_squared | `gridding_weight_850_250hpa_squared_sum` | mol2 | sum | float64 | column | Σw² |
| weight_footprint_area | `gridding_weight_850_250hpa_footprint_area_sum` | mol km2 | sum | float64 | column | ΣwA |
| weight_total | `gridding_weight_850_250hpa_footprint_weight_sum` | mol2 | sum | float64 | column | ΣwW |
| level_delta_d | `water_vapor_delta_d` | 1e-3 | statistic | float32 | level | Σwδ / Σw |
| level_delta_d_apriori | `water_vapor_delta_d_apriori` | 1e-3 | statistic | float32 | level | Σwδa / Σw |
| level_kernel_diagonal | `water_vapor_hdo_h2o_ratio_averaging_kernel_log_diagonal` | unitless | statistic | float32 | level | ΣwK / Σw |
| level_h2o | `water_vapor_h2o_mole_fraction_dry_air` | 1e-6 | statistic | float32 | level | Σaq / Σa |
| level_count | `observation_count_level` | unitless | statistic | int32 | level | N |
| level_weight | `gridding_weight_level_sum` | mol | sum | float64 | level | Σw |
| level_weight_delta_d | `gridding_weight_level_delta_d_sum` | mol 1e-3 | sum | float64 | level | Σwδ |
| level_weight_delta_d_squared | `gridding_weight_level_delta_d_squared_sum` | mol 1e-6 | sum | float64 | level | Σwδ² |
| level_weight_delta_d_apriori | `gridding_weight_level_delta_d_apriori_sum` | mol 1e-3 | sum | float64 | level | Σwδa |
| level_weight_kernel_diagonal | `gridding_weight_level_averaging_kernel_diagonal_sum` | mol | sum | float64 | level | ΣwK |
| level_area | `footprint_overlap_area_level_sum` | km2 | sum | float64 | level | Σa |
| level_area_h2o | `footprint_overlap_area_h2o_mole_fraction_sum` | km2 1e-6 | sum | float64 | level | Σaq |
| surface_delta_d | `water_vapor_delta_d_surface` | 1e-3 | statistic | float32 | surface | Σwδ / Σw |
| surface_delta_d_apriori | `water_vapor_delta_d_surface_apriori` | 1e-3 | statistic | float32 | surface | Σwδa / Σw |
| surface_kernel_diagonal | `water_vapor_hdo_h2o_ratio_surface_averaging_kernel_log_diagonal` | unitless | statistic | float32 | surface | ΣwK / Σw |
| surface_h2o | `water_vapor_h2o_mole_fraction_dry_air_surface` | 1e-6 | statistic | float32 | surface | Σaq / Σa |
| surface_count | `observation_count_surface` | unitless | statistic | int32 | surface | N |
| surface_pressure | `pressure_surface` | Pa | statistic | float32 | surface | Σwp / Σw |

## Input Key

The L2 quantities each input must hold, checked against the L2 store's
`units` before a build reads it. A config names the L2 variable for each
input (`inputs:`).

| input | canonical_units |
| --- | --- |
| ratio | unitless |
| h2o | 1e-6 |
| pressure | Pa |
| apriori | unitless |
| kernel | unitless |

## Temporal Frequency Key

| frequency | canonical_name |
| --- | --- |
| day | `day` |
| 3day | `3day` |
| month | `month` |
