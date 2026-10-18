# Nomenclature Key — TROPOMI (SRON HDO L2, processor 8.1)

Maps the SRON TROPOMI HDO Level 2 product onto the authoritative
[nomenclature_data.md](/glade/u/home/kheyblom/work/style_guides/nomenclature_data.md),
as the data engineering style guide requires.

**This file is machine read.** `utils/nomenclature.py` parses the three tables
below. It is the only place the pipeline learns what a variable is called, what
its units are, and how its values are converted. Edit the tables, not the code.
Columns are matched by header name: reorder them freely, but do not rename them.

- `original_variable_name` is the HDF5 path inside the orbit file
  (`<group>/<variable>`). There are no root variables.
- `unit_conversion` is parsed: `none`, or `x <factor>`, where the factor is
  numbers and the constant `N_A` (6.02214076e23 mol-1, exact SI) joined by `*`
  and `/`. The build multiplies in float64 and stores the source dtype.
- `original_units` is documentation. The build records the units string read
  from the file on each store.

## Variable Key

| original_variable_name | original_units | canonical_name | canonical_units | canonical_long_name | unit_conversion | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `target_product/deltad` | `1` | `water_vapor_column_delta_d` | `1e-3` | delta D of the total water vapor column | x 1000 | fraction to per mil |
| `target_product/deltad_precision` | `1` | `water_vapor_column_delta_d_standard_error` | `1e-3` | standard error of delta D of the total water vapor column | x 1000 | fraction to per mil |
| `target_product/h2o_column` | `molec. cm-2` | `water_vapor_column_h2o` | `mol m-2` | total column of water vapor (H2O) | x 1e4 / N_A | molec cm-2 to mol m-2 |
| `target_product/h2o_column_precision` | `molec. cm-2` | `water_vapor_column_h2o_standard_error` | `mol m-2` | standard error of the total column of water vapor (H2O) | x 1e4 / N_A | molec cm-2 to mol m-2 |
| `target_product/hdo_column` | `molec. cm-2` | `water_vapor_column_hdo` | `mol m-2` | total column of HDO water vapor | x 1e4 / N_A | molec cm-2 to mol m-2 |
| `target_product/hdo_column_precision` | `molec. cm-2` | `water_vapor_column_hdo_standard_error` | `mol m-2` | standard error of the total column of HDO water vapor | x 1e4 / N_A | molec cm-2 to mol m-2 |
| `diagnostics/processing_quality_flags` | (none) | `quality_flags_retrieval` | `unitless` | retrieval quality flags | none | int32; mandatory in every run; CF flag attributes carried |
| `diagnostics/iterations` | `1` | `iterations_retrieval` | `unitless` | number of retrieval iterations | none | int32 |
| `instrument/scanline` | `1` | `scanline_index` | `unitless` | zero-based along-track scanline index of the observation in its Level 1B file | none | int32; with `ground_pixel_index`, the pixel's address on the L1B grid (decided 2026-10-18) |
| `instrument/ground_pixel` | `1` | `ground_pixel_index` | `unitless` | zero-based across-track ground pixel index of the observation in its Level 1B file | none | int32; 0..214 across the swath (decided 2026-10-18) |
| `instrument/solar_zenith_angle` | `degrees` | `solar_zenith_angle` | `degree` | solar zenith angle | none | respelled only |
| `side_product/aerosol_optical_thickness` | `1` | `optical_thickness_scattering_layer` | `unitless` | optical thickness of the retrieval's effective scattering layer | none | `nwin` squeezed; Table 1 "cloud optical thickness" |
| `side_product/aerosol_height` | `m` | `height_scattering_layer` | `m` | height of the centre of the retrieval's effective scattering layer above the surface | none | Table 1 "cloud height" |
| `side_product/surface_albedo` | `1` | `albedo_surface_2365nm` | `unitless` | surface albedo at 2365 nm | none | `nwin` squeezed |
| `diagnostics/chi_squared` | `1` | `chi_squared_retrieval` | `unitless` | unreduced chi-squared of the final retrieval fit residual | none | unreduced, as published |
| `diagnostics/chi_squared_prefit` | `1` | `chi_squared_prefit` | `unitless` | unreduced chi-squared of the retrieval pre-fit residual | none | unreduced, as published |
| `diagnostics/number_of_spectral_points_in_retrieval` | `1` | `spectral_point_count_retrieval` | `unitless` | number of spectral points used in the final retrieval fit | none | int32; `nwin` squeezed |
| `diagnostics/number_of_spectral_points_in_prefit` | `1` | `spectral_point_count_prefit` | `unitless` | number of spectral points used in the retrieval pre-fit | none | int32; `nwin` squeezed |

