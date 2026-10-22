# SCIAMACHY (SRON SICOR L2 H2O/HDO, file version 0110)

In progress (2026-10-22): audit and subset proposal. First measured 2026-10-14 from header reads and one file's values.

## Raw data

```
raw/SCIAMACHY/HDO_SICORv10/<YYYYMM>/sci_l2_h2o_hdo_0110_<orbit:05d>.nc   (~4 MB)
```

- 41,616 files, one per orbit, across 112 month folders (2003-01 .. 2012-04);
  ~1,876 obs per file, ~7.8e7 in all.
- **Same file format as TROPOMI** (same SRON Sicor processor, `version` 8.1):
  - groups `target_product`, `instrument`, `diagnostics`, `meteo`,
    `side_product`;
  - observation dim `nobs`, with `instrument/time` as a 7-integer broken-down
    timestamp;
  - no `_FillValue` attributes.

  Expect to reuse most of the TROPOMI reader. That is also why SCIAMACHY is a
  poor choice for the "deliberately different" second reader.
- **Dims:** `nlayer` 60, `nlevel` 61, `ncorner` 4, `nwin` 1, `ntime` 7;
  `side_product` adds `nbaseline` 4.
- **Fill:** no `9.96921e36` was seen in the sampled file, but check the fill
  convention against several files before declaring it. Some retrieved
  columns are negative (e.g. `hdo_column` -9.3e16), which is real retrieval
  output, not fill.
- **Not SCIAMACHY:** `raw/SCIAMACHY/H2O` and `raw/SCIAMACHY/HDO` hold ESA
  MIPAS files and are excluded.

## Variables and units

- `target_product/h2o_column` and `hdo_column`, their `_precision`s and
  `_apriori`s are in `molec. cm-2` and convert to `mol m-2` (x 1e4 / N_A).
  - Value check, one file: p50 1.1e22 and 4.3e18.
- Column averaging kernels on `nlayer` (`1`, p50 0.27) and a priori profiles
  on `nlayer`.
- **No δD is published.** WISO-SAT derives it; deriving it here would be a new
  quantity, not a conversion, and needs approval.
- Quality flag: `diagnostics/processing_quality_flags`.

## Filtering guidance to record, not apply (Sarkar et al. 2026)

- flag 0, iterations < 12, SZA < 70°;
- 0.7 <= H2O/H2O_apriori <= 1.3 and 0.9 <= CH4/CH4_apriori <= 1.1;
- -600 < δD < 0 per mil;
- log(RMS) within ±6σ of its median; log(uncertainty) for H2O and HDO within
  ±5σ, per file.

## Geolocation

- Granule: an orbit file.
- Geolocation store: ~1.25 GB (lat/lon/time) plus 19 GB for the pressure grid
  (61 levels), uncompressed.

## Model-comparison variables (named 2026-10-19)

Named in the cross-product naming pass. The grammar and decisions are in
`docs/model-comparison-naming.md`; the rows are in `nomenclature_data.md`
(style_guides `fee64ec`). Units are after conversion. Not built yet.

- **Dims:** `nlayer` (60) becomes `layer`; `nlevel` (61) becomes `level`, the
  layer interfaces.
- **Vertical order:** `top_first` (level 0 is 0 Pa), as TROPOMI.

| source | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- |
| `target_product/h2o_column_averaging_kernel` | `water_vapor_column_h2o_averaging_kernel` | unitless | (obs, layer) | none |
| `target_product/hdo_column_averaging_kernel` | `water_vapor_column_hdo_averaging_kernel` | unitless | (obs, layer) | none |
| `target_product/h2o_profile_apriori` | `water_vapor_partial_column_h2o_apriori` | mol m-2 | (obs, layer) | x 1e4 / N_A from `molec. cm-2` |
| `target_product/hdo_profile_apriori` | `water_vapor_partial_column_hdo_apriori` | mol m-2 | (obs, layer) | x 1e4 / N_A |
| `meteo/dry_air_subcolumns` | `dry_air_partial_column` | mol m-2 | (obs, layer) | x 1e4 / N_A |
| `meteo/pressure_levels` | `pressure` (its own store since 2026-10-19) | Pa | (obs, level) | none; layer interfaces |

- SRON calls the priors "profile", but they are partial columns: "A-priori
  vertically integrated partial column of water in layers", in molec cm-2
  per layer. Hence `partial_column`.
