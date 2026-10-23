# AIRS and CrIS (NASA TROPESS / MUSES HDO)

Not built yet. Sources:
- **Surveyed 2026-10-22:** a header scan of every AIRS file then on disk
  (7,612 files, no read errors), value probes of one file per version, the
  NASA catalog (CMR), the TROPESS READMEs and User Guide, and Sarkar et al.
  (2026).
- **Every AIRS and CrIS collection is now on disk** (downloaded 2026-10-22 by
  the `access_tropess` codebase; its report is
  `~/work/data_access/access_tropess/HANDBACK.md`). The new AIRS folders were
  header-scanned on 2026-10-23 (8,740 files, no read errors), and Summary was
  matched against Standard on five day pairs.

AIRS v1 is built first. AIRS v2 waits for CrIS (user decision 2026-10-23),
which has 139 days of the same v2 layout. One reader serves every v1
collection (one file format).

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
  target within each box", with "both day and night time coverage".
  - **The box sampling holds in all four AIRS v1 collections** (measured
    2026-10-23 on 5 days each, R14): about one target per 0.7° box per
    overpass.
  - **What differs is how many boxes are filled**, which depends on the
    stream: RS fills 6-10x fewer boxes per day than FS, at ~110 km spacing
    against 54-78 km. The documents don't say why.
  - **"Day and night" fits RS only** (R13).
  - **The product type thins the rows further:** Summary keeps only rows with
    DOF >= 1.1.
- **FS v2 is a continuation, not a reprocessing.** It starts 2026-06-01 with
  algorithm R1p25 and format **F2p10**, the first change of the format's
  leading digit. v1 runs to 2026-05-31. The v2 README is the v1 document
  unchanged (last revised 2023-05-09, still headed "Version 1"), and the
  catalog states no differences.

### Every TROPESS HDO collection: upstream vs on disk

Upstream from CMR granule listings, 2026-10-22; sizes are CMR's. v2
collections are still growing. **Since the download of 2026-10-22, every
collection below is complete on disk** up to its cutoff. The "on disk" column
records what was held *before* that download.
- **New folders:** `raw/<AIRS|CRIS>/<ShortName.version>/<YYYY>/`, with
  `<ShortName.version>_manifest.csv` at the collection's top level.
- **Integrity:** every file was checked against CMR's size, opened, and
  matched on `ShortName` and `VersionID`.
- **v2 cutoffs** (2026-10-22): AIRS 2026-06-30 in all three types (it has not
  advanced since June); CrIS-JPSS1 Summary and Standard 2026-10-17 (139
  days), Full 2026-10-15 (137).
- **The two partly held collections** span two folders each: the old download
  folder and the new `ShortName.version` one.

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

## Product scheme (decided 2026-10-22, revised 2026-10-23)

- **One product per platform, stream and collection version (2026-10-23).**
  - Summary is merged into Standard, so there is no Summary product and no
    `summary`/`standard` token in the name. This replaces the 2026-10-22 plan
    of one product per product type.
  - The reason: Summary v1 is exactly Standard's rows with DOF >= 1.1, with
    identical values (Summary vs Standard, below).
  - Each product gets its own obs axis, geolocation store and config.
- **Store names follow the style guide's version rule:** the collection
  version, then the stream after a period, as the guide's `v_3_5.nrt`:
  - `wisosat.airs.v_1.rs.inst.native_swath.<variable>.zarr`
  - `wisosat.airs.v_1.fs.inst.native_swath.<variable>.zarr`

