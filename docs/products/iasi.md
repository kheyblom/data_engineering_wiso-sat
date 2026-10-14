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