- **Total-column priors** are also published (`h2o_column_apriori`,
  `hdo_column_apriori`, both (obs), molec cm-2). They have no rows yet; by
  the grammar they are `water_vapor_column_{h2o,hdo}_apriori`. This is the one
  case where `column` and `partial_column` tell two variables apart.
- **Stores:** 5 variable stores, plus `pressure` as a store of its own.

## Production subset (decided 2026-10-22; three points still open)

Reviewed by the user in place, 2026-10-22. P1, P2, P4, P6 and most of P3 are
approved. Still **open**, marked below: the RMS name (P3a), CH4 final only
(P3b) and `pixel_id` (P3c). Review those with `#@CLAUDE` comments. The new
rows go to style_guides for review before commit.

Facts behind it, from the audit of every file on 2026-10-22 (S2; TESTING.md
finding 13), a fill-by-flag pass over the 756 files with fill, and one-file
probes:
- All 41,616 files open, are version 8.1 and share one layout: 78,666,953
  obs, every row with time, lat and lon. Every dataset is contiguous.
- Quality flags over the record: 0 on 78,241,717 rows (99.46%); 2
  (dead spectrum) 258,132; 5 (side retrieval failure) 123,108; 4
  (convergence error) 39,338; 2048 (weak spectrum warning) 3,585; 3
  (numerical error) 719; 96 (netCDF error) 354.
- **What the stores hold on flagged rows** (fill never occurs on a flag-0
  row):

  | stores | flag 0, 2048 | flags 2, 3, 4, 5 | flag 96 (354 rows) |
  | --- | --- | --- | --- |
  | geolocation, `pressure`, `dry_air_partial_column`, SZA, the flag, every a priori (total and partial columns, CH4) | written | written | written |
  | H2O and HDO columns and errors, both kernels, iterations, CH4, chi-squared, albedo | written | fill | fill on 288-354 |
  | RMS, spectral point count | written | fill | fill on all 354 |

  So a user who keeps flag 0 never meets fill. The a priori, meteo and
  geometry stores are complete on every row. Fill is masked to NaN (ints
  keep int32 with a `_FillValue`), as TROPOMI's.
- `aerosol_optical_thickness` and its precision are fill on every row of the
  record, and `aerosol_height_precision` on all but 128. `aerosol_height`
  equals its a priori on 961,977 of 962,105 rows in the 756 files checked
  (S6).
- The total-column priors equal the sums of their partial-column priors to
  float32 precision (S7).

**What the retrieval is** (Schneider et al., 2018, AMT 11, 3339, Sect. 2).
SICOR has two modes:
- **Non-scattering (this product):** one fit over 2338.5-2382.5 nm retrieves
  the total columns of H2O, HDO, CH4 and CO together with a Lambertian
  surface albedo, ignoring scattering. The cloud filter therefore compares
  the CH4 retrieved in the same fit with its TM5 prior (their eq. 2).
- **Scattering:** CH4 is held to its prior to infer the height and optical
  depth of a scattering layer, with the other columns.

This explains S6: no scattering layer is fitted, so its optical thickness is
never written and its height stays at the a priori. They add: "The ratio δD
may be computed a posteriori from these data but is not a primary product."

### P1. Store version: `v_8_1` (approved)

- store names `wisosat.sciamachy.v_8_1.inst.native_swath.<variable>.zarr`,
  from the root `version` `8.1`, checked on every file;
- `0110`, from the file names, recorded as `source_product_version`, as
  TROPOMI's `0003`.

### P2. δD: left out (approved)

The stores hold only what SRON published. The filtering guidance (P5) gives
the δD definition, so a user can form it for the -600 < δD < 0 cut. Why:
- deriving is a new quantity, not a conversion (project rule);
- no exact standard error can be derived, since the HDO-H2O error correlation
  is not published;
- SRON call δD "not a primary product";
- the plain ratio is very noisy per sounding (flag-0 medians of -27 to +92
  per mil and p1/p99 near ±3,000 in three files).

### P3. The 1-D stores (approved, but for P3a-c)

The user's rule (2026-10-22): **align with the stores TROPOMI has**, plus
what Sarkar et al. (2026) filter on. TROPOMI's 1-D set and its SCIAMACHY
counterpart:

