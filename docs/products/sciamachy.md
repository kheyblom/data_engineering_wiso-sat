# SCIAMACHY (SRON SICOR L2 H2O/HDO, file version 0110)

Not started. Measured 2026-10-14 from header reads and one file's values.

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
| `meteo/pressure_levels` | geolocation `pressure` | Pa | (obs, level) | none; layer interfaces |

- SRON calls the priors "profile", but they are partial columns: "A-priori
  vertically integrated partial column of water in layers", in molec cm-2
  per layer. Hence `partial_column`.
- **Total-column priors** are also published (`h2o_column_apriori`,
  `hdo_column_apriori`, both (obs), molec cm-2). They have no rows yet; by
  the grammar they are `water_vapor_column_{h2o,hdo}_apriori`. This is the one
  case where `column` and `partial_column` tell two variables apart.
- **Stores:** 5 variable stores, plus `pressure` in the geolocation store.

## Known data issues

Status: **handled** (the pipeline deals with it), **open** (settle before this product is built), **record only** (users should know; kept as published).

| # | issue | status |
| --- | --- | --- |
| S1 | **`raw/SCIAMACHY/H2O` and `raw/SCIAMACHY/HDO` hold ESA MIPAS files**, a different Envisat instrument that is not in WISO-SAT. | handled: excluded |
| S2 | **Same SRON format as TROPOMI**, so TROPOMI's T1-T17 (`tropomi.md`) likely apply. No 9.96921e36 was seen in the one file sampled. | open: check the fill convention, and audit for shells and partial files as for TROPOMI |
| S3 | **Negative retrieved columns** (e.g. `hdo_column` -9.3e16) are real retrieval output, not fill. | record only |
| S4 | **No δD is published**; WISO-SAT derives it. | record only: deriving it would be a new quantity and needs approval |
