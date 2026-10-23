# Nomenclature Key — TROPESS (NASA MUSES HDO Level 2: AIRS, later CrIS)

Maps the TROPESS HDO Level 2 Standard and Summary products onto the
authoritative
[nomenclature_data.md](/glade/u/home/kheyblom/work/style_guides/nomenclature_data.md),
as the data engineering style guide requires. It is machine read by
`utils/nomenclature.py`; edit the tables, not the code. The format rules are in
`nomenclature-key_tropomi.md`.

Each day's Standard and Summary files are merged onto the Standard rows (user
decision 2026-10-23; `docs/products/tropess.md`, Product scheme). Summary is
the Standard rows with DOF > 1.1, with identical values, so:
- **From Standard:** every variable both files carry, and the kernel, prior,
  errors, DOF and cloud.
- **From Summary:** only the five 850-250 hPa and 0.004 fields, absent (NaN)
  on rows with DOF <= 1.1.

`original_variable_name` is the path in the file; `x`, `x_h2o`, `pressure`
and the position are root variables.

## Variable Key

| original_variable_name | original_units | canonical_name | canonical_units | canonical_long_name | unit_conversion | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `x` | `1` | `water_vapor_hdo_h2o_ratio` | `unitless` | HDO/H2O mole ratio of water vapor | none | Standard; bias corrected by TROPESS; row 0 of each Standard file masked as a declared defect (R22) |
| `x_h2o` | `1` | `water_vapor_h2o_mole_fraction_dry_air` | `1e-6` | dry-air mole fraction of water vapor (H2O) | x 1e6 | Standard; bias corrected; mol mol-1 to 1e-6; Summary's standard_name retained |
| `dd_col_p` | `1e-3` | `water_vapor_delta_d_850_250hpa` | `1e-3` | delta D of water vapor from the unweighted mean HDO/H2O mole ratio over the retrieval levels between 850 and 250 hPa | none | Summary; levels 250 <= p < 850 hPa, unweighted (R30, Q2b) |
| `dd_col_p_error` | `1e-3` | `water_vapor_delta_d_850_250hpa_standard_error` | `1e-3` | standard error of delta D of water vapor from the unweighted mean HDO/H2O mole ratio over the retrieval levels between 850 and 250 hPa | none | Summary; 1-sigma, (1000 + dD) sqrt(M S M^T); -9999 where a level in range has a negative variance (R17) |
| `x_h2o_col_p` | `1e-6` | `water_vapor_h2o_mole_fraction_dry_air_850_250hpa` | `1e-6` | unweighted mean dry-air mole fraction of water vapor (H2O) over the retrieval levels between 850 and 250 hPa | none | Summary |
| `x_h2o_col_p_error` | `1e-6` | `water_vapor_h2o_mole_fraction_dry_air_850_250hpa_standard_error` | `1e-6` | standard error of the unweighted mean dry-air mole fraction of water vapor (H2O) over the retrieval levels between 850 and 250 hPa | none | Summary |
| `dd_004` | `1e-3` | `water_vapor_delta_d_004` | `1e-3` | delta D of water vapor where the dry-air mole fraction of water vapor (H2O) is 0.004 (4 per mil) | none | Summary; name decided by the user (Q2c) |
| `observation_ops/signal_dof` | `1` | `water_vapor_hdo_h2o_ratio_degrees_of_freedom_for_signal` | `unitless` | degrees of freedom for signal of the HDO/H2O mole ratio retrieval of water vapor, the trace of its averaging kernel | none | Standard; negative on some rows (R28) |
| `geophysical/average_cloud_eod` | `1` | `cloud_effective_optical_depth` | `unitless` | average effective optical depth of cloud in the retrieved scene | none | Standard; the COD of Sarkar et al.'s filter |
| `geophysical/cloud_top_pressure` | `hPa` | `cloud_top_pressure` | `Pa` | air pressure at the top of the cloud in the retrieved scene | x 100 | Standard |
| `geophysical/surface_temperature` | `K` | `temperature_surface` | `K` | surface temperature of the retrieved scene | none | Standard |
| `geophysical/land_flag` | (none) | `land_flag` | `unitless` | flag that is 1 where the observation is over land and 0 otherwise | none | both files; int32/int64 by version, stored int32 (source_dtypes) |
| `geophysical/day_night_flag` | (none) | `day_night_flag` | `unitless` | flag that is 1 where the observation is in daytime and 0 otherwise | none | both files; int32/int16 by version, stored int32; -999 fill |
| `observation_ops/xa` | `1` | `water_vapor_hdo_h2o_ratio_apriori` | `unitless` | a priori HDO/H2O mole ratio of water vapor | none | Standard; on `level` |
| `observation_ops/averaging_kernel` | `1` | `water_vapor_hdo_h2o_ratio_averaging_kernel_log` | `unitless` | averaging kernel of the ln HDO/H2O mole ratio of water vapor, with respect to the true ln ratio | none | Standard; (target, level, level) -> (obs, level, level_2), rows retrieved, columns true |
| `observation_ops/observation_error_h2o` | `1` | `water_vapor_h2o_mole_fraction_dry_air_observation_standard_error_log` | `unitless` | 1-sigma observation error of the ln dry-air mole fraction of water vapor (H2O) | none | Standard; ln space, never scaled (R8); NaN and -999 fill (R15) |
| `pressure` | `hPa` | `pressure` | `Pa` | air pressure at each vertical level of a retrieval | x 100 | both files; its own store (N3); the lowest valid level is the surface (R10) |
| `altitude` | `m` | `altitude` | `m` | altitude at each vertical level of a retrieval | none | both files |

- **Units:** `1` is respelled `unitless`, and the TROPESS units string for a
  flag is empty. Only `x_h2o` (x 1e6) and the two pressures (x 100) change
  value.
- **Bias correction:** `x` and `x_h2o` are TROPESS's bias-corrected
  profiles. The configs state it on both stores (`variable_attrs`); the
  uncorrected `retrieval/x_raw` and `x_h2o_raw` are not stored (Q4).

## Coordinate Key

| original_name | original_units | name | units | unit_conversion | notes |
| --- | --- | --- | --- | --- | --- |
| `time` | `seconds since 1993-01-01 00:00:00` | `time` | `seconds since 1900-01-01` | decoded | TAI seconds (R3), whole seconds in every file; less the leap seconds since 1993 to UTC, checked against `datetime_utc` on every row |
| `latitude` | `degrees_north` | `lat` | `degrees_north` | none | target centre |
| `longitude` | `degrees_east` | `lon` | `degrees_east` | none | target centre |

## Temporal Frequency Key

| original_frequency_name | canonical_name | canonical_long_name |
| --- | --- | --- |
| `observation` | `inst` | instantaneous observation |

## Dimensions

| source | store | note |
| --- | --- | --- |
| `target` | `obs` | each day's Standard rows, in source order (not time order; R32) |
| `level` | `level` | 17 levels, surface first, recorded as `vertical_order: surface_first` |
| `level` (second axis of a matrix) | `level_2` | the averaging kernel's columns (true state) |

## Store naming (decided 2026-10-22, revised 2026-10-23)

```
<zarr>/wisosat.airs.v_1.rs.inst.native_swath.<variable>.zarr
<zarr>/wisosat.airs.v_1.fs.inst.native_swath.<variable>.zarr
```

- `v_1` is the collection version the files declare (`VersionID`).
- `rs` or `fs` is the stream (`version_product`), after a period, as the
  style guide's `v_3_5.nrt`.