- **δD** is published as a fraction (`ratio / standard_ratio - 1`, with
  `standard_ratio` 0.00031153). It becomes per mil, the canonical `1e-3`.
- **Columns** are published in molecules per cm². x 1e4 converts cm-2 to m-2,
  and / N_A converts molecules to moles.
- **`unitless`** is the canonical spelling of SRON's `1`, and of no units
  attribute at all for `processing_quality_flags`. No value changes.
- **Reduced chi-squared** is not stored. It is `chi_squared` divided by the
  matching spectral point count, which is inferred (no source defines it; see
  `docs/products/tropomi.md`). Both inputs are stored so users can form it.

## Coordinate Key

The geolocation store's per-observation coordinates. `nomenclature_data.md`
has no coordinate rows. The gridded stores keep `time`, `lat` and `lon`, and so
does this product.

| original_name | original_units | name | units | unit_conversion | notes |
| --- | --- | --- | --- | --- | --- |
| `instrument/time` | `year month day hour minute second millisecond` | `time` | `milliseconds since 1900-01-01` | decoded | broken-down int32 (obs, 7) decoded to a timestamp; int64, proleptic_gregorian |
| `instrument/latitude_center` | `degrees north` | `lat` | `degrees_north` | none | pixel centre; respelled only |
| `instrument/longitude_center` | `degrees east` | `lon` | `degrees_east` | none | pixel centre; respelled only |
| `instrument/latitude_corners` | `degrees north` | `lat_corners` | `degrees_north` | none | the pixel's 4 corners on `corner` (decided 2026-10-18); respelled only |
| `instrument/longitude_corners` | `degrees east` | `lon_corners` | `degrees_east` | none | the pixel's 4 corners on `corner` (decided 2026-10-18); respelled only |

## Temporal Frequency Key

| original_frequency_name | canonical_name | canonical_long_name |
| --- | --- | --- |
| `observation` | `inst` | instantaneous observation |

SRON names no temporal frequency. Each record is one instantaneous retrieval,
so `observation` is this project's own word for it, used in the configs.

## Dimensions

| source | store | note |
| --- | --- | --- |
| `nobs` | `obs` | the L1B swath flattened scanline then ground pixel; concatenated over orbits in orbit order |
| `nwin` | (squeezed) | length 1 |
| `ncorner` | `corner` | the 4 pixel corners, in the geolocation store's `lat_corners` and `lon_corners`. Corners 0-1 are the back edge (toward the previous scanline) and 2-3 the front; a pixel's corners 1 and 2 are exactly the next ground pixel's corners 0 and 3 (measured 2026-10-18) |
| `nlayer`, `nlevel` | `layer`, `level` | none in the current subset |

## Store naming (decided 2026-10-14)

```
<zarr>/wisosat.tropomi.<version>.inst.native_swath.<variable>.zarr
<zarr>/wisosat.tropomi.v_8_1.inst.native_swath.water_vapor_column_delta_d.zarr
<zarr>/wisosat.tropomi.v_8_1.inst.native_swath.geolocation.zarr
```

- **Data source** is `wisosat.tropomi`: the collection, then the sensor.
- **Version** is the processor version from the files' root `version`
  attribute (`8.1`). The config declares it, and the build and verifier check
  it against every orbit file.
  - The `0003` in the file names is the product version and is not used.
- There is no product token.
