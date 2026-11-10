# Nomenclature Key — TROPESS v2 (NASA MUSES HDO Level 2 Full: AIRS, CrIS-JPSS1)

Maps the TROPESS HDO Level 2 v2 **Full** products onto the authoritative
[nomenclature_data.md](/glade/u/home/kheyblom/work/style_guides/nomenclature_data.md),
as the data engineering style guide requires. It is machine read by
`utils/nomenclature.py`; edit the tables, not the code. The format rules are in
`nomenclature-key_tropomi.md`; v1's key is `nomenclature-key_tropess.md`.

v2 is built from the Full files only (user decision 2026-10-28;
`docs/products/tropess.md`, v2 production subset V1-V9). The canonical names
are v1's, plus three; several come from other source paths than in v1, which
is why v2 has a key of its own (V9, D1).

`original_variable_name` is the path in the file, with a numpy-style
selection where only part of a source is stored (V9, D2): `[:, 0:17]` keeps
the 17 levels of the 34-wide retrieval dimension that hold values (R42). What
a selection leaves out is checked from raw at every build and verify, as the
config's `source_remainders` declares.

## Variable Key

| original_variable_name | original_units | canonical_name | canonical_units | canonical_long_name | unit_conversion | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `x[:, 0:17]` | `1` | `water_vapor_hdo_h2o_ratio` | `unitless` | HDO/H2O mole ratio of water vapor | none | bias corrected by TROPESS; R22 does not occur in v2 |
| `x_h2o[:, 0:17]` | `1` | `water_vapor_h2o_mole_fraction_dry_air` | `1e-6` | dry-air mole fraction of water vapor (H2O) | x 1e6 | bias corrected; mol mol-1 to 1e-6; the source standard_name retained |
| `dd_col_p` | `1e-3` | `water_vapor_delta_d_850_250hpa` | `1e-3` | delta D of water vapor from the unweighted mean HDO/H2O mole ratio over the retrieval levels between 850 and 250 hPa | none | every row in v2 (v1: Summary rows); levels 250 <= p < 850 hPa (R30) |
| `dd_col_p_error` | `1e-3` | `water_vapor_delta_d_850_250hpa_standard_error` | `1e-3` | standard error of delta D of water vapor from the unweighted mean HDO/H2O mole ratio over the retrieval levels between 850 and 250 hPa | none | 1-sigma; -9999 or NaN (R17) |
| `x_h2o_col_p` | `1e-6` | `water_vapor_h2o_mole_fraction_dry_air_850_250hpa` | `1e-6` | unweighted mean dry-air mole fraction of water vapor (H2O) over the retrieval levels between 850 and 250 hPa | none | |
| `x_h2o_col_p_error` | `1e-6` | `water_vapor_h2o_mole_fraction_dry_air_850_250hpa_standard_error` | `1e-6` | standard error of the unweighted mean dry-air mole fraction of water vapor (H2O) over the retrieval levels between 850 and 250 hPa | none | |
| `dd_004` | `1e-3` | `water_vapor_delta_d_004` | `1e-3` | delta D of water vapor where the dry-air mole fraction of water vapor (H2O) is 0.004 (4 per mil) | none | |
| `observation_ops/signal_dof` | `1` | `water_vapor_hdo_h2o_ratio_degrees_of_freedom_for_signal` | `unitless` | degrees of freedom for signal of the HDO/H2O mole ratio retrieval of water vapor, the trace of its averaging kernel | none | equals the root `dofs` on every row (audit) |
| `geophysical/average_cloud_eod` | `1` | `cloud_effective_optical_depth` | `unitless` | average effective optical depth of cloud in the retrieved scene | none | |
| `geophysical/cloud_top_pressure` | `hPa` | `cloud_top_pressure` | `Pa` | air pressure at the top of the cloud in the retrieved scene | x 100 | Full's standard_name `cloud_top_pressure` is retained (Q3) |
| `geophysical/surface_temperature` | `K` | `temperature_surface` | `K` | surface temperature of the retrieved scene | none | |
| `geophysical/land_flag` | (none) | `land_flag` | `unitless` | flag that is 1 where the observation is over land and 0 otherwise | none | int16, stored int32 (source_dtypes) |
| `geophysical/day_night_flag` | (none) | `day_night_flag` | `unitless` | flag that is 1 where the observation is in daytime and 0 otherwise | none | int16, stored int32; -999 fill (R29) |
| `quality` | `N/A` | `quality_flags_retrieval` | `unitless` | TROPESS retrieval quality flag, 1 good and 0 bad | none | new in v2; int16, stored int32; the v2 Standard product is exactly the rows with 1 (R41) |
| `observation_ops/xa[:, 0:17]` | `1` | `water_vapor_hdo_h2o_ratio_apriori` | `unitless` | a priori HDO/H2O mole ratio of water vapor | none | |
| `observation_ops/averaging_kernel[:, 0:17, 0:17]` | `1` | `water_vapor_hdo_h2o_ratio_averaging_kernel_log` | `unitless` | averaging kernel of the ln HDO/H2O mole ratio of water vapor, with respect to the true ln ratio | none | (obs, level, level_2), rows retrieved, columns true; fill at the lowest levels on some quality 0 rows (R45) |
| `observation_ops/observation_error_h2o[:, 0:17]` | `1` | `water_vapor_h2o_mole_fraction_dry_air_observation_standard_error_log` | `unitless` | 1-sigma observation error of the ln dry-air mole fraction of water vapor (H2O) | none | ln space, never scaled (R8); NaN and -999 fill, written below the surface (R15) |
| `pressure_ret[:, 0:17]` | `hPa` | `pressure` | `Pa` | air pressure at each vertical level of a retrieval | x 100 | its own store (N3); levels 17-33 repeat 0-16, checked (R42) |
| `altitude` | `m` | `altitude` | `m` | altitude at each vertical level of a retrieval | none | Full's, on the 67-level forward-model grid, read where `pressure_fm` equals each retrieval pressure (`level_lookups`; R43) |
| `retrieval/air_density[:, 0:17]` | `molecules/m^3` | `air_molar_density` | `mol m-3` | molar density of air (moles of air per cubic metre) at each vertical level of a retrieval | x 1 / N_A | new in v2; dry or total air not stated by TROPESS; slots 17-33 repeat 0-16 and 34-66 are fill, checked (R42); the source standard_name withheld (Q2) |
| `hdo_hdo_averaging_kernel[:, 0:17, 0:17]` | `1` | `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log` | `unitless` | averaging kernel of the ln dry-air mole fraction of HDO water vapor, with respect to the true ln HDO mole fraction | none | block of the joint kernel store |
| `hdo_h2o_averaging_kernel[:, 0:17, 0:17]` | `1` | `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log_cross_h2o` | `unitless` | averaging kernel of the ln dry-air mole fraction of HDO water vapor, with respect to the true ln H2O mole fraction | none | block of the joint kernel store |
| `h2o_hdo_averaging_kernel[:, 0:17, 0:17]` | `1` | `water_vapor_h2o_mole_fraction_dry_air_averaging_kernel_log_cross_hdo` | `unitless` | averaging kernel of the ln dry-air mole fraction of water vapor (H2O), with respect to the true ln HDO mole fraction | none | block of the joint kernel store; the ratio kernel equals hdo_hdo - this, to 1e-6 (finding 18) |
| `h2o_h2o_averaging_kernel[:, 0:17, 0:17]` | `1` | `water_vapor_h2o_mole_fraction_dry_air_averaging_kernel_log` | `unitless` | averaging kernel of the ln dry-air mole fraction of water vapor (H2O), with respect to the true ln H2O mole fraction | none | block of the joint kernel store; equals `observation_ops/averaging_kernel_h2o` on every row (Q1) |

