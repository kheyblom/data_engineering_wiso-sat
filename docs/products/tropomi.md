# TROPOMI (SRON HDO L2, product version 0003)

Product notes for the TROPOMI reader, configs and key. Rules that apply to every
product are in the root `CLAUDE.md` and the style guide; cross-product evidence
is in `docs/l2-survey.md`.

## Raw data (measured 2026-10-13/14)

```
/glade/derecho/scratch/kheyblom/data/wisosat/raw/TROPOMI/tropomi.grid.surfsara.nl/
  hdo/<YYYY>/<MM>/<DD>/<orbit>/s5p_l2_hdo_<product_version>_<orbit:05d>.nc
  hdo/2017/11/08/373/s5p_l2_hdo_0003_00373.nc     (~1.1 GB each)
```

- **Files:** 31,492 orbit directories from 2017-11-08 to 2024-05-30, but
  only 30,800 orbit files: 692 directories are empty. **The download is
  incomplete:**
  - 339 of the empty orbits, and 12 of the 70 missing days, exist upstream;
  - the rest are real upstream gaps, declared in the config;
  - details are in `tropomi-download-gaps.md` (checked against the server,
    2026-10-14). Orbits per day
  vary (5-14 seen); not every orbit has a file. Product version `0003` (from
  the filename); processor version `8.1` (root `version` attribute) in all 11
  files sampled across 2017-2024 (2026-10-14). The stores are named by the
  processor version.
- **Missing days:** 70 days have no day directory here. 58 are absent
  upstream too (`expected_missing_days`), and 12 are a download gap. The tree also holds 195 stray
  `.DS_Store` files, which the reader skips.
- **Groups:** there are no root variables, so open each group with `group=`.
  - `target_product`: deltad, h2o/hdo columns, precisions, averaging kernels,
    a priori profiles.
  - `instrument`: lat/lon centre and corners, time, geometry, pixel ids.
  - `diagnostics`: the flags.
  - `meteo` and `side_product`.
- **Observation layout:** everything is indexed by `nobs`, the full L1B swath
  flattened in scanline-then-pixel order (e.g. 4173 x 215 = 897,195).
  - Scanline = i // 215 and ground pixel = i % 215 within an orbit. The
    verifier must confirm this for every orbit.
  - `nobs` is ~697,800 per orbit in 2018-2019 and ~897,000 from 2020 on
    (the Aug 2019 along-track resolution change), but varies more than that:
    625,220 to 1,204,215 were seen in 11 files sampled 2026-10-14. Each is a
    whole number of 215-pixel scanlines.
  - The record totals ~2.6e10 observations: ~105 GB uncompressed per 1-D
    float32 variable, ~5.2 TB per `(obs, 50)`.
- **Secondary dims:**
  - `nlayer` 50, `nlevel` 51, `ncorner` 4;
  - `nwin` 1 (squeeze);
  - `ntime` 7: `instrument/time` is a broken-down timestamp
    (year .. millisecond) that becomes `time`.
- **Fill:** there is no `_FillValue`. Missing values are the netCDF default
  float fill `9.96921e36`, so declare it in config and mask it.
  - In orbit 16820, 71% of `nobs` have an `hdo_column` and 65% have
    `processing_quality_flags == 0`.
- **Flags:** `quality_flag`, `convergence` and `glintflag` are "Not
  implemented". `processing_quality_flags` is the real flag (CF
  `flag_masks`/`flag_values`).
- **Storage:** each variable is one HDF5 chunk spanning the whole variable,
  zlib level 1 with shuffle (corrected 2026-10-14; earlier noted as
  uncompressed). Reading the 19 variables of one orbit took 2.6 s cold.
- **Units:**
  - `deltad` is a fraction (`1`; median -0.25), so it converts x 1000 to per
    mil.
  - Columns are `molec. cm-2`. Some units are byte strings (`b'1'`); decode
    them.
- **`standard_name`s** are SRON's own (`delta_d`, `water_column`, ...). Keep
  them unchanged, per the guide.
