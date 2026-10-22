# Nomenclature Key — SCIAMACHY (SRON SICOR H2O/HDO L2, processor 8.1)

Maps the SRON SCIAMACHY H2O/HDO Level 2 product (Schneider et al. 2018) onto
the authoritative
[nomenclature_data.md](/glade/u/home/kheyblom/work/style_guides/nomenclature_data.md),
as the data engineering style guide requires. The subset was decided with the
user on 2026-10-22 (`docs/products/sciamachy.md`, Production subset).

**This file is machine read.** `utils/nomenclature.py` parses the three tables
below. It is the only place the pipeline learns what a variable is called, what
its units are, and how its values are converted. Edit the tables, not the code.
Columns are matched by header name: reorder them freely, but do not rename them.

- `original_variable_name` is the HDF5 path inside the orbit file
  (`<group>/<variable>`), as in TROPOMI's format.
- `unit_conversion` is parsed: `none`, or `x <factor>`, where the factor is
  numbers and the constant `N_A` (6.02214076e23 mol-1, exact SI) joined by `*`
  and `/`. The build multiplies in float64 and stores the source dtype.
- `original_units` is documentation. The build records the units string read
  from the file on each store.

## Variable Key

| original_variable_name | original_units | canonical_name | canonical_units | canonical_long_name | unit_conversion | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `target_product/h2o_column` | `molec. cm-2` | `water_vapor_column_h2o` | `mol m-2` | total column of water vapor (H2O) | x 1e4 / N_A | molec cm-2 to mol m-2 |
| `target_product/h2o_column_precision` | `molec. cm-2` | `water_vapor_column_h2o_standard_error` | `mol m-2` | standard error of the total column of water vapor (H2O) | x 1e4 / N_A | molec cm-2 to mol m-2 |
| `target_product/hdo_column` | `molec. cm-2` | `water_vapor_column_hdo` | `mol m-2` | total column of HDO water vapor | x 1e4 / N_A | molec cm-2 to mol m-2 |
| `target_product/hdo_column_precision` | `molec. cm-2` | `water_vapor_column_hdo_standard_error` | `mol m-2` | standard error of the total column of HDO water vapor | x 1e4 / N_A | molec cm-2 to mol m-2 |
| `diagnostics/processing_quality_flags` | (none) | `quality_flags_retrieval` | `unitless` | retrieval quality flags | none | int32; mandatory in every run; CF flag attributes carried |
| `diagnostics/iterations` | `1` | `iterations_retrieval` | `unitless` | number of retrieval iterations | none | int32 |
| `instrument/solar_zenith_angle` | `degrees` | `solar_zenith_angle` | `degree` | solar zenith angle | none | respelled only |
| `target_product/h2o_column_apriori` | `molec. cm-2` | `water_vapor_column_h2o_apriori` | `mol m-2` | a priori total column of water vapor (H2O) | x 1e4 / N_A | the sum of the partial-column prior (S7); stored as published |
| `target_product/hdo_column_apriori` | `molec. cm-2` | `water_vapor_column_hdo_apriori` | `mol m-2` | a priori total column of HDO water vapor | x 1e4 / N_A | the sum of the partial-column prior (S7); stored as published |
| `side_product/ch4_column` | `molec. cm-2` | `methane_column` | `mol m-2` | total column of methane (CH4) | x 1e4 / N_A | retrieved in the same fit as the water columns; the cloud filter's c_CH4 (P3b) |
| `side_product/ch4_column_apriori` | `molec. cm-2` | `methane_column_apriori` | `mol m-2` | a priori total column of methane (CH4) | x 1e4 / N_A | TM5 |
| `diagnostics/rms` | `mol ph. s-1 m-2 nm-1 sr-1` | `rms_residual_retrieval` | `mol s-1 m-2 nm-1 sr-1` | root mean square of the final retrieval fit residual radiance, in photons | none | respelled only: `ph.` (photons) is a label, kept in the long_name |
| `side_product/surface_albedo` | `1` | `albedo_surface_2360nm` | `unitless` | surface albedo at 2360 nm | none | `nwin` squeezed; Lambertian, retrieved in the same fit |
| `diagnostics/chi_squared` | `1` | `chi_squared_retrieval` | `unitless` | unreduced chi-squared of the final retrieval fit residual | none | unreduced, as published |
| `diagnostics/number_of_spectral_points_in_retrieval` | `1` | `spectral_point_count_retrieval` | `unitless` | number of spectral points used in the final retrieval fit | none | int32; `nwin` squeezed |
| `target_product/h2o_column_averaging_kernel` | `1` | `water_vapor_column_h2o_averaging_kernel` | `unitless` | column averaging kernel of the total column of water vapor (H2O), with respect to layer partial columns | none | on `layer` (60), top first; model comparison |
| `target_product/hdo_column_averaging_kernel` | `1` | `water_vapor_column_hdo_averaging_kernel` | `unitless` | column averaging kernel of the total column of HDO water vapor, with respect to layer partial columns | none | on `layer` (60), top first; model comparison |
| `target_product/h2o_profile_apriori` | `molec. cm-2` | `water_vapor_partial_column_h2o_apriori` | `mol m-2` | a priori layer partial column of water vapor (H2O) | x 1e4 / N_A | on `layer` (60), top first; SRON's "profile" is a partial column per layer |
| `target_product/hdo_profile_apriori` | `molec. cm-2` | `water_vapor_partial_column_hdo_apriori` | `mol m-2` | a priori layer partial column of HDO water vapor | x 1e4 / N_A | on `layer` (60), top first; SRON's "profile" is a partial column per layer |
| `meteo/dry_air_subcolumns` | `molec. cm-2` | `dry_air_partial_column` | `mol m-2` | layer partial column of dry air | x 1e4 / N_A | on `layer` (60), top first; model comparison |
| `meteo/pressure_levels` | `Pa` | `pressure` | `Pa` | air pressure at each vertical level of a retrieval | none | on `level` (61), the boundaries of the 60 layers, top first: level 0 is 0 Pa and the last level is the surface pressure. Its own store |

