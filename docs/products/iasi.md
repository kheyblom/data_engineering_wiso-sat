# IASI (KIT MUSICA L2pp, H2O/δD pair product, version 030201 v2)

Not started. Measured 2026-10-14 from header reads and one file's values.

## Raw data

```
raw/IASI/IASI_L2/<YYYY>/IASIAB_MUSICA_030201_L2pp_H2Oiso_v2_<YYYYMMDD>_{morning,evening}_global.nc   (~670 MB)
```

- **Files:** 4,568 files over 2014-2020, two per day (morning and evening
  overpasses), so the granule is a half-day file. ~344k obs per file,
  ~1.6e9 in all: the second-largest product after TROPOMI.
- `IASIAB` presumably combines MetOp-A and -B; confirm from the metadata.
- **Also on disk but excluded:** `raw/IASI/10.35097-495` (the MUSICA L3 data
  bag, which is what WISO-SAT itself gridded) and `raw/IASI/trash`.

## Format

- **Layout:** flat. Observation dim `observation_id`; `atmospheric_levels` 29;
  `musica_species_id` 2.
- **Time:** int64 `seconds since 2000-01-01 00:00:00`, at 1 s resolution,
  plus a `time_string`.
- **Fill:** `_FillValue` NaN (CF-decoded already).
- **Root attribute:** `retrieval_in_logarithmic_parameter_space: true`.
- **Geolocation:** `lat`, `lon` (float32); `musica_pressure_levels` and
  `musica_altitude_levels` on `atmospheric_levels` go in the geolocation
  store.

## Variables and units

- **`musica_deltad`** (`1e-3`, already canonical; p50 -341) and its `_apriori`
  and `_error`.
- **`musica_h2o`** (`ppmv`; respell to `1e-6`, no value change; p50 168) and
  its `_apriori` and `_error`.
  - Dry-air basis per Sarkar et al. (2026); the file does not say.
- **`musica_wvp` and its family:** the state in **log space**
  ({0.5(lnH2O + lnHDO), lnHDO - lnH2O}), `1`. **Never scale them.**
- **Averaging kernels are stored compressed as a truncated SVD:**
  `musica_wvp_avk_lvec`, `_rvec`, `_val`, `_rank` (rank <= 13), plus the
  temperature cross-kernel `musica_wvp_xavkat_*`.
  - Store the components as published. Reconstructing the full kernel would
    be a derivation, not a rename.
- **Flags:**
  - `musica_deltad_error_flag` (1 = error below 40 per mil);
  - `musica_wvp_kernel_flag` (uint64);
  - `eumetsat_surface_type_flag`.

## Filtering guidance

- The L3 that WISO-SAT used was MUSICA-filtered.
- Record the MUSICA L2pp flag guidance from Diekmann et al. (2021). This has
  not been read yet.

## Model-comparison variables (named 2026-10-19)

Named in the cross-product naming pass. The grammar and decisions are in
`docs/model-comparison-naming.md`; the rows are in `nomenclature_data.md`
(style_guides `fee64ec`). Units are after conversion. Not built yet.

- **Dims:**
  - `atmospheric_levels` (29) becomes `level`. Levels beyond `musica_nol`
    (18-29 per obs) are NaN.
  - `wv_avk_rank` becomes `rank`, and `wv_xavkat_rank` becomes
    `rank_temperature`, so the two SVDs never share a dim name with two
    sizes.
- **Vertical order:** `top_first` (level 0 at ~46 Pa).
- **The proxy state.** MUSICA retrieves two ln-space proxies per level:
  - humidity, 0.5 (ln H2O + ln HDO);
  - δD, ln HDO - ln H2O (`musica_species_id` 0 and 1).

  The kernel is a 58 x 58 matrix over them.
- **How the kernel is published.** As a truncated SVD, `A = L diag(s) R^T`,
  with L and R orthonormal. Block (k, l), retrieved proxy k against true
  proxy l, is `L_k diag(s) R_l^T`.
  - L and R split per proxy, which loses nothing.
  - The δD-proxy block that δD comparisons use needs `L_δD`, s and `R_δD`.
  - Rebuilding A would be a derivation, and 2.2 times larger, so the
    components are stored as published.

