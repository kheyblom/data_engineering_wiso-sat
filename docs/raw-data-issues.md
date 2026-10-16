# Known issues in the WISO-SAT Level 2 raw data

A reference for anyone using, rebuilding or questioning the WISO-SAT Level 2
stores. It lists every known problem with the raw files as distributed, how it
was found, and what the pipeline does about it.

Raw root: `/glade/derecho/scratch/kheyblom/data/wisosat/raw/`. Findings are
dated. Unless marked otherwise, an issue is upstream: present in the
producer's own copy, not introduced by the download.

**Status** in the tables:
- **handled:** the build and the verifier deal with it, and the stores record
  it in their metadata;
- **open:** not yet resolved; it must be settled before that product is built;
- **record only:** a property of the data that users should know about; the
  stores keep it as published.

Nothing here changes a data value without saying so. Every observation the
producer wrote is stored, and quality filtering is never applied (style
guide). The one exception is TROPOMI rows that were never processed; see T5.

---

## Applies to all products

| # | issue | status |
| --- | --- | --- |
| A1 | **Undeclared fill.** Several producers mark missing values with the netCDF default fill without setting `_FillValue`, so standard CF decoding treats the sentinel as data (e.g. TROPOMI's 9.96921e36). | handled: fill is declared per source variable in the config and masked to NaN (an integer keeps the value as its `_FillValue`). The verifier fails if a declared fill never occurs, or if an undeclared default fill appears anywhere. |
| A2 | **Missing days and empty granules** cannot be told apart from an incomplete download by looking at the tree. | handled: every gap is declared in the config, and the build refuses any undeclared one. Each declared TROPOMI gap was checked against the upstream server. |

---

## TROPOMI (SRON HDO L2, product 0003, processor 8.1)

Audited file by file on 2026-10-16: all 38,648 orbit files, 2017-11-08 to
2025-11-29 (develop job 7839486, `tools/survey/tropomi_file_audit.py`).

| result | files |
| --- | --- |
| complete | 38,459 (99.5%) |
| partially processed (T5) | 77 |
| shells, nothing written (T4) | 109 |
| corrupt upstream (T3) | 3 |

Plus 353 empty orbit directories (T2) and 77 days with no files (T1). By year,
the defects cluster in 2019 (93 shells, 74 partial). 2017, 2020 and 2025 are
clean.

### Record coverage

| # | issue | status |
| --- | --- | --- |
| T1 | **77 days have no data upstream** between 2017-11-08 and 2025-11-29. Each returned HTTP 404 from `tropomi.grid.surfsara.nl`: 58 checked 2026-10-14, 19 on 2026-10-16. The longest runs are 2017-11-30..12-11 and 2018-01-10..01-27. | handled: `expected_missing_days` |
| T2 | **353 orbit directories are empty upstream**: the directory exists on the server but holds no file. Each was checked against the server listing (2026-10-14). After the re-download these are the only empty orbit directories. | handled: `expected_empty_granules` |
| T3 | **3 files are corrupt upstream**, byte-identical to the server copies: **03335** (2018-06-05, "wrong fractal heap header signature"), **07821** (2019-04-17, truncated to 3.6 MB of 645 MB) and **07844** (2019-04-19, truncated to 18 MB of 1.2 GB). HDF5 cannot open them. Worth reporting to SRON. | handled: `expected_unreadable_granules`; left out of every store and named in `known_data_gaps`. The build confirms each still fails to open. |
| T4 | **109 shell files**: every variable is declared at full size (e.g. 693,590 observations) but no data was ever written, so every read returns fill. Mostly 68,534 bytes. 93 are in 2019. The upstream copies are identical. Orbit list in the appendix. | handled: indexed as granules with zero observations; `granule_source_rows` keeps their declared size. |
| T5 | **77 partially processed files.** In 73, most rows (93-100% per file) were never processed: their time, lat/lon, SZA and every retrieval variable are unwritten. Across all 48,741,476 such rows, none of the 20 other variables the pipeline reads holds a value. In the other 4, every row was processed but some retrieval variables were never written. The processed rows (1,356,964 in all) often have the retrieval variables, the quality flags and even the scanline indices unwritten as well. Mostly 2019. Orbit list with row counts in the appendix. | handled (user decision 2026-10-16): an observation is a row whose time is written. Unprocessed rows are left out, but only after the build confirms every source is fill on them; the verifier re-derives this from raw. `granule_source_rows` records each file's own row count. |
| T6 | **The upstream record ends at 2025-11-29.** The server lists 2025-11-30, but its 14 orbit directories are empty. | record only |
| T7 | **The first download (2026-10) was incomplete:** 339 orbits and 12 days were missing, there were truncated duplicates named `*.nc?action=show` (orbits 00608, 16210), a `.smbdelete*` file (orbit 9453), and 195 `.DS_Store` files. | handled: re-downloaded 2026-10-16 and re-audited. The reader matches file names exactly and walks only all-digit directories, so stray files are ignored. Details: `docs/products/tropomi-download-gaps.md`. |

### File format

| # | issue | status |
| --- | --- | --- |
| T8 | **No `_FillValue`.** Missing values are the netCDF defaults: float 9.96921e36 and int -2147483647. In a complete file, float fill occurs in every retrieval, aerosol, albedo and chi-squared variable but not in SZA, lat or lon. Int fill occurs in `iterations` and both spectral-point counts. `processing_quality_flags` holds int fill only on processed rows of partial files (238 rows). | handled: declared per source in `source_fill_values` (A1) |
| T9 | **Real NaNs in `deltad_precision`** alongside the fill (5,447 in orbit 13847). | record only: they stay NaN, indistinguishable from masked fill |
| T10 | **Time is broken down**: `instrument/time` is int32 (nobs, 7), year .. millisecond. | handled: decoded exactly to int64 ms since 1900 |
| T11 | **Three variables are "not implemented"**: `quality_flag`, `convergence`, `glintflag`. The real flag is `processing_quality_flags` (CF `flag_masks`/`flag_values`). | handled: only `processing_quality_flags` is stored, as `quality_flags_retrieval` |
| T12 | **`standard_name`s are SRON's own**, not CF (`delta_d`, `water_column`, `height_scattering_layer`, ...). | record only: retained unchanged, per the style guide |
| T13 | **Cloud parameters are named after aerosol.** Schneider et al. (2022) Table 1 filters on "cloud" optical thickness and height. In the file these are `aerosol_optical_thickness` and `aerosol_height`, SRON's effective scattering layer. Evidence: `aerosol_geometric_thickness` is 2500 m on every pixel, matching the paper's fixed layer thickness, and SRON's PAL product guide uses `aerosol_optical_thickness < 0.3` for clear sky. | handled: stored as `optical_thickness_scattering_layer` and `height_scattering_layer`; explained in `filtering_guidance` |
| T14 | **Reduced chi-squared is undefined.** Table 1 filters on reduced chi-squared, but the files hold only unreduced `chi_squared` and per-pixel spectral point counts (270-277 final fit, 309-316 pre-fit). Dividing by the point count is inferred; dividing by points minus degrees of freedom differs by ~2.5%. | handled: both inputs stored; the inference is recorded in the metadata |
| T15 | **`nobs` varies widely**: 625,220 to 1,204,215 per complete file, plus short orbits down to 1,505. The along-track resolution changed in August 2019. Every orbit is a whole number of 215-pixel scanlines. | handled: the verifier checks the scanline layout on every file, on the rows where the indices were written |
| T16 | **Some units are byte strings** (`b'1'`) when read with h5py. | handled: decoded |

### Values (record only)

| # | issue |
| --- | --- |
| T17 | `processing_quality_flags == 0` still passes unphysical δD: -0.99 to +13 as a fraction (p1/p99), with extremes of -67,429 and +55,177. `h2o_column` reaches 1.7e26 molec cm-2. SRON's filtering guidance (Table 1) is needed on top of the flag; it is recorded in every store's `quality_filtering`. |
| T18 | Flag-0 pixels reach negative surface albedo (p1 -0.95, minimum -1.97). The albedo >= 0.02 clear-sky cut removes them. |
| T19 | Column averaging kernels reach p99 ~700 in some layers. Unexplained; not a unit issue. Relevant once kernels are stored. |

---

## GOSAT and GOSAT-2 (IUP FOCAL v3.0.1)

| # | issue | status |
| --- | --- | --- |
| G1 | **DED and H2O are separate, separately filtered files** with only partly overlapping soundings. Over 13 sampled days, 44% of DED soundings were in the H2O file. Where both hold a sounding, all 16 shared fields are identical. | handled (user decision 2026-10-14): merged per day onto one axis of distinct soundings. A variable is absent where its file lacks the sounding. |
| G2 | **Pre-filtered upstream**: the files hold only soundings that passed IUP's quality control, and every flag sampled is 0. | record only: stated in `filtering_guidance` |
| G3 | **Time has no decimal grid coarser than a nanosecond.** It is float64 seconds since 1970. In an exact round trip of 38,003 sampled times, ms failed 99% and us 76%. | handled: stored as int64 ns since 1900 |
| G4 | **The time variable carries `calendar: standard`**, which blocks xarray's time encoding. | handled: kept as `original_calendar`; stored as proleptic_gregorian |
| G5 | **GOSAT: 138 days have no files, GOSAT-2: 51**, identical for DED and H2O. Not yet checked against upstream. | handled for GOSAT (`expected_missing_days`); GOSAT-2 not configured |
| G6 | **GOSAT-2 file names say `GOSAT2` while their folders say `GOSAT`.** The GOSAT-2 2019 folder also holds L3 files (`GOSAT2_monthly_1deg.nc`, `HDO_5x5_monthly.mat`). | handled: the reader accepts both names and matches L2 file names exactly |
| G7 | **`dry_column` has units `no. of molecules`**, with no per-area unit. | open: value-check it before storing |
| G8 | `xh2o` holds negative values (minimum -116.6 ppm in one sampled day). | record only |

---

## TES (Aura L2 HDO Nadir Lite v006)

Not built yet; from header reads, sampled values and an integration test
(2026-10-14).

| # | issue | status |
| --- | --- | --- |
| E1 | **`Species` stacks two profiles**: levels 0-16 are HDO and 17-33 are H2O, on the same 17 pressures repeated. `Retrieval/HDO_H2O` is an identical array, not a ratio. `AveragingKernel`, `ObservationErrorCovariance` and the `Characterization/*ErrorCovariance` stack the same way into 2 x 2 blocks. | open: split into one store per quantity and the matrices into blocks, cross blocks kept (style guide) |
| E2 | **`TotalColumnDensity` is mislabelled `molecules/m2`; the values are the HDO column in molec cm-2.** Integrating the HDO profile gives exactly 1e4 times the stored value for every target. | open: declare the corrected source unit and its evidence in the key; convert x 1e4 / N_A |
| E3 | **Non-CF attributes**: `Units`, `FillValue`, `MissingValue` (capitalised), so xarray does not mask fill. Fill values seen: -999, -999.0 and -99. | open: declare per variable |
| E4 | **Time is "seconds since 1993-01-01"** with calendar `julian`; likely TAI93, which counts leap seconds. | open: check against `YYYYMMDD` and `UT_Hour` |
| E5 | **2011-2015 is absent from disk** (Sarkar et al. 2026 use TES through 2015). | record only: flagged, not chased |

---

## AIRS and CrIS (NASA TROPESS / MUSES)

Not built yet; from header reads and sampled values (2026-10-14).

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

---

## IASI (KIT MUSICA L2pp v030201)

Not built yet (2026-10-14).

| # | issue | status |
| --- | --- | --- |
| I1 | **The H2O basis is not stated in the file**; it is dry-air per Sarkar et al. (2026). | record only |
| I2 | **`musica_wvp` and its family are log-space states** with units `1`. | open: never scale (project rule) |
| I3 | **Averaging kernels are stored as a truncated SVD** (rank <= 13). | open: store the components as published; reconstructing is a derivation |
| I4 | **`IASIAB`** presumably combines MetOp-A and -B; not confirmed. `raw/IASI/trash` and the L3 data bag sit beside the L2 files. | open: confirm from metadata; exclude both folders |
| I5 | **WISO-SAT itself gridded the MUSICA L3**, not these L2pp files. | record only |

---

## SCIAMACHY (SRON SICOR L2, file version 0110)

Not built yet (2026-10-14).

| # | issue | status |
| --- | --- | --- |
| S1 | **`raw/SCIAMACHY/H2O` and `raw/SCIAMACHY/HDO` hold ESA MIPAS files**, a different Envisat instrument that is not in WISO-SAT. | handled: excluded |
| S2 | **Same SRON format as TROPOMI**, so T8-T16 likely apply. No 9.96921e36 was seen in the one file sampled. | open: check the fill convention, and audit for shells and partial files as for TROPOMI |
| S3 | **Negative retrieved columns** (e.g. `hdo_column` -9.3e16) are real retrieval output, not fill. | record only |
| S4 | **No δD is published**; WISO-SAT derives it. | record only: deriving it would be a new quantity and needs approval |

---

## Outside the Level 2 scope

| # | issue |
| --- | --- |
| X1 | The WISO-SAT TROPOMI L3 files (`TROPOMI_averaged_files`) appeared to hold `deltad_1deg` as a fraction (median -0.175) with no `units` attribute, while Sarkar et al. (2026) state per mil. Worth raising with the authors if those are the published files. |

---

## Appendix: TROPOMI defect files (audit of 2026-10-16)

The audit output itself is
`/glade/derecho/scratch/kheyblom/data/wisosat/audit/tropomi_files.jsonl`.
Scratch is purged, so the lists below are the durable copy.

### Corrupt upstream (3)

`YYYY/MM/DD/<orbit>`: `2018/06/05/3335`, `2019/04/17/7821`, `2019/04/19/7844`

### Shells (109): nothing written

As `YYYY/MM/DD/<orbit>` (declared rows):

```
2019/01/06/6380  (693,590)
2019/01/13/6481  (697,675)
2019/01/15/6517  (697,890)
2019/01/19/6576  (697,675)
2019/01/20/6581  (697,675)
2019/01/23/6628  (624,575)
2019/01/27/6682  (697,675)
2019/01/27/6683  (697,890)
2019/01/27/6685  (697,675)
2019/02/08/6851  (697,890)
2019/02/10/6877  (697,675)
2019/02/15/6960  (697,675)
2019/02/16/6963  (697,675)
2019/02/17/6985  (697,675)
2019/02/21/7033  (624,575)
2019/02/24/7080  (697,675)
2019/03/01/7147  (697,890)
2019/03/10/7281  (697,890)
2019/03/10/7282  (697,675)
2019/03/15/7351  (697,890)
2019/03/17/7383  (697,675)
2019/03/24/7480  (697,675)
2019/03/24/7482  (697,675)
2019/03/29/7549  (697,890)
2019/04/04/7632  (697,675)
2019/04/07/7675  (697,675)
2019/04/13/7757  (697,890)
2019/04/13/7764  (697,675)
2019/04/14/7776  (697,890)
2019/04/20/7858  (624,575)
2019/04/21/7882  (697,675)
2019/04/22/7884  (697,675)
2019/04/23/7910  (697,675)
2019/04/27/7955  (697,890)
2019/04/27/7959  (697,675)
2019/04/28/7976  (697,675)
2019/04/28/7980  (697,890)
2019/04/29/7983  (697,675)
2019/05/01/8016  (697,675)
2019/05/02/8025  (697,675)
2019/05/03/8041  (697,675)
2019/05/03/8042  (697,890)
2019/05/03/8046  (697,675)
2019/05/05/8078  (697,675)
2019/05/06/8083  (624,575)
2019/05/08/8115  (697,890)
2019/05/08/8122  (697,675)
2019/05/10/8147  (697,675)
2019/05/10/8150  (697,675)
2019/05/12/8180  (697,675)
2019/05/15/8217  (697,890)
2019/05/19/8279  (697,675)
2019/05/27/8381  (697,890)
2019/05/31/8443  (624,575)
2019/06/01/8453  (697,890)
2019/06/03/8482  (697,675)
2019/06/06/8522  (697,890)
2019/06/06/8529  (697,675)
2019/06/07/8539  (697,890)
2019/06/07/8547  (697,675)
2019/06/09/8575  (697,675)
2019/06/12/8608  (624,790)
2019/06/12/8609  (697,890)
2019/06/12/8615  (697,675)
2019/06/12/8619  (697,675)
2019/06/13/8623  (624,790)
2019/06/13/8626  (697,890)
2019/06/13/8632  (697,675)
2019/06/14/8639  (697,675)
2019/06/14/8642  (697,675)
2019/06/14/8647  (697,675)
2019/06/15/8649  (697,675)
2019/06/15/8650  (697,890)
2019/06/15/8653  (624,575)
2019/06/16/8664  (697,890)
2019/06/16/8668  (624,790)
2019/06/17/8684  (697,675)
2019/06/20/8720  (697,890)
2019/06/20/8721  (697,675)
2019/06/21/8741  (697,890)
2019/06/21/8742  (697,890)
2019/06/22/8762  (697,890)
2019/06/23/8764  (697,890)
2019/06/23/8773  (624,790)
2019/06/24/8783  (697,675)
2019/06/26/8811  (697,675)
2019/06/26/8819  (697,675)
2019/06/28/8837  (697,675)
2019/06/29/8848  (624,575)
2019/06/29/8857  (697,675)
2019/06/29/8858  (697,675)
2019/06/29/8861  (697,675)
2019/07/01/8880  (697,890)
2022/08/22/25171  (896,980)
2022/08/23/25185  (896,980)
2022/08/24/25192  (852,260)
2022/08/25/25209  (896,980)
2022/08/28/25255  (897,195)
2023/07/29/30009  (852,045)
2023/07/30/30022  (852,475)
2023/08/08/30157  (852,045)
2023/09/03/30522  (881,285)
2023/10/25/31257  (851,830)
2023/10/28/31300  (852,045)
2023/11/11/31494  (852,045)
2023/12/01/31779  (852,045)
2023/12/02/31790  (851,830)
2024/04/06/33587  (896,980)
2024/05/15/34132  (856,990)
```

### Partially processed (77)

As `YYYY/MM/DD/<orbit>`: processed rows kept of rows declared; pipeline variables unwritten (of 21).

```
2018/10/30/5420   13,975 of    13,975  (14 unwritten)
2019/01/20/6580   32,786 of   697,890  (10 unwritten)
2019/01/26/6671        3 of   697,890  (17 unwritten)
2019/01/27/6687        1 of   697,675  (17 unwritten)
2019/02/16/6961        3 of   697,675  (17 unwritten)
2019/02/17/6979   15,160 of   624,790  (14 unwritten)
2019/02/17/6980   34,435 of   697,675  (6 unwritten)
2019/03/03/7176   34,856 of   697,675  (10 unwritten)
2019/03/03/7178   34,869 of   697,890  (10 unwritten)
2019/03/03/7180   31,211 of   697,675  (14 unwritten)
2019/03/03/7182   34,888 of   697,675  (10 unwritten)
2019/03/16/7360   27,696 of   697,675  (14 unwritten)
2019/03/17/7384   35,303 of   697,675  (10 unwritten)
2019/03/24/7484        1 of   697,675  (17 unwritten)
2019/03/27/7517        1 of   697,675  (17 unwritten)
2019/03/31/7583        2 of   697,675  (17 unwritten)
2019/04/03/7617       15 of   697,675  (17 unwritten)
2019/04/06/7665        2 of   697,675  (17 unwritten)
2019/04/07/7678        1 of   624,575  (17 unwritten)
2019/04/10/7719   26,328 of   697,890  (14 unwritten)
2019/04/11/7739   26,586 of   697,675  (14 unwritten)
2019/04/13/7759    4,752 of   697,675  (14 unwritten)
2019/04/14/7782       48 of   459,240  (16 unwritten)
2019/04/18/7829   27,559 of   697,675  (14 unwritten)
2019/04/19/7853   27,778 of   697,675  (14 unwritten)
2019/04/20/7856   31,217 of   697,675  (14 unwritten)
2019/04/20/7868        1 of   697,675  (17 unwritten)
2019/04/23/7911        3 of   697,675  (17 unwritten)
2019/04/25/7934   18,990 of   697,890  (14 unwritten)
2019/05/01/8013   15,233 of   697,675  (14 unwritten)
2019/05/02/8026   36,379 of   697,675  (14 unwritten)
2019/05/02/8034   30,102 of   697,890  (14 unwritten)
2019/05/06/8085   37,683 of   697,890  (10 unwritten)
2019/05/07/8109        3 of   697,675  (17 unwritten)
2019/05/10/8149        2 of   697,675  (17 unwritten)
2019/05/12/8172        3 of   697,675  (17 unwritten)
2019/05/17/8238        1 of   697,675  (17 unwritten)
2019/05/18/8253        1 of   697,890  (17 unwritten)
2019/05/19/8277   38,468 of   697,675  (10 unwritten)
2019/05/20/8280   38,485 of   697,675  (10 unwritten)
2019/05/20/8283   38,468 of   697,675  (10 unwritten)
2019/05/23/8329        4 of   554,700  (15 unwritten)
2019/05/26/8378   39,348 of   697,890  (3 unwritten)
2019/05/27/8383        2 of   624,575  (17 unwritten)
2019/05/29/8421        1 of   697,675  (17 unwritten)
2019/05/30/8430        3 of   697,675  (17 unwritten)
2019/05/31/8439   39,350 of   697,675  (10 unwritten)
2019/06/03/8480        1 of   697,675  (19 unwritten)
2019/06/06/8523   39,886 of   697,675  (12 unwritten)
2019/06/06/8531        2 of   697,890  (17 unwritten)
2019/06/06/8532       10 of   697,890  (17 unwritten)
2019/06/07/8543        4 of   697,675  (17 unwritten)
2019/06/09/8576   40,032 of   697,675  (10 unwritten)
2019/06/10/8579        1 of   624,575  (17 unwritten)
2019/06/10/8581   40,101 of   697,675  (10 unwritten)
2019/06/12/8614        4 of   697,890  (15 unwritten)
2019/06/12/8618   40,309 of   697,675  (13 unwritten)
2019/06/13/8624   40,423 of   697,890  (10 unwritten)
2019/06/13/8628   27,625 of   697,675  (14 unwritten)
2019/06/13/8630        4 of   697,675  (15 unwritten)
2019/06/13/8634   40,202 of   697,675  (14 unwritten)
2019/06/14/8638        4 of   624,575  (15 unwritten)
2019/06/14/8640   40,316 of   697,675  (10 unwritten)
2019/06/16/8674        2 of   697,675  (19 unwritten)
2019/06/17/8681   10,585 of   697,675  (14 unwritten)
2019/06/20/8726        3 of   697,890  (19 unwritten)
2019/06/21/8736   31,862 of   697,890  (14 unwritten)
2019/06/22/8758   40,852 of   624,790  (10 unwritten)
2019/06/22/8759   40,632 of   624,575  (14 unwritten)
2019/06/24/8785   40,692 of   697,675  (10 unwritten)
2019/06/26/8808        2 of   697,890  (17 unwritten)
2019/06/26/8815   40,746 of   697,675  (10 unwritten)
2019/06/28/8840        4 of   697,675  (15 unwritten)
2019/06/29/8850   27,224 of   697,675  (14 unwritten)
2019/11/12/10784   17,415 of    17,415  (14 unwritten)
2021/12/11/21566    1,505 of     1,505  (14 unwritten)
2022/01/20/22141   24,510 of    24,510  (14 unwritten)
```