- **RS and FS stay separate products** (user decision 2026-10-23). They are
  built to join cleanly: the same variables, names, units, dims, chunking and
  filtering guidance, so concatenating on `obs` is one call. Each store's
  metadata points to the other ("continued by" / "preceded by") and states
  the seam:
  - RS fills 6-10x fewer 0.7° boxes per day (R14);
  - RS is about half night, FS almost all day (R13);
  - RS is reanalysis with one algorithm (R1p6), FS forward processing with
    14 versions;
  - TROPESS's "1.12.0 Fixed HDO error calculation" postdates R1p6 by version
    number (inferred; TROPESS does not say what RS contains);
  - no data 2020-04 .. 2021-01 (R1).

  Why: a merged store would present a changing sample and processing as one
  record, with nothing overlapping to measure the step; the style guide keeps
  a low-latency stream apart (`v_3_5.nrt`); and CrIS-SNPP's RS and FS retrieve
  the same targets where they overlap (R26), so merging would not carry over
  to CrIS. v2 is a separate `v_2` store set: its layout differs.
- **Full and special collections:** added when wanted. The user's "four max"
  was a guideline, not a rule. A v2 Full product would be its own question,
  because in v2 only Full keeps every row (R25).
- **Checked on every file:** `ShortName` (stream and type), `VersionID`,
  `Platform`, `Instrument`, and `source` against the name's `R1pNN`.

### The Summary merge (decided 2026-10-23; recorded in docs and metadata)

- **A granule is one day: the Standard file and the Summary file**, read
  together as GOSAT reads its DED and H2O files (multi-file granules,
  CLAUDE.md).
- **The obs axis is Standard's rows.** The five Summary-only fields
  (`dd_col_p`, `dd_col_p_error`, `dd_004`, `x_h2o_col_p`, `x_h2o_col_p_error`)
  are placed on their Standard rows by matching `time`, `latitude` and
  `longitude`. They are NaN on rows with DOF < 1.1, which Summary leaves out.
- **Checked from raw, by the build and by the verifier:**
  - every Summary row matches one Standard row, in the same order;
  - the matched rows are exactly those with `signal_dof` >= 1.1;
  - every variable both files carry is identical on the matched rows, except
    `x` of target 0 (R22).
- **Summary's `target_id`** fills in where the Standard file lacks it (FS
  R1p11 and early R1p12), if the audit confirms it agrees wherever both have
  it.
- **Metadata:** each store records the merge:
  - both collections (`ShortName`, version, DOI) and both files per granule
    (`granule_file`);
  - the DOF >= 1.1 relationship;
  - for the five Summary fields, that they come from the Summary product and
    are absent where DOF < 1.1.
- **Days with only one of the two files** (R23): RS 3 days, FS v1 11 days.
  - A Standard-only day gives rows with the Summary fields NaN.
  - A Summary-only day gives rows with no Standard diagnostics (kernel,
    prior, DOF and so on are NaN), so every observation is kept.
  - Open: confirm with the user when the production subset is drafted.

### The first-row defect (R22; decided 2026-10-23: masked, declared)

`x` of the first target in every Standard file is not the retrieval: it is
`x_test` (R22). The build masks that one value (all 17 levels of `x`, row 0
of each Standard file) as a **declared defect**. It is not detected: it is
listed in config and confirmed from raw by the reader and by the verifier,
which check that the row's `x` equals `x_test`. It is recorded in the docs
(here) and in each affected store's metadata. Everything else in that row is
kept.
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

## Summary vs Standard, v1 (measured 2026-10-23)

Five day pairs tested: RS 2003-03-01 and 2010-06-15; FS 2021-02-01 (R1p11),
2022-06-01 (R1p17) and 2025-06-01 (R1p24). Sampled Standard files for R22: 40
across RS and every FS version.

1. **Same rows, filtered.** Summary is exactly Standard's rows with
   `signal_dof` >= 1.1, in the same order, with no mismatches in any pair.
   The Summary minimum DOF is 1.100.
2. **Same values.** All 16-17 per-observation variables they share are
   identical on matched rows: geolocation, `time`, `datetime_utc`, `x`,
   `x_h2o`, `pressure`, `altitude`, the flags and the AIRS indices. The one
   exception is `x` of target 0 (R22).
