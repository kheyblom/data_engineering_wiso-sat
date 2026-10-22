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

## Proposal: store version, δD and the production subset (for review, 2026-10-22)

Review in place with `#@CLAUDE` comments. Once settled, this section becomes
"Production subset (decided ...)", as in `tropomi.md`, and the new rows go to
style_guides for review before commit.

Facts behind it, from one-file probes on 2026-10-22 (the full audit of every
file is running; S2):
- Every dataset is contiguous and the layout is the same in the 40 files
  sampled. Fill (9.96921e36, int -2147483647) occurs only on rows flagged 4
  or 5 (convergence error, side retrieval failure). Those rows have time and
  position, so they are observations and stay in.
- `aerosol_optical_thickness`, its precision and `aerosol_height_precision`
  are fill on every row sampled (S6).
- `h2o_column_apriori` and `hdo_column_apriori` equal the sums of their
  partial-column priors to float32 precision (ratio 1.000000 in three files;
  S7).

### P1. Store version: `v_8_1` (recommended)

The root `version` attribute is `8.1` in every file sampled. TROPOMI's files
also carry a four-digit product version in their name (`0003`); it went into
`source_product_version` and the stores are named from `version`. SCIAMACHY
follows the same rule:
- store names `wisosat.sciamachy.v_8_1.inst.native_swath.<variable>.zarr`;
- `0110` recorded as `source_product_version`, checked on every file name.

### P2. δD: leave it out (recommended)

SCIAMACHY publishes no δD (S4). Two options:
- **Leave it out (recommended).** The stores hold only what SRON published.
  The filtering guidance gives the definition SRON uses in its TROPOMI files
  of the same processor, `delta_d = (hdo_column / h2o_column) / 3.1153e-4 - 1`,
  so a user can form it for the -600 < δD < 0 cut. Reasons:
  - deriving would be a new quantity, not a conversion (project rule);
  - no standard error can be derived exactly: the HDO-H2O error correlation
    is not published;
  - the plain ratio is not obviously what WISO-SAT used. On flag-0 rows of
    three files it gives medians of -27 to +92 per mil and p1/p99 of about
    ±3,000, so single soundings are very noisy, and WISO-SAT may have
    averaged or bias-corrected before applying the cut.
- **Derive it** as `water_vapor_column_delta_d` with the TROPOMI definition,
  without a standard error, and record the derivation in the metadata.

### P3. The 1-D stores

**Core: the retrieval plus the mandatory flag** (all rows exist).

| source | canonical_name | units | conversion |
| --- | --- | --- | --- |
| `target_product/h2o_column` | `water_vapor_column_h2o` | mol m-2 | x 1e4 / N_A |
| `target_product/h2o_column_precision` | `water_vapor_column_h2o_standard_error` | mol m-2 | x 1e4 / N_A |
| `target_product/hdo_column` | `water_vapor_column_hdo` | mol m-2 | x 1e4 / N_A |
| `target_product/hdo_column_precision` | `water_vapor_column_hdo_standard_error` | mol m-2 | x 1e4 / N_A |
| `diagnostics/processing_quality_flags` | `quality_flags_retrieval` | unitless | none (int32; mandatory) |

**Filter inputs: everything Sarkar et al. (2026) apply to SCIAMACHY**, as
TROPOMI stores everything Table 1 needs. Rows marked *new* need adding.

| source | canonical_name | units | conversion | filter |
| --- | --- | --- | --- | --- |
| `diagnostics/iterations` | `iterations_retrieval` | unitless | none (int32) | iterations < 12 |
| `instrument/solar_zenith_angle` | `solar_zenith_angle` | degree | none (respell `degrees`) | SZA < 70° |
| `target_product/h2o_column_apriori` | `water_vapor_column_h2o_apriori` *new* | mol m-2 | x 1e4 / N_A | 0.7 <= H2O/H2O_apriori <= 1.3 |
| `side_product/ch4_column` | `methane_column` *new* | mol m-2 | x 1e4 / N_A | 0.9 <= CH4/CH4_apriori <= 1.1 |
| `side_product/ch4_column_apriori` | `methane_column_apriori` *new* | mol m-2 | x 1e4 / N_A | as above |
| `diagnostics/rms` | `rms_residual_retrieval` *new* | mol s-1 m-2 nm-1 sr-1 | none (drop `ph.`, a photon label) | log(RMS) within ±6σ of the file's median |

The precisions in the core serve the log-uncertainty cut (±5σ, per file).

Choices inside P3:
- **`hdo_column_apriori`** (`water_vapor_column_hdo_apriori`, *new*): no
  filter needs it. I'd include it, so the total-column priors come as a pair
  (~300 MB). Both are exact sums of the partial-column priors (S7), but they
  are published, so they are stored as published, not derived.