| TROPOMI store | SCIAMACHY |
| --- | --- |
| `water_vapor_column_delta_d`, `_standard_error` | none: not published (P2) |
| H2O and HDO columns and errors, `quality_flags_retrieval` | stored |
| `iterations_retrieval`, `solar_zenith_angle` | stored |
| `albedo_surface_2365nm` | stored as `albedo_surface_2360nm` (*new*): SRON's label is "at 2360 nm" |
| `chi_squared_retrieval`, `spectral_point_count_retrieval` | stored |
| `chi_squared_prefit`, `spectral_point_count_prefit` | none: not in the files |
| `optical_thickness_scattering_layer` | none: fill on every row (S6) |
| `height_scattering_layer` | none: not retrieved, only a copy of its a priori (S6) |
| `scanline_index`, `ground_pixel_index` | none: no scanlines or ground pixels; `pixel_id` is P3c |

**Core: the retrieval plus the mandatory flag** (all rows exist).

| source | canonical_name | units | conversion |
| --- | --- | --- | --- |
| `target_product/h2o_column` | `water_vapor_column_h2o` | mol m-2 | x 1e4 / N_A |
| `target_product/h2o_column_precision` | `water_vapor_column_h2o_standard_error` | mol m-2 | x 1e4 / N_A |
| `target_product/hdo_column` | `water_vapor_column_hdo` | mol m-2 | x 1e4 / N_A |
| `target_product/hdo_column_precision` | `water_vapor_column_hdo_standard_error` | mol m-2 | x 1e4 / N_A |
| `diagnostics/processing_quality_flags` | `quality_flags_retrieval` | unitless | none (int32; mandatory) |

**Filter inputs and TROPOMI's counterparts.** Rows marked *new* need adding
(6 rows).

| source | canonical_name | units | conversion | why |
| --- | --- | --- | --- | --- |
| `diagnostics/iterations` | `iterations_retrieval` | unitless | none (int32) | iterations filter |
| `instrument/solar_zenith_angle` | `solar_zenith_angle` | degree | none (respell `degrees`) | SZA filter |
| `target_product/h2o_column_apriori` | `water_vapor_column_h2o_apriori` *new* | mol m-2 | x 1e4 / N_A | H2O / prior filter |
| `target_product/hdo_column_apriori` | `water_vapor_column_hdo_apriori` *new* | mol m-2 | x 1e4 / N_A | the prior pair (approved) |
| `side_product/ch4_column` | `methane_column` *new* (approved name) | mol m-2 | x 1e4 / N_A | CH4 / prior cloud filter |
| `side_product/ch4_column_apriori` | `methane_column_apriori` *new* | mol m-2 | x 1e4 / N_A | as above |
| `diagnostics/rms` | `rms_residual_retrieval` *new* (P3a) | mol s-1 m-2 nm-1 sr-1 | none (respell: `ph.` moves to the long_name) | RMS filter |
| `side_product/surface_albedo` | `albedo_surface_2360nm` *new* | unitless | none (squeeze `nwin`) | as TROPOMI |
| `diagnostics/chi_squared` | `chi_squared_retrieval` | unitless | none (unreduced) | as TROPOMI |
| `diagnostics/number_of_spectral_points_in_retrieval` | `spectral_point_count_retrieval` | unitless | none (int32; squeeze `nwin`) | as TROPOMI |

The precisions in the core serve the log-uncertainty cut.

**P3a, open: why `rms_residual_retrieval` and not `rms_retrieval`.**
- A data-lake name must say what it measures without the product's context.
  RMS is a statistic of *something*: of a radiance, of noise, of an error.
  `rms_retrieval` would most naturally read as the RMS error of the retrieved
  columns, a different quantity.
- SRON's own definition is "Root mean square fit residual", and Schneider et
  al. call it "the root mean square of the spectral fit residual". The unit
  is a radiance, which only makes sense for the residual.
- `chi_squared_retrieval` needs no `residual`, because chi-squared is by
  definition a statistic of a fit's residual; its row's long_name says so.
- The order follows the naming rule: the statistic, then what it is of,
  then which fit.
- The unit drops `ph.` because it is a label (photons), not a unit; the
  long_name keeps it: "root mean square of the final retrieval fit residual
  radiance, in photons".

**P3b, open: store `ch4_column` and leave out `ch4_column_prefit`
(recommended).**
- **The difference.** `ch4_column` is the CH4 retrieved in the same fit that
  gives the H2O and HDO columns. That is the c_CH4 of Schneider et al.'s
  cloud filter, "the retrieved columns c_CH4 and c_H2O", and so the one
  Sarkar et al. take over.
- `ch4_column_prefit` comes from a preliminary SICOR step run before that
  fit. In the scattering mode it sets up the scattering-layer parameters; in
  this product nothing downstream uses it.
- **Evidence that it is a separate, earlier step:** it is written on every
  flag 3, 4 and 96 row (40,411), where the final CH4 is fill on all but 3.
  It is fill exactly where the spectrum was unusable (flag 2) or a side
  retrieval failed (flag 5).