3. **Only in Summary:** `dd_col_p`, `dd_col_p_error`, `dd_004`,
   `x_h2o_col_p`, `x_h2o_col_p_error`. FS Summary also has `target_id` in
   R1p11 (format F0p6 throughout), where Standard does not.
4. **Only in Standard:** `averaging_kernel`, `xa`, `observation_error`,
   `observation_error_h2o`, `signal_dof`, `average_cloud_eod`,
   `cloud_top_pressure`, `surface_temperature`, `x_raw`, `x_h2o_raw`, and the
   rows with DOF < 1.1.
5. **Totals** (header scans 2026-10-22 and 10-23):

   | collection | files | obs | Summary / Standard |
   | --- | --- | --- | --- |
   | RS Summary | 6,361 | 11,063,132 | 65% |
   | RS Standard | 6,362 | 17,107,958 | |
   | FS Summary v1 | 1,814 | 19,071,666 | 40% |
   | FS Standard v1 | 1,815 | 47,829,401 | |

6. **Dates almost match** (R23):
   - RS Standard has 2002-08-30 and 08-31, which Summary lacks, and lacks
     2020-03-31, which Summary has;
   - FS v1 has 5 Summary-only days (2022-06-19, 2022-11-06, 2024-04-03,
     2024-11-11, 2024-12-03) and 6 Standard-only days (2021-02-12,
     2024-02-07, 2024-08-05, 2025-01-12, 2025-01-24, 2025-03-05).
7. **v2 is different** (R25): Standard v2 is already cut at DOF >= 1.1, so it
   has the same rows as Summary v2; only Full v2 keeps every row.

**Stream vs type, resolved** (20 days measured, R13 and R14). All four
collections take about one target per 0.7° box per overpass.
- **The stream** sets how many boxes are filled (RS 6-10x fewer) and the
  overpasses (RS about half night, FS almost all day).
- **The product type** sets the DOF >= 1.1 filter (Summary keeps 65% of RS
  rows and 40% of FS rows) and the contents.

## AIRS RS Summary vs FS Standard (measured 2026-10-22)