- **Day boundary:** in the sampled pair, orbits did not straddle UTC midnight.
  The build checks `time` never decreases.
- **Value notes:**
  - `processing_quality_flags == 0` still passes δD from -0.99 to +13
    (p1/p99) and `h2o_column` up to 1.7e26, so more filtering is needed
    downstream.
  - The column kernels reach p99 ~700 in some layers; this is unexplained and
    not a unit issue.

## Build details (built 2026-10-14; fixture passes, bench next)

- **Granule:** an orbit. The granule index has ~31.5k entries and is stored as
  one chunk. Resume starts after the last committed orbit, whose index entry
  is written in the same commit as its data.
- **Appends:** orbit sizes vary, so appends do not land on chunk boundaries.
  Each append rewrites the trailing partial chunk, which is safe only with a
  single writer.
- **Missing days:** declared in config as `expected_missing_days`. The build
  fails on any gap that is not declared.
- **Fill as measured in orbit 13847:** the float fill 9.96921e36 occurs in
  every float source of the subset except `solar_zenith_angle`, `lat` and
  `lon`. The int fill -2147483647 occurs in `iterations` and both
  spectral-point counts, but not in `processing_quality_flags`.
  `deltad_precision` also holds real NaNs (5,447 in that orbit), which stay
  NaN. The verifier fails if a declared fill never occurs over the record, or
  if an undeclared netCDF default fill occurs anywhere.
- **Fixture:** `validation/stage_tropomi.py` writes orbits 13857, 13870,
  13871, 13899 and 13900, each cut to 23-47 mid-orbit scanlines (38,055 obs).
  2020-06-18, a real upstream gap, falls between them.
- **Chunking starting points for the bench** (the guide allows 5-40 MiB):
  - 4,194,304 obs for 1-D float32 (16 MiB);
  - 131,072 obs for `(obs, 50)` float32 (25 MiB).
- **Geolocation store:**
  - `time`;
  - `lat`, `lon` (pixel centre);
  - `pressure` on `level` (`meteo/pressure_levels`, 51 interfaces, Pa), only
    once the model-comparison set is produced: the kernels are what need it;
  - pixel corners, optional (`corner`, 32 B/obs).
- **Filtering guidance to record in metadata, not apply.** Schneider et al.
  (2022) Table 1, read from the publisher's image. Sarkar et al. (2026)
  apply the all-scene and clear-sky rows.
  - All scenes:
    - iterations <= 10;
    - reduced chi-squared of the final fit <= 150;
    - reduced chi-squared of the pre-fit <= 150;
    - SZA <= 70°.
  - Clear sky: cloud optical thickness < 0.3 and surface albedo >= 0.02.
  - Cloudy scenes: cloud height <= 2000 m and cloud optical thickness > 0.3.
  - Schneider et al. recommend clear-sky and low-cloud scenes.
- **What Table 1's terms are in the file:**
  - **Cloud optical thickness and height:** these are `aerosol_optical_thickness`
    and `aerosol_height`, SRON's effective scattering layer. The evidence:
    - the paper fixes the layer's thickness d at 2500 m, and
      `aerosol_geometric_thickness` is 2500 m on every pixel;
    - SRON's PUM for the successor PAL product (SRON-ESG-RP-2024_020)
      uses `aerosol_optical_thickness < 0.3` for clear sky.
  - **Reduced chi-squared:** this is `chi_squared` / `number_of_spectral_points_*`,
    which is inferred because no source defines it. In orbit 13847
    (2020-06-15, flag 0):
    - the median is ~10;
    - 92% (final fit) and 99% (pre-fit) pass <= 150.
    The alternative divisor, points minus degrees of freedom, differs by
    ~2.5%. The counts vary per pixel (270-277 final, 309-316 pre-fit), so
    the raw inputs are stored and the reduction is recorded as inferred.
  - **No CH4 filter:** CH4 only drives the pre-fit of the cloud parameters.
  - **Negative albedo:** flag-0 pixels reach negative surface albedo (p1
    -0.95); the albedo >= 0.02 cut removes them.

## Production subset (decided 2026-10-14)