- Their ratios to the prior are nearly the same on flag-0 rows (p50 0.78-0.83
  for both in three files), so storing it would add little. TROPOMI also left
  out its `ch4_column_prefit`, and its other CH4 and CO side products.
- Storing both is the alternative (one more store, ~300 MB, and a row).

**P3c, open: `pixel_id`, no store (recommended), if the verifier confirms it
on every file.**
- TROPOMI's `scanline_index` and `ground_pixel_index` exist only because 83
  of its granules had rows left out. There, an obs's position in the store no
  longer gave its source row (`tropomi.md`, Swath position).
- SCIAMACHY's `pixel_id` ("One-based pixel index in Level 1B file") is the
  source row + 1 in the three files looked at (15838 across its copies,
  45262 and 45263); the whole record is not checked yet.
- Both rows-left-out cases (P6) drop only rows after the last row kept. So
  the granule index gives every obs's source row, and `pixel_id` follows:
  obs index - `granule_obs_start` + 1.
- `check_granule` would confirm `pixel_id` = row + 1 on every file, as
  TROPOMI's checks its scanline layout. If any file breaks it, `pixel_id` is
  stored as `pixel_index_l1b` (*new* row) instead.

**Left out, as TROPOMI left them out:** `ch4_column_prefit`,
`ch4_column_precision`, `co_*`, `spectral_shift`, `baselinecorrection`,
`integration_time`, `snr`, `degrees_of_freedom_total`, `cloud_fraction`,
`averaged_reflectance_signal`, the azimuth and viewing angles, `l1b_file`,
the other `meteo` variables, and the aerosol variables (S6).

### P4. Geolocation and the model-comparison stores (approved)

- **Geolocation:** `time`, `lat`, `lon`, and the pixel corners
  (`instrument/{latitude,longitude}_corners`, `corner` 4, ~2.5 GB), as
  TROPOMI.
- **Model comparison:** the 5 variable stores named on 2026-10-19 (table
  above), plus `pressure` as its own store (Pa, 61 levels).
  - The 60-layer stores are ~19 GB each uncompressed.
  - By the chunk rule, 131,072 obs (30 MiB) per chunk, ~600 chunks per array,
    so no shards are needed.
  - Compression (default zstd, or blosc zstd 5 + shuffle as TROPOMI's wide
    arrays) is measured at the bench.

That makes **22 stores**: geolocation, 5 core, 10 filter and TROPOMI-aligned
inputs, 5 model-comparison and `pressure`, on 78,666,953 - 624 - 32 =
78,666,297 obs.

### P5. Filtering guidance in the metadata

Recorded, not applied, citing both sources:
- **Sarkar et al. (2026), WISO-SAT:** flag 0, iterations < 12, SZA < 70°;
  0.7 <= H2O/H2O_apriori <= 1.3 and 0.9 <= CH4/CH4_apriori <= 1.1; -600 < δD
  < 0 per mil; log(RMS) within ±6σ of its median; log(uncertainty) for H2O
  and HDO within ±5σ.
- **Schneider et al. (2018), the product paper:** the same ratio cuts
  (strict inequalities), iterations <= 12 (not < 12), SZA < 70°. σ is half
  the 15.9th to 84.1st percentile range of the log distribution, about its
  median.
- **δD,** as SRON define it in their TROPOMI files of the same processor:
  `(hdo_column / h2o_column) / 3.1153e-4 - 1`.
- **On flagged rows,** the retrieval stores hold fill (the table above); the
  a priori, meteo and geometry stores are complete.

### P6. The two time-order defects (approved; one exception to the guide)

The style guide requires time never to decrease along `obs`, and every
observation kept in source order. Both cases are declared in config, never
detected, and each is checked by the build and the verifier.

**S8, orbit 15838 (2005-03-11), triplicated: keep the first copy.** Its 936
rows are the same 312 observations three times (rows 0-311, 312-623,
624-935), identical in every variable but `pixel_id`. The build and the
verifier check that rows 312-935 equal rows 0-311 in every source but
`pixel_id` before leaving them out. The index keeps `granule_source_rows`
936. The 624 rows are repeats, not observations, so nothing is lost.