| source | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- |
| `musica_h2o_apriori` | `water_vapor_h2o_mole_fraction_dry_air_apriori` | 1e-6 | (obs, level) | none (respell `ppmv`) |
| `musica_deltad_apriori` | `water_vapor_delta_d_apriori` | 1e-3 | (obs, level) | none |
| `musica_wvp_apriori[:, 0]` | `water_vapor_proxy_humidity_apriori` | unitless | (obs, level) | none; ln space, never scaled |
| `musica_wvp_apriori[:, 1]` | `water_vapor_proxy_delta_d_apriori` | unitless | (obs, level) | none; ln space |
| `musica_wvp_avk_lvec[:, 0]` | `water_vapor_proxy_humidity_averaging_kernel_svd_left_vectors` | unitless | (obs, rank, level) | none; rank padded (I6) |
| `musica_wvp_avk_lvec[:, 1]` | `water_vapor_proxy_delta_d_averaging_kernel_svd_left_vectors` | unitless | (obs, rank, level) | none |
| `musica_wvp_avk_rvec[:, 0]` | `water_vapor_proxy_humidity_averaging_kernel_svd_right_vectors` | unitless | (obs, rank, level) | none |
| `musica_wvp_avk_rvec[:, 1]` | `water_vapor_proxy_delta_d_averaging_kernel_svd_right_vectors` | unitless | (obs, rank, level) | none |
| `musica_wvp_avk_val` | `water_vapor_proxy_averaging_kernel_svd_singular_values` | unitless | (obs, rank) | none |
| `musica_wvp_avk_rank` | `water_vapor_proxy_averaging_kernel_svd_rank` | unitless | (obs) | none (int8) |
| `musica_wvp_xavkat_lvec[:, 0]` | `water_vapor_proxy_humidity_averaging_kernel_cross_air_temperature_svd_left_vectors` | unitless | (obs, rank_temperature, level) | none; rank padded |
| `musica_wvp_xavkat_lvec[:, 1]` | `water_vapor_proxy_delta_d_averaging_kernel_cross_air_temperature_svd_left_vectors` | unitless | (obs, rank_temperature, level) | none |
| `musica_wvp_xavkat_rvec` | `water_vapor_proxy_averaging_kernel_cross_air_temperature_svd_right_vectors` | unitless | (obs, rank_temperature, level) | none; temperature side, so no proxy dim |
| `musica_wvp_xavkat_val` | `water_vapor_proxy_averaging_kernel_cross_air_temperature_svd_singular_values` | K-1 | (obs, rank_temperature) | none; corrected source unit `1` -> `K-1` (I8) |
| `musica_wvp_xavkat_rank` | `water_vapor_proxy_averaging_kernel_cross_air_temperature_svd_rank` | unitless | (obs) | none (int8) |
| `musica_pressure_levels` | geolocation `pressure` | Pa | (obs, level) | none |

- **Priors:**
  - The proxy priors are what the kernel applies to.
  - The H2O and δD priors are the physical ones. The proxies follow from them
    only through ln and a reference ratio, so not exactly in float32.
  - Both pairs are stored.
- **Padding (I6):**
  - Each file pads its rank dim with NaN past each obs's own rank.
  - The stores pad to the record maximum in the same way, recorded in the
    metadata.
  - Find the maximum of both rank dims from the headers before building.
- **Stores: 6.** A matrix published in pieces is one store (style guide,
  Level 2).
  - The four priors are one store each.
  - The six `musica_wvp_avk_*` arrays share
    `water_vapor_proxy_averaging_kernel_svd`.
  - The five `musica_wvp_xavkat_*` arrays share
    `water_vapor_proxy_averaging_kernel_cross_air_temperature_svd`.
  - This needs multi-array variable stores in the shared code first.
- **Sizes:**
  - each kernel vector array is ~2.4 TB uncompressed (1.6e9 obs x 13 x 29 x
    4 B), ~9.7 TB for the four;
  - the temperature cross-kernel is ~4.5 TB.
- **Not here:** `musica_h2o_error`, `musica_deltad_error` and
  `musica_wvp_error` are 1-sigma retrieval errors. They are named with the
  retrieved quantities when the reader is built (e.g.
  `water_vapor_h2o_mole_fraction_dry_air_standard_error`).
- **Before building:** the store version (I7).

## Known data issues

Status: **handled** (the pipeline deals with it), **open** (settle before this product is built), **record only** (users should know; kept as published).

| # | issue | status |
| --- | --- | --- |
| I1 | **The H2O basis is not stated in the file**; it is dry-air per Sarkar et al. (2026). | record only |
| I2 | **`musica_wvp` and its family are log-space states** with units `1`. | open: never scale (project rule) |
| I3 | **Averaging kernels are stored as a truncated SVD** (rank <= 13). | open: store the components as published; reconstructing is a derivation |
| I4 | **`IASIAB`** presumably combines MetOp-A and -B; not confirmed. `raw/IASI/trash` and the L3 data bag sit beside the L2 files. | open: confirm from metadata; exclude both folders |
| I5 | **WISO-SAT itself gridded the MUSICA L3**, not these L2pp files. | record only |
| I6 | **`wv_avk_rank` varies by file**: 12 or 13 in seven files sampled 2014-2020. Within a file, per-obs ranks vary (5-12 in the 2016-06-15 morning file) and components past an obs's rank are NaN (2026-10-19). | open: pad `rank` to the record maximum with NaN (`docs/model-comparison-naming.md` N10); find the maximum before building |
| I8 | **The temperature cross-kernel's units are wrong**: every `musica_wvp_xavkat_*` says `1`, but the kernel is of ln mixing ratio with respect to temperature in K (its own description), so K-1. The singular vectors are orthonormal (checked on one obs), so the singular values carry the K-1 (2026-10-19). | decided (user, 2026-10-19): declare the corrected unit `K-1` on `musica_wvp_xavkat_val` in the key and metadata, with this evidence (`docs/model-comparison-naming.md` N17) |
| I7 | **The processor version changes in 2019**: `IASIAB_MUSICA_030201` to 2019, then `IASIAB_MUSICA_030300` and `IASIABC_MUSICA_030300` (MetOp-C joins). File counts: 2019 holds 362 AB 030201, 230 AB 030300 and 138 ABC 030300; 2020 is all ABC 030300 (2026-10-19). The store name carries one version. | open: decide the store version and naming before building |