- **Units:** `1` is respelled `unitless`. `x_h2o` (x 1e6), the two
  pressures (x 100) and `air_density` (x 1 / N_A) change value.
- **Bias correction:** `x` and `x_h2o` are TROPESS's bias-corrected profiles,
  stated on both stores (`variable_attrs`), as v1.

## Matrix Store Key

| store | arrays | canonical_long_name |
| --- | --- | --- |
| `water_vapor_hdo_and_h2o_mole_fraction_dry_air_averaging_kernel_log` | `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log`, `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log_cross_h2o`, `water_vapor_h2o_mole_fraction_dry_air_averaging_kernel_log_cross_hdo`, `water_vapor_h2o_mole_fraction_dry_air_averaging_kernel_log` | averaging kernel of the joint ln HDO and ln H2O dry-air mole fraction state of water vapor, as its four blocks |

## Coordinate Key

| original_name | original_units | name | units | unit_conversion | notes |
| --- | --- | --- | --- | --- | --- |
| `time` | `seconds since 1993-01-01 00:00:00` | `time` | `seconds since 1900-01-01` | decoded | TAI seconds (R3), whole seconds; less the leap seconds since 1993 to UTC, checked against `datetime_utc` on every row |
| `latitude` | `degrees_north` | `lat` | `degrees_north` | none | target centre |
| `longitude` | `degrees_east` | `lon` | `degrees_east` | none | target centre |

## Temporal Frequency Key

| original_frequency_name | canonical_name | canonical_long_name |
| --- | --- | --- |
| `observation` | `inst` | instantaneous observation |

## Dimensions

| source | store | note |
| --- | --- | --- |
| `target` | `obs` | each day's Full rows, in source order (not time order; R32, R40) |
| `level_ret` | `level` | 34 wide, of which levels 0-16 are kept (R42); surface first, recorded as `vertical_order: surface_first` |
| `level_ret` (second axis of a matrix) | `level_2` | a kernel's columns (true state) |
| `level_fm` | (none) | the 67-level forward-model grid; `altitude` is read from it at the retrieval pressures, onto `level` |

## Store naming (decided 2026-10-22, v2 2026-10-28)

```
<zarr>/wisosat.airs.v_2.fs.inst.native_swath.<variable>.zarr
<zarr>/wisosat.cris_jpss1.v_2.fs.inst.native_swath.<variable>.zarr
```

- `v_2` is the collection version the files declare (`VersionID`); `fs` the
  stream (`version_product`), as v1.
