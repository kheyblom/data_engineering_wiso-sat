# AIRS and CrIS (NASA TROPESS / MUSES HDO)

Not built yet. Surveyed 2026-10-22: header scan of every AIRS file on disk
(7,612 files, no read errors), value probes of one file per version, the
NASA catalog (CMR), the TROPESS READMEs and User Guide, and Sarkar et al.
(2026). **Waiting on downloads** (user decision 2026-10-22): everything for
AIRS and CrIS not on disk is fetched by a separate data-access codebase,
briefed in `docs/handoff-tropess-download.md`. AIRS is built first, CrIS once
AIRS is finalized. One reader will serve every collection (one file format).

## Collections: stream, product type, platform

Every TROPESS file carries two independent labels, both in its name and
`ShortName` (`TRPS` + `D` Standard / `Y` Summary / `F` Full + `L2HDO` +
instrument + stream):

```
TROPESS_AIRS-Aqua_L2_Summary_HDO_20100615_MUSES_R1p6_RS_F0p8_J0.nc
                     ^^^^^^^ product type     ^^^^ ^^ ^^^^ ^^
                                       algorithm  |  format  joint flag
                                             stream
```

- **Stream** (README "ProcessingStrategy"):
  - **RS, Reanalysis Stream:** the past record reprocessed with one fixed
    algorithm version;
  - **FS, Forward Stream:** "low-latency" processing that keeps up with new
    data, so its algorithm changes as it goes;
  - **SC, special collections:** regional, on request.
- **Product type** (README 1.1, 2.2; User Guide 1.2):
  - **Full:** the archival product;
  - **Standard:** "a subset of the parameters in the Full archival product",
    for "full analysis with averaging kernel and covariance";
  - **Summary:** "smaller file size … first-look and rapid analysis …
    total and partial column product".
- **Versions** (README 1.3.3, 1.3.4, 2.2):
  - **Collection version:** the root `VersionID` and the `.N` of the
    `ShortName.N` collection. "Version 1: This is the first version of this
    product."
  - **Algorithm version:** `R1pNN` in the name, `source: MUSES v1.NN` in the
    file. They match in every file scanned.
  - **Format version:** `F0pN`. A change "signals a change in the netCDF file
    layout, which would likely require a change in the users' data readers".
  - **Joint processing indicator:** `J0` single, `J1` joint retrieval.
- **Sampling** (both READMEs): "subsampled using a grid sampling approach"
  with 0.7° boxes for AIRS and 0.8° for CrIS, keeping "the single, center most
  target within each box", with "both day and night time coverage". This fits
  AIRS RS Summary but not AIRS FS Standard (R13, R14).
- **FS v2 is a continuation, not a reprocessing.** It starts 2026-06-01 with
  algorithm R1p25 and format **F2p10**, the first change of the format's
  leading digit. v1 runs to 2026-05-31. The v2 README is the v1 document
  unchanged (last revised 2023-05-09, still headed "Version 1"), and the
  catalog states no differences.

### Every TROPESS HDO collection: upstream vs on disk

Upstream from CMR granule listings, 2026-10-22; sizes are CMR's. v2
collections are still growing.

