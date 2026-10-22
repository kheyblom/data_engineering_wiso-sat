# Nomenclature Key — GOSAT (IUP FOCAL v3.0.1)

Maps the IUP FOCAL GOSAT Level 2 product onto the authoritative
[nomenclature_data.md](/glade/u/home/kheyblom/work/style_guides/nomenclature_data.md),
as the data engineering style guide requires. It is machine read by
`utils/nomenclature.py`; edit the tables, not the code. The format rules are in
`nomenclature-key_tropomi.md`.

FOCAL publishes two files per day, DED (δD) and H2O (XH2O). Their sounding
sets overlap only partly, so the stores merge them into **one obs axis per day,
one obs per distinct sounding** (decided 2026-10-14; see
`docs/products/gosat.md`).
- A variable from one file is absent at a sounding only in the other: NaN for
  a float, the config's `absent_fill_values` for an integer.
- `original_variable_name` is the variable name in its file. The files are
  flat, with no groups.

## Variable Key

| original_variable_name | original_units | canonical_name | canonical_units | canonical_long_name | unit_conversion | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `xded` | `1e-3` | `water_vapor_column_delta_d` | `1e-3` | delta D of the total water vapor column | none | DED file. Column-averaged δD: XHDO and XH2O share the dry-air column, so this is δD of the total column, as TROPOMI's |
| `xded_uncertainty` | `1e-3` | `water_vapor_column_delta_d_standard_error` | `1e-3` | standard error of delta D of the total water vapor column | none | DED file |
| `xded_quality_flag` | (none) | `quality_flags_retrieval_delta_d` | `unitless` | quality flags of the delta D retrieval, where a product retrieves delta D and H2O separately | none | DED file; int32, 0 good, 1 potentially bad |
| `xh2o` | `1e-6` | `water_vapor_column_h2o_mole_fraction_dry_air` | `1e-6` | column-averaged dry-air mole fraction of water vapor (H2O) | none | H2O file; dry-air by definition |
| `xh2o_uncertainty` | `1e-6` | `water_vapor_column_h2o_mole_fraction_dry_air_standard_error` | `1e-6` | standard error of the column-averaged dry-air mole fraction of water vapor (H2O) | none | H2O file; 1-sigma |
| `xh2o_quality_flag` | (none) | `quality_flags_retrieval_h2o` | `unitless` | quality flags of the H2O retrieval, where a product retrieves delta D and H2O separately | none | H2O file; int32, 0 good, 1 potentially bad |
| `solar_zenith_angle` | `degree` | `solar_zenith_angle` | `degree` | solar zenith angle | none | both files, identical where both hold a sounding |
| `xh2o_averaging_kernel` | `1` | `water_vapor_column_h2o_mole_fraction_dry_air_averaging_kernel` | `unitless` | normalized column averaging kernel of the column-averaged dry-air mole fraction of water vapor (H2O), with respect to the layer dry-air mole fraction | none | H2O file; on `layer`, layer means, surface first |
| `h2o_profile_apriori` | `1e-6` | `water_vapor_h2o_mole_fraction_dry_air_apriori` | `1e-6` | a priori dry-air mole fraction of water vapor (H2O) | none | H2O file; on `layer`, layer means, surface first |
| `pressure_weight` | `1` | `pressure_weight_column_average` | `unitless` | layer pressure weight that forms a column average from a layer profile | none | both files, identical where both hold a sounding; on `layer`. Within 0.0026 of dp / p_surface but not equal, so stored as published |
| `pressure_levels` | `hPa` | `pressure` | `Pa` | air pressure at each vertical level of a retrieval | x 100 | on `level` (6), the boundaries of the 5 layers, surface first; both files, identical where both hold a sounding. Its own store, not in the geolocation store (user decision 2026-10-19) |

- **Units are already canonical**, except `pressure` (hPa x 100 to Pa).
  FOCAL writes `1e-3` and `1e-6`, so no other value changes. The quality flags carry no units attribute (`unitless`).
- **Every sounding is flag 0** in the files sampled: FOCAL publishes only
  soundings that pass its quality control (Sarkar et al. 2026). The flags are
  stored anyway, since quality flags are mandatory.
- **Model-comparison variables** (named 2026-10-19; mapping in
  `docs/products/gosat.md`): the kernel, the a priori, the pressure weight
  and `pressure` above. They apply FOCAL's operator
  `XH2O_sim = sum_j w_j (xa_j + a_j (x_model_j - xa_j))`.
  - The kernel and the a priori are in the H2O file only, so they are absent
    (NaN) on DED-only soundings.
  - `dry_column` is held (G7): its unit is unresolved, and the operator does
    not need it.

## Coordinate Key

| original_name | original_units | name | units | unit_conversion | notes |
| --- | --- | --- | --- | --- | --- |
| `time` | `seconds since 1970-01-01 00:00:00` | `time` | `nanoseconds since 1900-01-01` | decoded | float64 seconds; nanoseconds is the coarsest unit that holds every one exactly (ms fails 99% and us 76% of 38,003 sampled times) |
| `latitude` | `degrees_north` | `lat` | `degrees_north` | none | sounding centre |
| `longitude` | `degrees_east` | `lon` | `degrees_east` | none | sounding centre |

## Temporal Frequency Key

| original_frequency_name | canonical_name | canonical_long_name |
| --- | --- | --- |
| `observation` | `inst` | instantaneous observation |

## Dimensions

| source | store | note |
| --- | --- | --- |
| `sounding_dim` | `obs` | each day's DED and H2O soundings merged into one, in time order |
| `level_dim`, `layer_dim` | `level`, `layer` | 6 pressure levels bounding 5 layers. Surface first, recorded as `vertical_order: surface_first` (`VERTICAL_ORDER` in the reader) |

## Store naming (decided 2026-10-14)

```
<zarr>/wisosat.gosat.v_3_0_1.inst.native_swath.<variable>.zarr
```

- The version is the files' root `product_version` attribute (`v3.0.1`).
- GOSAT-2 has the same format and reuses this key (`source: gosat` in
  `config/gosat2/`), as `wisosat.gosat2.v_3_0_1...`.