There are 16 one-dimensional stores, ~1.7 TB uncompressed. The rows are in
`nomenclature_data.md` (style_guides `fd94a93`).
- **Naming rule:** the quantity comes first, then qualifiers general to
  specific (location, component, fit, band).
- **Exception:** established terms stay whole (`solar_zenith_angle`).
- **`quality_flags_retrieval`** is shared across products; the store
  attributes carry each product's flag meanings.

**Core: the retrieval plus the mandatory flag.**

| source | canonical_name | units | conversion |
| --- | --- | --- | --- |
| `target_product/deltad` | `water_vapor_column_delta_d` | 1e-3 | x 1000 |
| `target_product/deltad_precision` | `water_vapor_column_delta_d_standard_error` | 1e-3 | x 1000 |
| `target_product/h2o_column` | `water_vapor_column_h2o` | mol m-2 | x 1e4 / N_A |
| `target_product/h2o_column_precision` | `water_vapor_column_h2o_standard_error` | mol m-2 | x 1e4 / N_A |
| `target_product/hdo_column` | `water_vapor_column_hdo` | mol m-2 | x 1e4 / N_A |
| `target_product/hdo_column_precision` | `water_vapor_column_hdo_standard_error` | mol m-2 | x 1e4 / N_A |
| `diagnostics/processing_quality_flags` | `quality_flags_retrieval` | unitless | none (int32; mandatory) |

**Filter inputs: everything Table 1 needs**, so users can filter without the
raw files.

| source | canonical_name | units | conversion |
| --- | --- | --- | --- |
| `diagnostics/iterations` | `iterations_retrieval` | unitless | none (int32) |
| `instrument/solar_zenith_angle` | `solar_zenith_angle` | degree | none (respell `degrees`) |
| `side_product/aerosol_optical_thickness` | `optical_thickness_scattering_layer` | unitless | none (squeeze `nwin`) |
| `side_product/aerosol_height` | `height_scattering_layer` | m | none (above surface) |
| `side_product/surface_albedo` | `albedo_surface_2365nm` | unitless | none (squeeze `nwin`) |
| `diagnostics/chi_squared` | `chi_squared_retrieval` | unitless | none (unreduced) |
| `diagnostics/chi_squared_prefit` | `chi_squared_prefit` | unitless | none (unreduced) |
| `diagnostics/number_of_spectral_points_in_retrieval` | `spectral_point_count_retrieval` | unitless | none (int32; squeeze `nwin`) |
| `diagnostics/number_of_spectral_points_in_prefit` | `spectral_point_count_prefit` | unitless | none (int32; squeeze `nwin`) |

**Deferred: model comparison.** These are 50 layers each, ~5.2 TB
uncompressed. With the pressure grid they total ~31 TB.
- Revisit after the bench measures how well kernels compress. A standalone
  scratch script measures it; that needs no nomenclature rows.
- No canonical names or nomenclature rows yet. At the second-reader step
  (GOSAT or TES), the kernels, priors and dry-air columns are named in one
  design pass across all products, following the naming rule.
  - Every product has kernels and priors, in different layouts:
    - column kernels: TROPOMI, SCIAMACHY, GOSAT;
    - block matrices: TES;
    - log-space ratio kernels: TROPESS;
    - SVD components: IASI;
    - priors as partial columns or as mole fractions.
  - A TROPOMI-only name would fix the pattern too early.

| source | units | conversion |
| --- | --- | --- |
| `target_product/h2o_column_averaging_kernel` | unitless | none |
| `target_product/hdo_column_averaging_kernel` | unitless | none |
| `target_product/h2o_profile_apriori` | mol m-2 | x 1e4 / N_A |
| `target_product/hdo_profile_apriori` | mol m-2 | x 1e4 / N_A |
| `meteo/dry_air_subcolumns` | mol m-2 | x 1e4 / N_A |

- **Left out unless asked:**
  - the other `meteo/` fields;
  - the CH4/CO side products;
  - the other aerosol and albedo parameters;
  - the remaining fit diagnostics.