| instrument | collection (`ShortName.version`) | stream, type | upstream | algorithm, format | size | on disk |
| --- | --- | --- | --- | --- | --- | --- |
| AIRS | `TRPSYL2HDOAIRSORS.1` | RS Summary | 6,361 days, 2002-09-01 .. 2020-03-31 | R1p6 F0p8_J0 | 3.0 GB | **all 6,361** (names match) |
| AIRS | `TRPSDL2HDOAIRSORS.1` | RS Standard | 6,362 days, 2002-08-30 .. 2020-03-30 | R1p6 F0p8_J0 | 36.1 GB | none (released 2026-03-19) |
| AIRS | `TRPSYL2HDOAIRSFS.1` | FS Summary | 1,814 days, 2021-02-01 .. 2026-05-31 | R1p11 .. R1p24, F0p6 .. F0p9 | 4.2 GB | none |
| AIRS | `TRPSYL2HDOAIRSFS.2` | FS Summary | 30 days, 2026-06 | R1p25 F2p10_J1 | 0.1 GB | none |
| AIRS | `TRPSDL2HDOAIRSFS.1` | FS Standard | 1,815 days, 2021-02-01 .. 2026-05-31 | R1p11 .. R1p24, F0p1 .. F0p9 | 98.9 GB | **1,251** (2021-02-01 .. 2024-09-04); 564 missing, 30.8 GB |
| AIRS | `TRPSDL2HDOAIRSFS.2` | FS Standard | 30 days, 2026-06 | R1p25 F2p10_J1 | 1.5 GB | none |
| AIRS | `TRPSFL2HDOAIRSFS.2` | FS Full | 30 days, 2026-06 | R1p25 F2p10_J1 | 18.8 GB | none (no v1 Full) |
| CrIS-SNPP | `TRPSYL2HDOCRSRS.1` | RS Summary | 1,865 days, 2015-12-01 .. 2021-05-21 | R1p17 F0p8_J0 | 0.7 GB | **all 1,865** (names match) |
| CrIS-SNPP | `TRPSYL2HDOCRSFS.1` | FS Summary | 110 days, 2021-02-01 .. 2021-05-21 | R1p11, R1p12 F0p6 | 0.3 GB | none |
| CrIS-SNPP | `TRPSDL2HDOCRSFS.1` | FS Standard | 110 days, 2021-02-01 .. 2021-05-21 | R1p11, R1p12 F0p1 | 5.6 GB | none |
| CrIS-SNPP | `TRPSDL2HDOCRSAUS.1` | SC Standard (Australian fires) | 91 days, 2019-11 .. 2020-01 | R1p9 F0p1 | 0.8 GB | none |
| CrIS-JPSS1 | `TRPSYL2HDOCRS1FS.1` | FS Summary | 1,887 days, 2021-04-01 .. 2026-05-31 | R1p12 .. R1p24 | 5.8 GB | none |
| CrIS-JPSS1 | `TRPSYL2HDOCRS1FS.2` | FS Summary | 138 days, 2026-06-01 .. 2026-10-16 | R1p25 F2p10_J0 | 0.8 GB | none |
| CrIS-JPSS1 | `TRPSDL2HDOCRS1FS.1` | FS Standard | 1,887 days, 2021-04-01 .. 2026-05-31 | R1p12 .. R1p24 | 100.3 GB | **1,208** (2021-04-01 .. 2024-09-05); 684 missing, 36.5 GB (R18) |
| CrIS-JPSS1 | `TRPSDL2HDOCRS1FS.2` | FS Standard | 138 days, 2026-06-01 .. 2026-10-16 | R1p25 F2p10_J0 | 9.7 GB | none |
| CrIS-JPSS1 | `TRPSFL2HDOCRS1FS.2` | FS Full | 137 days, 2026-06-01 .. 2026-10-15 | R1p25 F2p10_J0 | 85.8 GB | none |

- **On disk:**
  - `raw/AIRS/TRPSYL2HDOAIRSORS_1-20240806_185241/`;
  - `raw/AIRS/TRPSDL2HDOAIRSFS_1-20240912_174250/` (also holds L3 files, R6, and 173 local `_target` copies, R5);
  - `raw/CRIS/TRPSYL2HDOCRSRS_1-20240923_230130/`;
  - `raw/CRIS/TRPSDL2HDOCRS1FS_1-20240912_023602/`.
- **No AIRS data exists 2020-04 .. 2021-01** in any collection (R1).
- **No CrIS RS Standard** collection is listed. SNPP's mid-wave band failed on
  2021-05-21, after which TROPESS made no SNPP HDO (RS README).

## Product scheme (decided 2026-10-22)

