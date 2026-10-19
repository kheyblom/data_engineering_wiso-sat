# AIRS and CrIS (NASA TROPESS / MUSES HDO)

Not started. Measured 2026-10-14 from header reads and sampled values. Four
products share one file format, so they will most likely share one reader:

| product | raw folder | stream | files | dates | obs/file | ~obs |
| --- | --- | --- | --- | --- | --- | --- |
| AIRS RS | `AIRS/TRPSYL2HDOAIRSORS_1-20240806_185241/` | Summary (reanalysis stream) | 6,361 | 2002-09-01 .. 2020-03-31 | ~1,753 | 1.1e7 |
| AIRS FS | `AIRS/TRPSDL2HDOAIRSFS_1-20240912_174250/` | Standard (forward stream) | 1,424 | 2021-02-01 .. 2024-09-04 | ~28,972 | 4.1e7 |
| CrIS-SNPP RS | `CRIS/TRPSYL2HDOCRSRS_1-20240923_230130/` | Summary | 1,865 | 2015-12-01 .. 2021-05-21 | ~1,518 | 2.8e6 |
| CrIS-JPSS1 FS | `CRIS/TRPSDL2HDOCRS1FS_1-20240912_023602/` | Standard | 1,208 | 2021-04-01 .. 2024-09-05 | ~24,937 | 3.0e7 |

- **File names:** `TROPESS_<sensor>_L2_{Summary,Standard}_HDO_<YYYYMMDD>_MUSES_R1pNN_{RS,FS}_F0pN[_J0].nc`.
  There is one file per day, and the day is the granule.
- **AIRS coverage gap:** AIRS has no data from 2020-04 to 2021-01 between
  the two streams (flagged, not chased). CrIS RS and FS overlap by two
  months.
- **Files to skip:** the AIRS FS folder also holds L3 files
  (`AIRS_TROPESS_gridded_*`), so glob `TROPESS_*`.
- **Open:** 51 AIRS FS files end `_F0p3_target.nc`. Check for duplicate dates
  against the plain files before building.
- **FS versions drift:** files span processor versions R1p11 .. R1p19 and
  F0p1 .. F0p6.
  - Units are the same across versions; `long_name` wording drifts.
  - The `retrieval/` group (`x_raw`, `x_h2o_raw`) is absent from the oldest
    files (R1p12 F0p1), so the reader must tolerate a variable missing from
    some granules, or the variable list must be restricted to ones present
    throughout.

## Format

- **Groups:** root, `geolocation`, `geophysical`, `retrieval`; FS adds
  `observation_ops`. Some variables are in the root group.
- **Dims:** observation dim `target`; `level` 17 (fixed pressure grid except
  the surface level, p50 421.7 hPa); `datetime_utc_dim` 6.
- **Time:** `time` is float64 `seconds since 1993-01-01 00:00:00`. Check it
  against the 6-field `datetime_utc` before trusting it: TROPESS may use
  TAI93, which counts leap seconds (~10 s by 2017).
- **Fill:** `_FillValue` -999 throughout, but `missing_value` is -999 on most
  variables and **-9999 on `dd_col_p`/`dd_004`**. Declare and mask both.
- **Pre-filtering:** RS (Summary) files are pre-filtered: only retrievals
  passing internal convergence and sensitivity checks (Sarkar et al. 2026).
  FS files are not.

## Variables and units

- **`x`:** bias-corrected HDO/H2O **mole ratio** profile (`1`, p50 2.3e-4).
  It is a ratio, not δD and not a mole fraction: keep `1`.
- **`x_h2o`:** bias-corrected H2O dry-air VMR profile (`1`) → `1e-6`
  (x 1e6).
  - The basis is explicitly dry in RS; dry for FS per Sarkar et al. (2026).
  - Values reach 0.44 mol mol-1, which is unphysical.
- **RS only:**
  - `dd_col_p` and `dd_col_p_error`: mean δD 850-250 hPa (`1e-3`, already
    canonical);
  - `dd_004`: δD at a VMR of 4 per mil (`1e-3`);
  - `x_h2o_col_p` and `x_h2o_col_p_error` (`1e-6`, canonical).
- **FS only:**
  - `observation_ops/xa`: a priori ratio, `1`.
  - `observation_ops/averaging_kernel` (17 x 17, **log-space** ratio kernel)
    and `observation_error`.
  - `observation_ops/observation_error_h2o`: `1`, **a relative / ln-space
    error, p50 0.09. Never scale it x 1e6.**
  - `x_test`, and `retrieval/x_raw` and `x_h2o_raw`: uncorrected, in the
    newer versions only.
- **Profile coordinate:** `pressure` (hPa) and `altitude` on `level`. These
  go in the geolocation store.

## Filtering guidance to record, not apply

- FS: DOF >= 1 and COD <= 0.5 (Sarkar et al. 2026).
- RS: already filtered upstream.

## Known data issues

Status: **handled** (the pipeline deals with it), **open** (settle before this product is built), **record only** (users should know; kept as published).

| # | issue | status |
| --- | --- | --- |
| R1 | **AIRS has no data 2020-04 .. 2021-01**, between the RS and FS streams. CrIS SNPP RS and JPSS1 FS overlap by two months. | record only |
| R2 | **Two fill conventions**: `_FillValue` -999 throughout, but `missing_value` is -9999 on `dd_col_p` and `dd_004`. | open: declare and mask both |
| R3 | **Time may be TAI93** (seconds since 1993-01-01, ~10 s of leap seconds by 2017). | open: check against `datetime_utc` |
| R4 | **FS processor versions drift** (R1p11..R1p19, F0p1..F0p6). Units are stable, but `long_name` wording changes, and `retrieval/x_raw`/`x_h2o_raw` are absent from the oldest files. | open: restrict to variables present throughout, or tolerate absence |
| R5 | **51 AIRS FS files end `_F0p3_target.nc`**, possibly duplicating plain files' dates. | open: check before building |
| R6 | **The AIRS FS folder holds L3 files** (`AIRS_TROPESS_gridded_*`). | open: glob `TROPESS_*` |
| R7 | **`x_h2o` reaches 0.44 mol mol-1**, which is unphysical. | record only |
| R8 | **`observation_error_h2o` is a ln-space relative error** with units `1`, sitting next to mole-fraction variables. | open: must never be scaled x 1e6 (project rule) |
| R9 | **RS (Summary) files are pre-filtered**; FS files are not. | record only |
| R11 | **FS `observation_error` is not a valid covariance.** In AIRS FS 2023-06-15 (R1p20, 29,650 targets), every target is asymmetric (median max abs(S - S^T) 0.052), and 99.4% have at least one negative variance, down to -14 at upper levels. Its `source` attribute says `obs_dd + obs_hh - obs_hd - obs_dh`, which must be symmetric with a non-negative diagonal (2026-10-19). | open: stored as published with the defect in its metadata (`docs/model-comparison-naming.md` N16, if approved); re-check every processor version at the reader |
| R12 | **`observation_error_h2o` looks 1-sigma**: p50 0.093, against p50 0.089 for the square root of TES's H2O observation-error variance. Not stated in the file (2026-10-19). | open: confirm against the TROPESS user guide |
| R10 | **FS `pressure` level 0 is -999** on the targets sampled (AIRS FS 2023-06-15); RS level 0 holds the surface pressure (2026-10-19). | open: check across the record; the fill is masked as usual |