Measured before RS Standard was on disk. Stream and type changed together
here; the section above separates them.

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
- **Products:** only Standard (and Full) have a kernel and prior. With
  Summary merged into Standard (2026-10-23), every v1 product carries them,
  NaN only on Summary-only days (R23).

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
  - **Confirmed exactly (2026-10-23):** with the true target-0 profile from
    Summary, `exp(ln xa + A (ln x − ln xa))` with A applied as stored
    reproduces `x_test` to 4-6e-8 in all 5 files where Summary has that row.
    Aᵀ misses by 4e-3 to 9e-2.
  - The 2026-10-22 tests were inexact (1e-5 to 2e-2) because Standard's
    `x[0]` is itself `x_test` (R22), not the retrieval.

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
| R13 | **AIRS FS is almost all daytime**: ~13:30 local solar time, against both overpasses in RS (55-57% local night in RS Summary and RS Standard). Night-side FS rows only at \|lat\| ~67-76 in summer. The READMEs say both streams have "day and night time coverage". A property of the stream, not the type (2026-10-23). | record only |
| R14 | **AIRS FS fills 6-10x more 0.7° boxes per day than RS** (corrected 2026-10-23; first read as FS not being box-sampled). All four v1 collections take about one target per box per overpass, as the READMEs describe, measured on 5 days each. <br>- Obs per day, record average: RS 1,739 Summary and 2,689 Standard; FS 10,514 and 26,352. <br>- Boxes filled per day: RS 1,352-2,691; FS 6,788-29,539. <br>- Nearest-neighbour spacing, p50: RS ~110 km; FS 54-78 km. <br>The stream sets the boxes covered. The type thins further (Summary = DOF >= 1.1: 65% of RS rows, 40% of FS). Why RS fills so few boxes is not documented. | record only |
| R15 | **`observation_error_h2o` fill changes by version:** from R1p12 F0p2 it is written below the surface (level 0 fill 0-3% vs 53-64% for `x`); from R1p15 its top level (0.1 hPa) is fill on ~96-98% of rows. | record only; confirm over the record at the audit |
| R16 | **FS integer dtypes drift:** int32 → int16 (`airs_*` indices, `day_night_flag`), int32/int64 (`land_flag`, `target_id`). | open: store as int32 with a `_FillValue` (existing rule) |
| R17 | **`dd_col_p_error` is -9999 on ~70% of RS Summary rows** (747 of 1,017; 1,454 of 2,019; 1,170 of 1,588 in three files), where `dd_col_p` is written. | record only |
| R18 | **CrIS-JPSS1 FS Standard v1 was backfilled upstream in 2025:** 108 granules with algorithm R1p24 dated before its R1p24 period (2021-05-21 ..). 5 replace files we hold under older names (2021-05-21, 2022-03-08, 2022-08-13, 2023-12-27, 2024-08-21; upstream updated 2025-09-04 .. 09-11); others fill days missing at our download. One file per date upstream. The 5 new files are downloaded and the old ones kept (the old ones are no longer in CMR). | open, for CrIS: which granule to keep where two exist |
| R19 | **Days not downloaded at first:** AIRS FS Standard 2023-07-21 and 2023-10-19; CrIS-JPSS1 FS Standard 46 dates within our window (2022-05-29 .. 2024-09-01). | handled: downloaded 2026-10-22 |
| R20 | **The README's Summary column kernel is absent** from the RS Summary HDO files (v1). | record only |
| R21 | **`x_test` is one 17-level profile per file** (target 0), not per target: the guide's check of the kernel convention, and the value written over `x[0]` (R22). | handled: not stored |
| R22 | **`x` of the first target in every Standard file is `x_test`, not the retrieval** (all 40 Standard files sampled: RS R1p6 and every FS version R1p11 .. R1p24). It is the kernel applied to the true profile, which Summary holds where that row has DOF >= 1.1 (it reproduces to 5e-8). It differs from the retrieval by up to ~6%. Only `x` is affected; the rest of the row is identical to Summary's. One obs per file: 8,177 in AIRS v1. | decided (user, 2026-10-23): masked as a declared defect, recorded in docs and metadata; confirmed from raw (row-0 `x` equals `x_test`) on every file at build and verify |
| R23 | **Standard and Summary dates differ slightly:** RS 2 Standard-only days (2002-08-30, 08-31) and 1 Summary-only (2020-03-31); FS v1 6 Standard-only and 5 Summary-only (listed under Summary vs Standard). | open: the merge's one-sided days (Product scheme) |
| R24 | **AIRS FS v1 has 72 upstream gap days after 2024-09-05**, in 18 runs (e.g. 2024-09-17 .. 19, 2024-10-04 .. 19). | record only (`known_data_gaps`) |
| R25 | **v2 (R1p25, format F2p10) changes the layout:** <br>- Standard is on 34 levels, cut at DOF >= 1.1, and adds `averaging_kernel_h2o`, the five column fields and `air_density`; `target_id` becomes a 36-character string. <br>- Summary stays on 17 levels with the same rows as Standard. <br>- Full keeps every row, on 67 forward-model and 34 retrieval levels, with every HDO/H2O kernel and covariance block (some as compressed int8 bytes). | record only; v2 designed with CrIS (user, 2026-10-23) |
| R26 | **CrIS-SNPP RS and FS retrieve the same targets where they overlap** (2021-02-01 .. 05-21): on 2021-03-01, 326 of RS's 1,111 targets are also in FS (R1p17 vs R1p11). `x` differs by p50 0.17%, up to 10%, and the matched times differ by up to 87 s. TROPESS 1.10 "Fixed to use correct observation time in CrIS products". | open, for CrIS |
