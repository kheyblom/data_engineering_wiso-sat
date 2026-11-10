# Nomenclature key: gridded WISO-SAT stores

Machine read by `utils/nomenclature.py`: the tables below map each gridded
quantity to its row in the authoritative
`/glade/u/home/kheyblom/work/style_guides/nomenclature_data.md` (rows added
2026-11-10, style_guides `8144058`). The build refuses a config whose
quantities, units or frequencies have no exact row there. Never restate this
mapping in Python.

What each quantity is, and how it is computed, is in
[`docs/technical/gridding-method.md`](../docs/technical/gridding-method.md)
(Sections 6 and 8). The weight is *w* = *a* · *H*: a footprint's overlap
area with the cell times its H2O column, in mol (the water-vapour moles it
puts in the cell: km² × 1e6 m² km⁻² × mol m⁻²). *W* is a footprint's *w*
summed over every cell of the grid; *A* its whole area; σ its δD random
uncertainty. Each statistic follows from the sums, so the sums are what add
over days and over cells.

## Quantity Key

`quantity` is the code's name, `kind` says whether the store holds a sum
(adds over cells and days) or a statistic (formed from the sums). `dtype` is
the stored dtype: the sums are float64 because the spread subtracts two
numbers of ~4e4 ‰² and float32 loses up to 0.2 ‰ of it
(`notebooks/drafting/gridding-notes.md`, "Coarsening one fine grid"); the
statistics are float32. `observation_count` is an integer: 0 in a cell no
footprint touched is a value, not a fill.

| quantity | canonical_name | canonical_units | kind | dtype | formula |
| --- | --- | --- | --- | --- | --- |
| delta_d | `water_vapor_column_delta_d` | 1e-3 | statistic | float32 | Σwδ / Σw |
| standard_error | `water_vapor_column_delta_d_standard_error` | 1e-3 | statistic | float32 | √(Σw²σ²) / Σw |
| spread | `water_vapor_column_delta_d_standard_deviation` | 1e-3 | statistic | float32 | √(max(Σwδ² / Σw − δD², 0)) |
| n_eff | `observation_count_effective` | unitless | statistic | float32 | (Σw)² / Σw² |
| count | `observation_count` | unitless | statistic | int32 | N |
| h2o | `water_vapor_column_h2o` | mol m-2 | statistic | float32 | Σw / Σa / 1e6 |
| coverage | `footprint_coverage` | unitless | statistic | float32 | Σa / A_c |
| footprint_area | `footprint_area` | km2 | statistic | float32 | ΣwA / Σw |
| area | `footprint_overlap_area_sum` | km2 | sum | float64 | Σa |
| weight | `gridding_weight_sum` | mol | sum | float64 | Σw |
| weight_delta_d | `gridding_weight_delta_d_sum` | mol 1e-3 | sum | float64 | Σwδ |
| weight_delta_d_squared | `gridding_weight_delta_d_squared_sum` | mol 1e-6 | sum | float64 | Σwδ² |
| weight_squared | `gridding_weight_squared_sum` | mol2 | sum | float64 | Σw² |
| weight_squared_variance | `gridding_weight_squared_delta_d_variance_sum` | mol2 1e-6 | sum | float64 | Σw²σ² |
| weight_footprint_area | `gridding_weight_footprint_area_sum` | mol km2 | sum | float64 | ΣwA |
| weight_total | `gridding_weight_footprint_weight_sum` | mol2 | sum | float64 | ΣwW |
| weight_total_variance | `gridding_weight_footprint_weight_delta_d_variance_sum` | mol2 1e-6 | sum | float64 | ΣwWσ² |

## Input Key

The L2 quantities each input must hold, checked against the L2 store's
`units` before a build reads it. A config names the L2 variable for each
input (`inputs:`); this table fixes the units the method needs.

| input | canonical_units |
| --- | --- |
| delta_d | 1e-3 |
| delta_d_uncertainty | 1e-3 |
| weight | mol m-2 |

## Temporal Frequency Key

A config's frequency is `day`, `<n>day`, `month` or `<n>month`
(`utils/periods.py`). Each token used must be a row in
`nomenclature_data.md`'s Temporal Frequency Key; these are the ones with
rows today.

| frequency | canonical_name |
| --- | --- |
| day | `day` |
| 3day | `3day` |
| month | `month` |