**S9, orbits 45262 and 45263 (2010-10-27), overlapping: leave out the last
32 rows of 45262.**
- **The defect:** the two L1B files overlap in time (45262's ends 02:52:24,
  45263's starts 02:52:05). Rows 253-284 of 45262 and rows 0-31 of 45263 have
  the same time, position and meteo, but different retrievals. All of 45262
  (285 rows) used 143 spectral points, with an RMS ~1000x smaller, against
  273 in 45263, as in normal orbits. All 64 rows are flag 0.
- **The exception:** this is the user's decision of 2026-10-22, an exception
  to "never select observations", for this case only and not a precedent.
  45263's retrieval of the 32 scenes is kept because it is the one made with
  the normal spectral setup. Keeping both would have broken "time never
  decreases"; the guide allows neither, and the user chose this.
- **The checks:** the build and the verifier confirm that the 32 rows left
  out have exactly the time, lat and lon of 45263's rows 0-31, and that 45262
  then ends before 45263 begins.
- **The record:** the store metadata (`known_data_gaps`), this doc,
  STATE.md's decisions and the config all name the exception, the rows and
  the reason. The other 253 rows of 45262 are kept as published, with their
  odd spectral setup recorded (record only).

**Shared code this needs:** one declared block in config, rows a granule
leaves out, each with the check it must pass (`repeat_of` rows, or `overlap`
with the next granule) and its reason. It is read by the build and the
verifier, so every product's fixture re-runs after it.

## Known data issues

Status: **handled** (the pipeline deals with it), **open** (settle before this product is built), **record only** (users should know; kept as published).

| # | issue | status |
| --- | --- | --- |
| S1 | **`raw/SCIAMACHY/H2O` and `raw/SCIAMACHY/HDO` hold ESA MIPAS files**, a different Envisat instrument that is not in WISO-SAT. | handled: excluded |
| S2 | **Same SRON format as TROPOMI**, so TROPOMI's T1-T17 (`tropomi.md`) might apply. Audit of every file, 2026-10-22 (TESTING.md finding 13): no shells, partial, unreadable or wrong-version files, and no row without time, lat or lon. The netCDF default fills occur, undeclared, on 421,648 flagged rows (see the Proposal). | handled: fills to declare in `source_fill_values`, as TROPOMI's |
| S3 | **Negative retrieved columns** (e.g. `hdo_column` -9.3e16) are real retrieval output, not fill. | record only |
| S4 | **No δD is published**; WISO-SAT derives it. SRON: "may be computed a posteriori ... but is not a primary product" (Schneider et al., 2018). | handled: left out (user decision 2026-10-22, P2); the definition is in the filtering guidance |
| S5 | **Hidden transfer leftovers in the raw tree** (found 2026-10-22): 24 `.ArchiveServiceTemp.sb-*` folders hold 3,350 files whose names all also exist in the month folders. 3,339 have the same size as the month-folder copy; 11 are truncated (0 B or a whole number of MiB). 201 names occur more than once among them. Also one `.DS_Store`. The month folders hold 41,616 files, 173 GB, with no repeated name. | handled: only `YYYYMM` folders are listed. Deleting the leftovers (~14 GB) is the user's call |
| S6 | **The scattering layer is not retrieved** (the non-scattering mode, Schneider et al., 2018): `aerosol_optical_thickness` and its precision are fill on every row of the record, `aerosol_height_precision` on all but 128, and `aerosol_height` equals its a priori on 961,977 of 962,105 rows in the 756 files checked. | record only: none of them stored (P3), so SCIAMACHY has no scattering-layer stores |
| S7 | **The total-column priors are the sums of the partial-column priors**, for H2O and HDO, to float32 precision (three files). | record only |
| S8 | **Orbit 15838 (2005-03-11) is triplicated**: 936 rows, the same 312 observations three times, identical but for `pixel_id`. Time steps back twice. | handled: the first copy kept, the repeats checked equal and left out (user decision 2026-10-22, P6) |
| S9 | **Orbits 45262 and 45263 (2010-10-27) overlap by 32 scenes**, retrieved twice from overlapping L1B files with different spectral setups (143 vs 273 points). Time steps back 18.5 s at the seam. | handled: 45262 rows 253-284 left out, checked against 45263 rows 0-31. **A one-time exception** to "never select observations" (user decision 2026-10-22, P6) |
| S10 | **The millisecond field reaches 1000** in 759 files, meaning the next whole second (`...:06.1000` is `:07.000`). | handled: `decode_time` (pandas) carries it; checked across a year end |
| S11 | **Month folders are by orbit start.** 41 orbits run across a month end, and 24 have their first observation after midnight on the 1st, so 65 files hold times outside their folder's month. | handled: granules are ordered by orbit number, never by folder |