- **CH4 final or prefit:** `ch4_column` and `ch4_column_prefit` give nearly the
  same ratio to the a priori (p50 0.78-0.83 for both). The paper says only
  "CH4/CH4_apriori". I'd store the final `ch4_column` and leave the prefit
  out; or store both.
- **Methane naming:** `methane_column` follows `dry_air_partial_column`, which
  has no species token. The rule that the species is always explicit (N13) was
  written for water vapour's isotopologues. The alternative is
  `methane_column_ch4`.
- **RMS naming:** the statistic first, then what it is of, then which fit, as
  `chi_squared_retrieval`. The source unit `mol ph. s-1 m-2 nm-1 sr-1` is a
  photon radiance; `ph.` is a label, not a unit, so it moves to the
  long_name.

**Left out unless asked:**
- `aerosol_optical_thickness`, its precision, `aerosol_height_precision`:
  fill on every row (S6);
- `aerosol_height`, `surface_albedo` (2360 nm, not TROPOMI's 2365 nm),
  `cloud_fraction`, `chi_squared`, `number_of_spectral_points_in_retrieval`,
  `degrees_of_freedom_total`, `snr`: no SCIAMACHY filter uses them, although
  TROPOMI's Table 1 uses the first two. Each would add one store (~300 MB);
- `ch4_column_prefit`, `ch4_column_precision`, `co_*`, `spectral_shift`,
  `baselinecorrection`, `pixel_id`, `integration_time`, the azimuth and
  viewing angles, and the other `meteo` variables.

### P4. Geolocation and the model-comparison stores

- **Geolocation:** `time`, `lat`, `lon`. **Pixel corners: include
  (recommended)**, as TROPOMI does (`instrument/{latitude,longitude}_corners`,
  `corner` 4, ~2.5 GB). SCIAMACHY's pixels are about 30 x 60 km, so the
  corners matter for gridding.
- **Model comparison:** the 5 variable stores named on 2026-10-19 (table
  above), plus `pressure` as its own store (Pa, 61 levels; revised N3).
  - The 60-layer stores are ~19 GB each uncompressed.
  - By the chunk rule, 131,072 obs (30 MiB) per chunk, ~600 chunks per array,
    so no shards are needed.
  - Compression (default zstd, or blosc zstd 5 + shuffle as TROPOMI's wide
    arrays) is measured at the bench.

That makes **19 stores**: geolocation, 5 core, 7 filter inputs (with
`hdo_column_apriori`), 5 model-comparison and `pressure`. About 7.8e7 obs.

### P5. Filtering guidance in the metadata

Sarkar et al. (2026) for SCIAMACHY in full, as listed above under Filtering
guidance, with the δD definition from P2. The record also notes that rows
flagged 4 or 5 hold fill in the retrieval variables.

## Known data issues

Status: **handled** (the pipeline deals with it), **open** (settle before this product is built), **record only** (users should know; kept as published).

| # | issue | status |
| --- | --- | --- |
| S1 | **`raw/SCIAMACHY/H2O` and `raw/SCIAMACHY/HDO` hold ESA MIPAS files**, a different Envisat instrument that is not in WISO-SAT. | handled: excluded |
| S2 | **Same SRON format as TROPOMI**, so TROPOMI's T1-T17 (`tropomi.md`) likely apply. No 9.96921e36 was seen in the one file sampled. | open: check the fill convention, and audit for shells and partial files as for TROPOMI |
| S3 | **Negative retrieved columns** (e.g. `hdo_column` -9.3e16) are real retrieval output, not fill. | record only |
| S4 | **No δD is published**; WISO-SAT derives it. | open: P2 |
| S5 | **Hidden transfer leftovers in the raw tree** (found 2026-10-22): 24 `.ArchiveServiceTemp.sb-*` folders hold 3,350 files whose names all also exist in the month folders. 3,339 have the same size as the month-folder copy; 11 are truncated (0 B or a whole number of MiB). 201 names occur more than once among them. Also one `.DS_Store`. The month folders hold 41,616 files, 173 GB, with no repeated name. | handled: only `YYYYMM` folders are listed. Deleting the leftovers (~14 GB) is the user's call |
| S6 | **`aerosol_optical_thickness`, its precision and `aerosol_height_precision` are fill on every row** in every file sampled, though `aerosol_height` and its prior are written. | record only: left out (P3); the audit counts it over every file |
| S7 | **The total-column priors are the sums of the partial-column priors**, for H2O and HDO, to float32 precision (three files). | record only |