- **One product per platform, stream, product type and collection version.**
  Each gets its own obs axis, geolocation store and config. Full and
  special-collection products are added when downloaded (the user's "four
  max" was a guideline, not a rule).
- **Store names follow the style guide's version rule:** the collection
  version, then the stream and product type after a period, as the guide's
  `v_3_5.nrt`. For example:
  - `wisosat.airs.v_1.rs_summary.inst.native_swath.<variable>.zarr`
  - `wisosat.airs.v_1.fs_standard.inst.native_swath.<variable>.zarr`
  - `wisosat.airs.v_2.fs_standard.inst.native_swath.<variable>.zarr`

  The last is a separate store set, built if and when v2 is downloaded.
- **Checked on every file:** `ShortName` (stream and product type),
  `VersionID`, `Platform`, `Instrument`, and `source` against the name's
  `R1pNN`.
- **Recorded in the metadata, per granule (approved; shared change):**
  - the algorithm (`R1pNN`), format (`F0pN`) and joint flag, as granule-index
    coordinates;
  - a store attribute listing each version's date span;
  - collection `ShortName`, version and DOI.

  Today `source_processor_version` comes from the first granule only
  (`utils/zarr_utils.py` `global_attrs`), which would be wrong for FS. IASI
  (I7) needs the same.
- **CrIS carries the platform in the product token** (`cris_snpp`,
  `cris_jpss1`, as `gosat` and `gosat2`). SNPP and JPSS1 FS overlap
  2021-04-01 .. 2021-05-21. The rest of CrIS is settled when it is reached.

## AIRS RS Summary vs FS Standard (measured 2026-10-22)

These are the two AIRS collections on disk. They differ in stream *and* type
at once, so the differences below cannot yet be assigned to one or the other.
RS Standard would separate them: compared with RS Summary it isolates the
type, compared with FS Standard the stream.

| | RS Summary | FS Standard v1 (on disk) |
| --- | --- | --- |
| files, obs | 6,361; 11,063,132 (p50 1,679 per day; min 8, max 2,579) | 1,251; 33,190,978 (p50 27,079 per day; min 13,805, max 32,873) |
| missing days in span | 61, all upstream gaps; longest 2003-10-30 .. 11-18 (20 d) and 2010-01-10 .. 01-25 (16 d) | 61: 59 upstream gaps (many in 2024), plus 2023-07-21 and 2023-10-19 not downloaded |
| produced | 2023-10-23 .. 11-02, in one pass | 2021-05-22 .. 2024-09-11, as the data came in |
| local solar time | both overpasses, ~50/50 at ~01:30 and ~13:30 | nearly all ~13:30. Night-side rows only at \|lat\| ~67-76 in summer, plus the `day_night_flag` -999 rows (R13) |
| pre-filtered | yes: convergence and sensitivity (Sarkar et al.) | no. DOF p1 ~0.001; 28-58% of rows pass DOF >= 1 and COD <= 0.5 in the files probed |
| `x`, `x_h2o`, `pressure`, `altitude` on 17 levels | yes | yes |
| `dd_col_p`, `dd_col_p_error`, `dd_004`, `x_h2o_col_p`, `x_h2o_col_p_error` | yes | no |
| `xa`, `averaging_kernel`, `observation_error`, `observation_error_h2o`, `signal_dof`, `x_test` | no | yes |
| `average_cloud_eod`, `cloud_top_pressure`, `surface_temperature` | no | yes |
| `land_flag`, `day_night_flag`, `airs_*` indices, `year_fraction`, `datetime_utc` | yes | yes |
| `target_id` | no | from R1p12 (9 of 183 R1p12 F0p1 files, then all) |
| `retrieval/x_raw`, `x_h2o_raw` | no | from R1p12 F0p2 (21 of 43, then all) |
| microwindow variables | yes | from R1p22 only |

- **Sarkar et al. (2026)** treat AIRS as one record: Summary before 2021,
  Standard after. They filter Standard with DOF >= 1 and COD <= 0.5, and name
  no TROPESS or MUSES version anywhere.
- **The README's column kernel is missing.** It says Summary products
  "include column averaging kernel"; the RS Summary HDO files have no kernel
  of any kind.

### AIRS FS Standard v1 version periods (on disk)

R1p12 F0p3 overlaps F0p2 over 2021-10-23 .. 11-09. `LongName` reads "…for FS…"
in 209 files and "…for Forward Stream…" in 1,042.

| algorithm, format | files | dates | produced |
| --- | --- | --- | --- |
| R1p11 F0p1 | 59 | 2021-02-01 .. 03-31 | 2021-05-22 |
| R1p12 F0p1 | 183 | 2021-04-01 .. 09-30 | 2021-05-22 .. 10-06 |
| R1p12 F0p2 | 43 | 2021-10-01 .. 11-30 | 2021-10-11 .. 2022-01-12 |
| R1p12 F0p3 | 18 | 2021-10-23 .. 11-09 | 2021-11-11 .. 11-21 |
| R1p13 F0p3 | 31 | 2021-12 | 2022-01 |
| R1p14 F0p3 | 59 | 2022-01-01 .. 02-28 | 2022-01-27 .. 03-06 |
| R1p15 F0p3 | 52 | 2022-03-01 .. 04-30 | 2022-03-16 .. 05-08 |
| R1p16 F0p4 | 31 | 2022-05 | 2022-05-13 .. 06-16 |
| R1p17 F0p4 | 91 | 2022-06-01 .. 08-31 | 2022-06-22 .. 12-01 |
| R1p18 F0p6 | 61 | 2022-09-01 .. 10-31 | 2022-12 |
| R1p19 F0p6 | 147 | 2022-11-01 .. 2023-03-31 | 2023-02-13 .. 04-14 |
| R1p20 F0p6 | 120 | 2023-04-01 .. 07-31 | 2023-04-19 .. 08-12 |
| R1p21 F0p7_J1 | 91 | 2023-08-01 .. 10-31 | 2023-10-19 .. 11-09 |
| R1p22 F0p8_J1 | 30 | 2023-11 | 2023-11-15 .. 12-10 |
| R1p22 F0p9_J1 | 121 | 2023-12-01 .. 2024-04-24 | 2023-12-11 .. 2024-05-01 |
| R1p23 F0p9_J1 | 114 | 2024-04-25 .. 09-04 | 2024-05-08 .. 09-11 |

Upstream v1 continues with R1p23 to 2025-03-27 and R1p24 2025-03-28 ..
2026-05-31. The TROPESS algorithm change log (FS README 1.3.4, to 1.20) has
one HDO entry: "1.12.0 Fixed HDO error calculation". The User Guide (MUSES
1.11) says the March 2021 release's "predicted error is overestimated".

## Format

- **Groups:** root, `geolocation`, `geophysical`; Standard adds
  `observation_ops`; `retrieval` is in RS Summary and newer FS Standard.
- **Dims:** observation dim `target`; `level` 17; `datetime_utc_dim` 6.
  `x_test` is on `level` only: one profile per file (R21).
- **Time is TAI93** (R3). `time` is float64 seconds since 1993-01-01, with
  `long_name` `time_tai93` and the README's "International Atomic Time (TAI)".
  It runs ahead of `datetime_utc` by the leap seconds since 1993: 5 s (2002),
  7 s (2010), 10 s (2020 on), constant within each file probed.
  `datetime_utc` holds whole seconds only.
- **Vertical grid:** the same in both streams and every version. Levels 1-16
  are fixed: 1000, 908.5, 825.4, 749.9, 681.3, 619.0, 510.9, 421.7, 348.1,
  287.3, 237.1, 177.8, 133.4, 75.0, 28.7 and 0.1 hPa.
  - The **lowest valid level holds the surface pressure**: level 0 where the
    surface is below 1000 hPa, otherwise the first grid level above the
    surface. Levels below the surface are fill.
  - `x`, `x_h2o`, `xa`, `pressure` and `altitude` share this fill pattern.
    Level 0 is fill on 25-64% of rows (R10).
- **Fill:** `_FillValue` -999 throughout, but `missing_value` is -9999 on
  `dd_col_p`, `dd_col_p_error` and `dd_004` (R2). Observed: `dd_col_p_error`
  is -9999 on ~70% of RS rows (R17); `dd_col_p` and `dd_004` showed no fill in
  the files probed.
- **Every row has time, lat and lon** in every file probed.
- **Pre-filtering, as documented:**
  - the User Guide (MUSES 1.11): "a pre-quality check, which involves checks
    for retrieval convergence and measurement sensitivity. There are no checks
    for clouds or land versus ocean";
  - the READMEs (1.4): "For the standard products, these quality flags have
    already been applied";
  - Sarkar et al.: Summary is pre-filtered, Standard is not.

  The FS Standard values (DOF down to ~0) fit Sarkar et al.

## Variables and units

- **`x`:** bias-corrected HDO/H2O **mole ratio** profile (`1`, p50 2.3e-4).
  It is a ratio, not δD and not a mole fraction: keep `1`.
- **`x_h2o`:** bias-corrected H2O dry-air VMR profile (`1`) → `1e-6` (x 1e6).
  The basis is explicitly dry in RS, and dry for FS per Sarkar et al. (2026).
  Values reach 0.72 mol mol-1, which is unphysical (R7).
- **RS Summary only:**
  - `dd_col_p` and `dd_col_p_error`: mean δD 850-250 hPa (`1e-3`, already
    canonical);
  - `dd_004`: δD at a VMR of 4 per mil (`1e-3`);
  - `x_h2o_col_p` and `x_h2o_col_p_error` (`1e-6`, canonical).
- **Standard only:**
  - `observation_ops/xa`: a priori ratio, `1`.
  - `observation_ops/averaging_kernel` (17 x 17, **log-space** ratio kernel)
    and `observation_error`.
  - **`observation_error` is left out of the stores** (user decision
    2026-10-19). It is not a valid covariance in any version sampled (R11).
    Its reserved name is `water_vapor_hdo_h2o_ratio_observation_error_covariance_log`
    (`docs/model-comparison-naming.md` N16). Revisit only if TROPESS documents
    or fixes it.
  - `observation_ops/observation_error_h2o`: `1`, **a relative / ln-space
    error, p50 0.09. Never scale it x 1e6.** Its fill pattern changes by
    version (R15).
  - `signal_dof` ("trace of averaging kernel"), `geophysical/average_cloud_eod`
    (the COD of the filter), `cloud_top_pressure` (hPa) and
    `surface_temperature` (K).
  - `x_test`; `retrieval/x_raw` and `x_h2o_raw` (uncorrected), in newer
    versions only.
- **Layout drift in FS Standard** (R16):
  - `airs_atrack`, `airs_xtrack`, `airs_granule` and `day_night_flag` go from
    int32 (393 files) to int16 (858);
  - `land_flag` is int64 in 130 files, otherwise int32;
  - `target_id` is int32 in 52 files, otherwise int64;
  - `retrieval/mw` units change from `cm-1` to `m-6`;
  - `long_name` wording changes (case and suffixes).

  Units of the science variables do not change.
- **Flags:** `land_flag` 1 = land; `day_night_flag` 1 = day, 0 = night
  (README Table 8). FS Standard also has -999 on up to ~2% of rows.
- **Profile coordinate:** `pressure` (hPa) and `altitude` on `level`.
  `pressure` becomes its own store (N3).

## Filtering guidance to record, not apply

- **FS Standard:** DOF >= 1 and COD <= 0.5 (Sarkar et al. 2026).
- **User Guide 4.2:** "a good rule of thumb is to begin to trust results in
  which DOFS > 0.7".
- **RS Summary:** already filtered upstream.

## Model-comparison variables (named 2026-10-19)

Named in the cross-product naming pass. The grammar and decisions are in
`docs/model-comparison-naming.md`; the rows are in `nomenclature_data.md`
(style_guides `fee64ec`). Units are after conversion. Not built yet.

- **Dims:** `level` (17) stays `level`. The files declare matrices as
  `(target, level, level)`, which xarray cannot represent, so the second axis
  becomes `level_2`.
- **Vertical order:** `surface_first`.
- **Products:** only Standard (and Full) have a kernel and prior. Summary has
  neither, so a Summary product has only `pressure` of these.

| source | products | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- | --- |
| `observation_ops/xa` | Standard | `water_vapor_hdo_h2o_ratio_apriori` | unitless | (obs, level) | none |
| `observation_ops/averaging_kernel` | Standard | `water_vapor_hdo_h2o_ratio_averaging_kernel_log` | unitless | (obs, level, level_2) | none; "logarithmic_averaging_kernel_hdo_to_h2o_ratio" |
| `observation_ops/observation_error_h2o` | Standard | `water_vapor_h2o_mole_fraction_dry_air_observation_standard_error_log` | unitless | (obs, level) | none; 1-sigma inferred (R12); never scaled |
| `observation_ops/observation_error` | Standard | **left out** (R11); reserved name `water_vapor_hdo_h2o_ratio_observation_error_covariance_log`, no row | — | (obs, level, level_2) | — |
| `pressure` | all | `pressure`, its own store | Pa | (obs, level) | x 100 from `hPa`; below-surface levels are fill (R10) |

- **The kernel is published whole**, so it is one array in one store.
- **Rows retrieved, columns true** (User Guide 4.1). The guide gives
  `ln(x̂) = ln(xa) + A (ln(x_true) - ln(xa))` and warns that A "is not
  symmetric so getting the row/column order of A correct is critical". It
  offers `x_test` (target 0) as the check.
  - Applied as stored (A @ d), A reproduces `x_test` to 9e-3 (R1p17) and 3e-3
    (R1p23, with `x_raw`). Aᵀ gives 4e-2 and 2e-2.
  - In R1p12 F0p3 with `x_raw`, A matches to 1e-5 against 3e-4 for Aᵀ.
  - R1p11 does not discriminate (4e-4 both ways).
  - `x_test` reproduces exactly in no version, so the input TROPESS used for
    it is not certain.

## Sources

- TROPESS Reanalysis Stream README (2023-10-25):
  https://tropess.gesdisc.eosdis.nasa.gov/data/TROPESS_Reanalysis_Summary/TRPSYL2O3AIRSORS.1/doc/TROPESS_Reanalysis_Stream_README.pdf
- TROPESS Forward Stream README (2023-05-09; the same file under the FS
  Standard v1 and v2 folders):
  https://tropess.gesdisc.eosdis.nasa.gov/data/TROPESS_Standard/TRPSDL2HDOAIRSFS.2/doc/TROPESS_Forward_Stream_README.pdf
- TROPESS HDO/H2O Level 2 Standard Product User Guide (2020-11-02, MUSES
  1.11):
  https://docserver.gesdisc.eosdis.nasa.gov/public/project/TROPESS/User_Guides/TROPESS-AIRS-HDO_L2_Product_User_Guide_20201102.pdf
- ATBD v1.1: https://docserver.gesdisc.eosdis.nasa.gov/public/project/TROPESS/TROPESS_ATBDv1.1.pdf
- CMR: `https://cmr.earthdata.nasa.gov/search/collections.json?short_name=TRPS*L2HDO*&options[short_name][pattern]=true&provider=GES_DISC`;
  granules per collection by `collection_concept_id` (ids in
  `docs/handoff-tropess-download.md`).
- Sarkar et al. (2026), `docs/sarkar-2026-wiso-sat.md`: Methods (AIRS, CrIS;
  Product-specific quality control), Tables 2-3.

## Known data issues

Status: **handled** (the pipeline deals with it), **open** (settle before this product is built), **record only** (users should know; kept as published).

| # | issue | status |
| --- | --- | --- |
| R1 | **AIRS has no data 2020-04 .. 2021-01**, between the RS and FS streams, in any collection. CrIS SNPP RS and JPSS1 FS overlap by seven weeks (2021-04-01 .. 05-21). | record only |
| R2 | **Two fill conventions**: `_FillValue` -999 throughout, but `missing_value` -9999 on `dd_col_p`, `dd_col_p_error` and `dd_004`. | open: declare and mask both |
| R3 | **Time is TAI93** (confirmed 2026-10-22): `time` runs ahead of `datetime_utc` by 5-10 s of leap seconds. | open: convert to UTC in the reader with a leap-second table; check against `datetime_utc` on every file |
| R4 | **FS layout drifts by version** (16 algorithm/format periods on disk): variable presence (`target_id`, `retrieval/*`, microwindows), dtypes (R16) and `long_name` wording. Units are stable. | open: the reader tolerates absent variables; stores keep only variables present throughout, or are declared per period |
| R5 | **173 AIRS FS files end `_target.nc`** (2022-03-01 .. 08-31). They are local copies: `ncks -O --mk_rec_dmn target` run on 2024-09-29 against the plain file, with the same variables and rows. Not upstream. | handled: the reader skips `*_target.nc` |
| R6 | **The AIRS FS folder holds L3 files** (`AIRS_TROPESS_gridded_*`). | handled: glob `TROPESS_*` |
| R7 | **`x_h2o` reaches 0.72 mol mol-1**, which is unphysical. | record only |
| R8 | **`observation_error_h2o` is a ln-space relative error** with units `1`, sitting next to mole-fraction variables. | open: must never be scaled x 1e6 (project rule) |
| R9 | **RS Summary files are pre-filtered**; FS Standard files are not (DOF down to ~0). The documents disagree on which type is filtered (Format). | record only |
| R10 | **Level 0 of `pressure` is fill on 25-64% of rows in every version**, RS included (resolved 2026-10-22; first read as version drift). Levels below the surface are fill, and the lowest valid level holds the surface pressure. | record only; the fill is masked as usual |
| R11 | **FS `observation_error` is not a valid covariance.** Its `source` attribute says `obs_dd + obs_hh - obs_hd - obs_dh`, which must be symmetric with a non-negative diagonal. Negative variances appear in all three files sampled (AIRS R1p11 2021-02-10, CrIS-JPSS1 R1p17 2022-07-10, AIRS R1p20 2023-06-15), in 16-31% of targets at 750-619 hPa, where the kernel is largest. R1p17 and R1p20 are also asymmetric, by as much as the variances (2026-10-19). | decided (user, 2026-10-19): left out, with no nomenclature row (`docs/model-comparison-naming.md` N16). Revisit if TROPESS documents or fixes it; worth reporting to them |
| R12 | **`observation_error_h2o` looks 1-sigma**: p50 0.093, against p50 0.089 for the square root of TES's H2O observation-error variance. Neither the files nor the User Guide state it. | open |
| R13 | **AIRS FS Standard is almost all daytime**: ~13:30 local solar time, against both overpasses ~50/50 in RS Summary. Night-side rows only at \|lat\| ~67-76 in summer. The READMEs say both streams have "day and night time coverage". | record only; recheck with RS Standard and FS Summary |
| R14 | **AIRS FS Standard is ~15-20x denser than RS Summary** (p50 27,079 vs 1,679 obs per day). The READMEs describe one 0.7° subsample for both streams. | record only; recheck as R13 |
| R15 | **`observation_error_h2o` fill changes by version:** from R1p12 F0p2 it is written below the surface (level 0 fill 0-3% vs 53-64% for `x`); from R1p15 its top level (0.1 hPa) is fill on ~96-98% of rows. | record only; confirm over the record at the audit |
| R16 | **FS integer dtypes drift:** int32 → int16 (`airs_*` indices, `day_night_flag`), int32/int64 (`land_flag`, `target_id`). | open: store as int32 with a `_FillValue` (existing rule) |
| R17 | **`dd_col_p_error` is -9999 on ~70% of RS Summary rows** (747 of 1,017; 1,454 of 2,019; 1,170 of 1,588 in three files), where `dd_col_p` is written. | record only |
| R18 | **CrIS-JPSS1 FS Standard v1 was backfilled upstream in 2025:** 108 granules with algorithm R1p24 dated before its R1p24 period (2021-05-21 ..). 5 replace files we hold under older names (2021-05-21, 2022-03-08, 2022-08-13, 2023-12-27, 2024-08-21; upstream updated 2025-09-04 .. 09-11); others fill days missing at our download. One file per date upstream. | open, for CrIS: which granule to keep where two exist |
| R19 | **Days not downloaded:** AIRS FS Standard 2023-07-21 and 2023-10-19; CrIS-JPSS1 FS Standard 46 dates within our window (2022-05-29 .. 2024-09-01). | open: in the download handoff |
| R20 | **The README's Summary column kernel is absent** from the RS Summary HDO files. | record only |
| R21 | **`x_test` is one 17-level profile per file** (target 0), not per target. It is the guide's check of the kernel convention, not a variable to store. | handled: not stored |
