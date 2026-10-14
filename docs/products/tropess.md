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