- **No δD** is published, and none is derived (user decision 2026-10-22, P2).
  SRON's TROPOMI definition, `(hdo_column / h2o_column) / 3.1153e-4 - 1`, is
  given in the filtering guidance.
- **Columns** are published in molecules per cm². x 1e4 converts cm-2 to m-2,
  and / N_A converts molecules to moles. The CH4 columns and every partial
  column take the same factor.
- **`unitless`** is the canonical spelling of SRON's `1`, and of no units
  attribute at all for `processing_quality_flags`. No value changes.
- **Not stored, though TROPOMI has a store of the name** (P3): no prefit
  chi-squared or spectral point count is published; the scattering layer is
  not retrieved in this non-scattering product (S6); and the source row is
  `pixel_id` - 1, which the granule index already gives (P3c).

## Coordinate Key

The geolocation store's per-observation coordinates. `nomenclature_data.md`
has no coordinate rows. The gridded stores keep `time`, `lat` and `lon`, and so
does this product.

| original_name | original_units | name | units | unit_conversion | notes |
| --- | --- | --- | --- | --- | --- |
| `instrument/time` | `year month day hour minute second millisecond` | `time` | `milliseconds since 1900-01-01` | decoded | broken-down int32 (obs, 7) decoded to a timestamp; a millisecond field of 1000 carries into the next second (S10); int64, proleptic_gregorian |
| `instrument/latitude_center` | `degrees north` | `lat` | `degrees_north` | none | pixel centre; respelled only |
| `instrument/longitude_center` | `degrees east` | `lon` | `degrees_east` | none | pixel centre; respelled only |
| `instrument/latitude_corners` | `degrees north` | `lat_corners` | `degrees_north` | none | the pixel's 4 corners on `corner` (P4); respelled only |
| `instrument/longitude_corners` | `degrees east` | `lon_corners` | `degrees_east` | none | the pixel's 4 corners on `corner` (P4); respelled only |

## Temporal Frequency Key

| original_frequency_name | canonical_name | canonical_long_name |
| --- | --- | --- |
| `observation` | `inst` | instantaneous observation |

SRON names no temporal frequency. Each record is one instantaneous retrieval,
so `observation` is this project's own word for it, used in the configs.

## Dimensions

| source | store | note |
| --- | --- | --- |
| `nobs` | `obs` | the file's retrievals in source order; concatenated over orbits in orbit order. Row r of a file is `pixel_id` r + 1 |
| `nwin` | (squeezed) | length 1 |
| `ncorner` | `corner` | the 4 pixel corners, in the geolocation store's `lat_corners` and `lon_corners`, in the source's order |
| `nlayer`, `nlevel` | `layer`, `level` | 61 pressure levels bounding 60 layers. Top first, recorded as `vertical_order: top_first` (`VERTICAL_ORDER` in the reader) |

## Store naming (decided 2026-10-22)

```
<zarr>/wisosat.sciamachy.<version>.inst.native_swath.<variable>.zarr
<zarr>/wisosat.sciamachy.v_8_1.inst.native_swath.water_vapor_column_h2o.zarr
<zarr>/wisosat.sciamachy.v_8_1.inst.native_swath.geolocation.zarr
```

- **Data source** is `wisosat.sciamachy`: the collection, then the sensor.
- **Version** is the processor version from the files' root `version`
  attribute (`8.1`). The config declares it, and the build and verifier check
  it against every orbit file.
  - The `0110` in the file names is the product version, recorded as
    `source_product_version`, and does not name the stores.
- There is no product token.
