# AIRS and CrIS (NASA TROPESS / MUSES HDO)

**AIRS v1 is built and finalized** (2026-10-23, tag `v1-verified-20261023`;
TESTING.md, AIRS v1 run log). **CrIS v1 is built and finalized**
(2026-10-26, tag `v1-verified-20261026`; TESTING.md, CrIS v1 run log).
**v2 (AIRS and CrIS-JPSS1) is next: start at "v2: handoff" below.**
Sources:
- **Surveyed 2026-10-22:** a header scan of every AIRS file then on disk
  (7,612 files, no read errors), value probes of one file per version, the
  NASA catalog (CMR), the TROPESS READMEs and User Guide, and Sarkar et al.
  (2026).
- **Every AIRS and CrIS collection is now on disk** (downloaded 2026-10-22 by
  the `access_tropess` codebase; its report is
  `~/work/data_access/access_tropess/HANDBACK.md`). The new AIRS folders were
  header-scanned on 2026-10-23 (8,740 files, no read errors), and Summary was
  matched against Standard on five day pairs.

AIRS v1 was built first, then CrIS v1. AIRS v2 is designed with CrIS-JPSS1
v2 (user decision 2026-10-23), which has 139 days of the same v2 layout.
One reader (`products/tropess.py`) serves every v1 collection (one file
format); it assumes v1 in the places the v2 handoff lists.

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
    DOF > 1.1.
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
  - The reason: Summary v1 is exactly Standard's rows with DOF > 1.1, with
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
  `longitude`. They are NaN on rows with DOF <= 1.1, which Summary leaves out.
- **Checked from raw, by the build and by the verifier:**
  - every Summary row matches one Standard row, in the same order;
  - the matched rows are exactly those with `signal_dof` > 1.1;
  - every variable both files carry is identical on the matched rows, except
    `x` of target 0 (R22).
- **`target_id` is not stored** (Q4; it overflows int32 in 52 FS files,
  R16).
- **Metadata:** each store records the merge:
  - both collections (`ShortName`, version, DOI) and both files per granule
    (`granule_file`);
  - the DOF > 1.1 relationship;
  - for the five Summary fields, that they come from the Summary product and
    are absent where DOF <= 1.1.
- **Days with only one of the two files** (R23): RS 3 days, FS v1 11 days.
  - A Standard-only day gives rows with the Summary fields NaN.
  - A Summary-only day gives rows with no Standard diagnostics (kernel,
    prior, DOF and so on are NaN), so every observation is kept.
  - Decided with the production subset (Q1): every row of a one-sided day
    is kept.

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

## v2: handoff (written 2026-10-26, for a new session)

*Historical: v2 was decided, built and finalized 2026-10-28. What follows
was the starting point; the answers and the probes below supersede it (R25's
"cut at DOF >= 1.1" is R41's `quality == 1`).*

AIRS v1 and CrIS v1 are finished (tags `v1-verified-20261023` and
`v1-verified-20261026`). What remains of TROPESS is **v2, for AIRS and
CrIS-JPSS1 together** (user decision 2026-10-23): decision 5 of the CrIS
handoff, deferred on 2026-10-26. Nothing about v2 has been built, and
nothing about it is decided beyond the points below. Follow the same path:
decisions with the user, the audit, the production subset reviewed in
place, the reader at fixture level, the full fixture test, a bench,
production, finalize with sign-off on every `--apply`.

**Settled already (user):**
- v2 is **a separate `v_2` store set** (Product scheme): `wisosat.airs.v_2.fs...`
  and `wisosat.cris_jpss1.v_2.fs...`, each its own product, config, obs
  axis and stores. Its layout differs (R25), so v1 and v2 are not one
  store.
- v2 is a continuation, not a reprocessing: FS only, from 2026-06-01, where
  v1 ends 2026-05-31. No SNPP v2 exists (SNPP HDO ended 2021-05-21).

**On disk** (counted 2026-10-26; every collection complete to its cutoff
when downloaded on 2026-10-22, by the `access_tropess` codebase, not this
repo):

| product | type | folder under `raw/` | files | days | size |
| --- | --- | --- | --- | --- | --- |
| AIRS v2 FS | Summary | `AIRS/TRPSYL2HDOAIRSFS.2/` | 30 | 2026-06-01 .. 06-30 | 0.1 GB |
| AIRS v2 FS | Standard | `AIRS/TRPSDL2HDOAIRSFS.2/` | 30 | 2026-06-01 .. 06-30 | 1.5 GB |
| AIRS v2 FS | Full | `AIRS/TRPSFL2HDOAIRSFS.2/` | 30 | 2026-06-01 .. 06-30 | 19 GB |
| CrIS-JPSS1 v2 FS | Summary | `CRIS/TRPSYL2HDOCRS1FS.2/` | 139 | 2026-06-01 .. 10-17 | 0.8 GB |
| CrIS-JPSS1 v2 FS | Standard | `CRIS/TRPSDL2HDOCRS1FS.2/` | 139 | 2026-06-01 .. 10-17 | 9.8 GB |
| CrIS-JPSS1 v2 FS | Full | `CRIS/TRPSFL2HDOCRS1FS.2/` | 137 | 2026-06-01 .. 10-15 | 86 GB |

All files are R1p25, format F2p10 (`_J1` for AIRS, `_J0` for CrIS). AIRS
v2 had not advanced past June when CMR was last queried (2026-10-22). The
CrIS v2 collections are still growing upstream.

**What is known of the layout** (R25, from probes on 2026-10-23; not yet
audited over every file):
- **Standard v2** is on 34 levels and already cut at DOF >= 1.1, so it has
  the same rows as Summary v2. It adds `averaging_kernel_h2o`, five column
  fields and `air_density`. `target_id` becomes a 36-character string.
- **Summary v2** stays on 17 levels, with the same rows as Standard v2.
- **Full v2** keeps every row, on 67 forward-model and 34 retrieval levels,
  with every HDO/H2O kernel and covariance block, some as compressed int8
  bytes. It is 9-13x Standard's size per day on disk.
- In v1, by contrast, Standard kept every row and Summary was the DOF > 1.1
  subset, so the v1 stores hold every row (Summary vs Standard, v1).

**Decision 5, for the user.** Lay it out with measurements before asking:
the user decides exceptions, and wants evidence first.
1. **Which v2 type or types become products:**
   - Standard (with Summary merged, as in v1?): small, but every row has
     DOF >= 1.1, a sample TROPESS chose, so the v1/v2 seam changes the
     sample as well as the levels;
   - Full: every row, as the v1 stores. About 86 GB raw for CrIS's 137
     days, and its int8-packed blocks need new reader code and an
     independent decode in the verifier;
   - or both, as separate products (Product scheme: "a v2 Full product
     would be its own question").
2. **The variable subset:** v1's set (C3, P3) as the base, plus any of v2's
   new fields (`averaging_kernel_h2o`, the columns, `air_density`). Each
   needs a nomenclature row first, and its levels named under
   `docs/model-comparison-naming.md` (34 and 67 levels are new).
3. **When:** CrIS v2 grows each day. Build now and append later (builds
   resume from the granule index; each later append needs a verify and a
   new tag), or wait. AIRS v2 has 30 days.
4. **The v1 rules do not carry over by default.** R40 (`time_order:
   source`) and R37 (one copy of each repeated footprint) were approved for
   CrIS v1 per product, after measurement. For v2, measure and ask again:
   the user's rule is no exception without their approval (2026-10-26).
   Likewise re-check R22 (first-row `x`), R36 (`land_flag` all 1), R38
   (`sunlit_binary_mask`) and the merge's one-sided days in the audit.
5. **The v1/v2 seam:** CrIS files hold rows up to ±2 days from their date
   (finding 16), so the v1 file of 2026-05-31 and the v2 file of 06-01 may
   share footprints (as R37, but across two products). Measure it, and
   state it in both products' metadata if it occurs.

**Code that assumes v1** (`products/tropess.py`, unless named):
- `LEVELS = 17` sets the profile shapes (`ABSENT_LAYOUT`, the level-count
  check); v2 Standard has 34 levels, Full 34 and 67;
- `FILE_RE` here and in `tools/survey/tropess_file_audit.py` accepts only
  `Standard|Summary`; Full needs its own token (and `granule_types`);
- the audit tool's `PRODUCTS` has no v2 entries;
- `target_id` (a 36-character string) and Full's int8-packed blocks are
  read nowhere yet;
- the `nomenclature-key_tropess.md` rows map v1's datasets only.

**First steps in the new session:** read this section and R25; probe one
file of each v2 type (headers, row counts, levels); measure the v1/v2
seam; then lay out decision 5 for the user, as the CrIS decisions were.
The audit over every v2 file follows the decision.

### v2: answers (user, 2026-10-28) and first probes

**Answers to decision 5:**
1. **Both** Standard and Full become products.
2. **Variables:** v1's set as the base, plus v2's new fields.
3. **Build now**, and append as CrIS v2 grows.
4. **A v1 exception carries over only where the situation is the same as in
   v1.** Where the setup, or the need for the exception, differs, the user
   approves it again.
5. **The seam:** measure, then decide.

**Follow-up (user, 2026-10-28), after the probes below:** leaning to Full
only, pending the level question (R42), with the rest of that point
approved; levels to be scanned over every file and looked up online;
`altitude` to be explained (R43); v1's 19 stores plus `quality`,
`averaging_kernel_h2o` and `air_density` approved (all three are new in
v2: none is in the v1 Standard or Summary files); the seam approved (both
products' metadata state the version change and the change in sample at
2026-06-01).

**Second follow-up (user, 2026-10-28):**
- the level scan of every 10th day held (TESTING.md finding 17), so the empty levels are cut: 17 levels, as v1 (R42);
- `altitude` from Full (R43);
- the cross kernels (`hdo_hdo`, `hdo_h2o`, `h2o_hdo`) are in, with three new nomenclature rows;
- the 67-level `species` and `constraint_vector` (R44) and the int8-packed 67x67 blocks are left out (addable later as stores of their own).

**Full only (user, 2026-10-28).** v2 is one product per platform, built from the Full files: `wisosat.airs.v_2.fs.*` and `wisosat.cris_jpss1.v_2.fs.*`. Standard and Summary are not read; Standard's selection is `quality == 1` (R41), stored as its own variable.

**Probes, 2026-10-28** (login node, one file per type: 2026-06-01 for AIRS
and CrIS-JPSS1, plus 06-02 and 06-03 for repeats; v1 05-30 and 05-31 for
the seam). Scripts and output were kept in the session scratchpad only.
**One day each: the audit over every v2 file must confirm them.**

- **Standard is Full's rows with `quality == 1`, exactly** (R41), not a
  DOF cut. CrIS: 21,939 of 35,300 rows; DOF >= 1.1 alone would keep 24,818.
  AIRS: 15,679 of 37,251; DOF alone 18,642. Full rows with `quality == 0`
  reach DOF 3.05. The rows are in the same order, `target_id`s agree, and
  every shared dataset is identical on them, except:
  - `observation_error_h2o` below the surface, where both write values
    (R15) and they differ;
  - `altitude` (R43).
- **Summary is Standard's levels 0-16 on the same rows**, identical in
  every shared variable except `altitude` (R43). The five 850-250 hPa and
  `_004` fields that v1 took from Summary are in v2 Standard and Full. So
  **v2 needs no Summary merge**, unless `altitude` is taken from Summary.
- **The 34 retrieval levels are v1's 17, padded** (R42). In Standard and
  Full, every array on the retrieval grid holds values only on levels 0-16:
  `x`, `x_h2o`, `xa`, `pressure`, `observation_error_h2o`, both kernels,
  and Full's joint 34x34 blocks. The pressures are v1's 17 (1000 ..
  0.1 hPa, the surface at level 0). The exceptions:
  - Full `pressure_ret` repeats the 17-level grid in levels 17-33;
  - Standard `air_density` holds two identical 17-level copies;
  - Standard `altitude` holds two different ones (R43).
  
  Full adds the 67-level forward-model grid (`pressure_fm`, `altitude`,
  `species`, `constraint_vector`, `air_density`, and the int8-packed
  blocks).
- **Full's own fields:**
  - `quality` (0/1, the Standard selection);
  - `dofs`, identical to `signal_dof`;
  - `species`, the HDO mole fraction on 67 levels, roughly `x` x `x_h2o`
    (p50 1.0036, 0.98-1.15) despite its `standard_name`
    `molar_ratio_of_hdo_to_h2o` (R44);
  - `constraint_vector`, exactly `xa` x `h2o_constraint_vector`;
  - joint kernels `hdo_hdo`, `hdo_h2o`, `h2o_hdo`, `h2o_h2o` (each 17x17
    in a 34x34 array; `h2o_h2o` equals `averaging_kernel_h2o`; the HDO/H2O
    ratio kernel `averaging_kernel` is none of them);
  - observation-error blocks: `hdo_hdo` is symmetric with no negative
    variance; `h2o_h2o` has negative variances on almost every row;
  - the `characterization` group (QA, emissivity, cloud, columns,
    covariances);
  - 67x67 int8-packed blocks (`averaging_kernel`, three covariances, and
    the H2O/HDO ones), which need TROPESS's `tropess_compression` to read.
- **R11 holds in v2:** `observation_error` (HDO/H2O ratio) has negative
  variances on 87-100% of rows and is asymmetric on all. Same situation,
  so it stays out.
- **R22 does not occur in v2.** Row 0's `x` is not `x_test`, in Standard or
  Full, for either instrument. In AIRS Standard, `x_test` is the kernel
  applied to row 0's own `x` (to 1e-6), so row 0 is the retrieval. CrIS's
  `x_test` drops the below-surface level, so it did not line up for that
  check. Not the v1 situation, so no mask (the audit checks every file).
- **R37 (CrIS) continues in v2:** consecutive days share footprints (exact
  time, lat, lon, and CrIS indices). Standard: 17 (06-01/02) and 94
  (06-02/03); Full: 38 and 113. None two days apart. The copies differ only
  in `observation_error_h2o` below the surface, as most of v1 JPSS1's did,
  and in Standard's `altitude` (R43). `x` never differs. Same situation as
  v1. **AIRS v2 has no repeats** (none in v1 either).
- **Row order:**
  - **CrIS v2** lists 16 latitude bands, each in time order over the day:
    15 steps back of ~22-24 h, and rows up to ~14 h beyond the file's date.
    v1 JPSS1's R1p24 files (05-30, 05-31) have the same 16 bands. These are
    R40's "larger blocks", without v1's 64 s jitter. Same situation as R40.
  - **AIRS v2** interleaves granules as v1 FS does (R32): 37% of steps go
    back (v1 05-31: 40%), most by one orbit (~5,850 s). Same situation as
    R32.
- **The v1/v2 seam is clean.** No row or footprint is shared between v1's
  05-30 and 05-31 Standard and v2's 06-01 and 06-02 Standard or Full, for
  either instrument. (Corrected 2026-10-28: CrIS v2 06-01 holds one row
  dated 2026-05-31T23:59:59 UTC, the start of the store's time coverage;
  it is not in v1. AIRS v2 06-01 holds none.)
- **The sample changes at the seam anyway.** Rows per day: CrIS v1 05-31
  23,868 (every row), v2 06-01 Full 35,300 and Standard 21,939. AIRS v1
  05-31 28,289; v2 Full 37,251 and Standard 15,679. v2 retrieves more
  targets than v1, and v2 Standard drops ~40-58% of them by `quality`.
- **AIRS and CrIS share the v2 layout** of each type; only the instrument
  indices differ (CrIS adds `cris_fov` and, in Full, `cris_l1b_type`).

## v2 production subset (approved 2026-10-28)

**Built, verified and finalized 2026-10-28** (tag `v2-verified-20261028`,
44 stores; TESTING.md Tier 2f and the TROPESS v2 run log).

**Approved 2026-10-28, with Q1, Q2 and Q3 as proposed.** Drafted for the user's in-place review (`#@CLAUDE` comments), on the CrIS v1
subset below: where a point is the same as v1's, it says so and points
there. Facts are from the v2 Full audit (TESTING.md finding 18), the level
scan (finding 17) and the probes above. Decisions already made: "v2:
answers" and its follow-ups. Open questions are marked **Q**.

### V1. Products, names and provenance

- **Two products, one config each, built from the Full files only**
  (`source: tropess`, `version_product: fs`):

  | product | config | stores named | days | obs |
  | --- | --- | --- | --- | --- |
  | AIRS v2 FS | `config/airs_fs_v2/` | `wisosat.airs.v_2.fs.inst.native_swath.<variable>.zarr` | 30 (2026-06-01 .. 06-30) | 1,028,658 |
  | CrIS-JPSS1 v2 FS | `config/cris_jpss1_fs_v2/` | `wisosat.cris_jpss1.v_2.fs.inst.native_swath.<variable>.zarr` | 137 (2026-06-01 .. 10-15) | 4,676,513 (4,687,895 less R37's 11,382) |

  CrIS Full is on disk to 10-15; Standard runs to 10-17. Later days are
  appended as they are downloaded (V8).
- **Checked on every file**, as v1 (C1):
  - `ShortName` `TRPSFL2HDOAIRSFS` / `TRPSFL2HDOCRS1FS`, `VersionID` 2;
  - `Platform` `Aqua` / `JPSS-1`, `Instrument`;
  - `source` against the file name's algorithm (all R1p25, F2p10).
- **Per granule, in the index:** algorithm, format and joint flag, as v1;
  for CrIS, the rows left out under R37; `granule_source_rows`.
- **Store attributes:** as v1 (C1), plus:
  - built from Full: every retrieved target, with TROPESS's quality flag
    stored (V3). Standard v2 is exactly the `quality == 1` rows (R41);
  - why `altitude` comes from Full (R43);
  - the seam, as approved: v2 continues v1 from 2026-06-01, with no
    observation in both. The sample changes there: v2 retrieves about
    1.3-1.5x as many targets per day (CrIS v1 05-31 23,868; v2 06-01
    35,300).

### V2. Granules and sources

- **A granule is one day: one Full file.** There is no merge; Standard and
  Summary are not read. The folders are `AIRS/TRPSFL2HDOAIRSFS.2/<YYYY>/`
  and `CRIS/TRPSFL2HDOCRS1FS.2/<YYYY>/`, matched on platform token, stream
  and type `Full` (`FILE_RE` gains the type).
- **No missing days** in either span, and no two files on one date.
- **Row order: the source order** (`time_order: source`), with the repeat
  check in place of the time order (look-back 2 for CrIS, as v1). The user's
  rule, 2026-10-28: a v1 exception applies where the situation is the same.
  It is the same:
  - **AIRS** interleaves granules as v1 FS does (R32): 37% of steps go
    back, up to 23.3 h;
  - **CrIS** lists 16 latitude bands, each in time order, as v1's R1p24
    files do (R40): 15 steps back per file, up to 57.5 h. 15,769 rows fall
    before their file's date and 7,986 after (v1: up to ±2 days).
- **R37 (CrIS), the same situation, so the same rule:** each footprint is
  kept once, from the newest algorithm, then the latest
  `ProductionDateTime`.
  - 11,382 rows share time, lat and lon with the day before, and none with
    two days before.
  - 4,618 copies are identical, 6,763 differ in `observation_error_h2o`
    only, and 1 differs in two kernels. That is the v1 JPSS1 pattern.
  - The later file is the newer in all 123 pairs.
  - `expected_left_out` 11,382 through 10-15. **AIRS has none**, as in v1.

### V3. Stores

**22 stores per product, 44 in all.** v1's 19, sourced from Full, plus
three new: `quality`, `air_density` and the joint HDO/H2O kernel store.
Every profile is cut to levels 0-16 (R42, decided), so the vertical grid
is v1's 17 levels. Dims and conversions are as v1 (P3) unless stated.

| store | Full source | note |
| --- | --- | --- |
| geolocation | `time`, `latitude`, `longitude` | as v1 |
| `water_vapor_hdo_h2o_ratio` | `x[:, 0:17]` | no R22 mask: R22 does not occur in v2 |
| `water_vapor_h2o_mole_fraction_dry_air` | `x_h2o[:, 0:17]` | x 1e6 |
| the five 850-250 hPa and `_004` stores | `dd_col_p`, `dd_col_p_error`, `x_h2o_col_p`, `x_h2o_col_p_error`, `dd_004` | on every row now (v1: Summary rows only); reproduced from the profiles on every file |
| `water_vapor_hdo_h2o_ratio_degrees_of_freedom_for_signal` | `observation_ops/signal_dof` | equals `dofs` |
| `cloud_effective_optical_depth`, `cloud_top_pressure`, `temperature_surface`, `land_flag`, `day_night_flag` | `geophysical/*` | as v1; flags int32 |
| `water_vapor_hdo_h2o_ratio_apriori` | `observation_ops/xa[:, 0:17]` | |
| `water_vapor_hdo_h2o_ratio_averaging_kernel_log` | `observation_ops/averaging_kernel[:, 0:17, 0:17]` | R45 fill on some `quality` 0 rows |
| `water_vapor_h2o_mole_fraction_dry_air_observation_standard_error_log` | `observation_ops/observation_error_h2o[:, 0:17]` | as v1 (R8, R12, R15) |
| `pressure` | `pressure_ret[:, 0:17]` | 17-33 must equal 0-16 |
| `altitude` | `altitude` at the level of `pressure_fm` equal to each `pressure_ret` | R43; found exactly once on every written level (audit) |
| `quality_flags_retrieval` *(new store; row exists)* | `quality` | int32; 1 good, 0 bad. Standard's selection (R41); DOF > 1.1 on every 1 |
| `air_molar_density` (Q2) *(new row)* | `retrieval/air_density[:, 0:17]` / N_A | mol m-3. 17-33 must equal 0-16, and 34-66 must be fill. Equals Standard's mol m-3 values (finding 17) |
| `water_vapor_hdo_and_h2o_mole_fraction_dry_air_averaging_kernel_log` *(new store; rows exist, TES)* | four arrays, each `[:, 0:17, 0:17]`: `hdo_hdo_averaging_kernel` → `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log`; `hdo_h2o_averaging_kernel` → `..._hdo_..._log_cross_h2o`; `h2o_hdo_averaging_kernel` → `..._h2o_..._log_cross_hdo`; `h2o_h2o_averaging_kernel` → `water_vapor_h2o_mole_fraction_dry_air_averaging_kernel_log` | one store per matrix (N18). Rows retrieved, columns true: the ratio kernel equals `hdo_hdo` - `h2o_hdo` to 1e-6 (finding 18). (obs, level, level_2) |

- **Q1, decided (user, 2026-10-28): stored once, as the joint store's H2O block. `averaging_kernel_h2o`:** approved as a store of its own, but it
  equals the `h2o_h2o` block on every row. Under N18 it is the H2O block of
  the joint kernel store, not a separate store. **Proposed:** store it once,
  as that block.
- **Q2, decided (user, 2026-10-28): `air_molar_density`, mol m-3, no `standard_name` (option b). `air_density`:** it needs a nomenclature row. The files say "Density
  of air" (Standard) and "number density of air" (Full). They do not say
  dry or total air, and the values cannot settle it (the difference is
  under ~2%).
  - **Proposed:** the name `air_molar_density`, unit `mol m-3`,
    "molar density of air (moles of air per cubic metre) at each level", with
    the basis stated as unknown in the metadata.
  - The source `standard_name` `air_number_density` is CF's for m-3 and
    does not fit mol m-3, so retaining it would mislabel the store. Options:
    (a) retain it anyway (the rule); (b) leave it off (an exception);
    (c) store molecules m-3 under it. **Proposed: (b).**
- **Q3, decided (user, 2026-10-28): retained as published, noted in each `comment`. Retained `standard_name`s that are not CF:** Full gives `quality`
  the `standard_name` `quality`, and `cloud_top_pressure` the
  `standard_name` `cloud_top_pressure`. v1's cloud-top store retained
  Standard's `air_pressure_at_cloud_top`. The rule retains a source
  `standard_name` unchanged, so v2's cloud-top store would carry a
  different one from v1's. **Proposed:** keep the rule (retain as
  published), and say so in each store's `comment`.
- **Levels (R42, decided):** the build and the verifier fail on any value
  in levels 17-33 of a stored array, except the declared copies
  (`pressure_ret`, `air_density`), which must equal 0-16;
  `air_density` 34-66 must be fill. Declared in config.
- **Flags:**
  - `day_night_flag` is `sunlit_binary_mask` in every v2 file, so no R38
    declaration is needed;
  - no file has `land_flag` 1 on every row, so there is no R36 mask. The
    verifier's check for such a file (C3, Q1) stays.
- **Always out:**
  - as v1: `observation_error` (R11), `x_test`, `target_id`, `x_raw` and
    `x_h2o_raw`, `year_fraction`, the microwindows, `datetime_utc`;
  - and now:
    - the Standard and Summary files;
    - Standard's `altitude` (R43);
    - the 67-level `species`, `constraint_vector`, `h2o_species` and
      `h2o_constraint_vector` (R44);
    - `dofs` (equals `signal_dof`);
    - the `characterization` group;
    - the int8-packed 67x67 blocks;
    - the 17x17 observation-error blocks (`h2o_h2o` has negative
      variances on almost every row, R11's defect).

### V4. Time

As v1 (C4): TAI93 less the leap seconds (10 throughout), checked against
`datetime_utc` on every row (no mismatch in the audit), stored in seconds.

### V5. Declared, never detected

- **R37 (CrIS):** the repeat rule and `expected_left_out` (11,382 through
  10-15).
- **R42:** the level cut, with the two declared copies.
- **R43:** `altitude` from the forward-model grid at the retrieval
  pressures.
- No R18, R22, R36 or R38 declarations: none occurs in v2.

### V6. Filtering guidance in the metadata

As v1 (C6), plus:
- **`quality == 1` is TROPESS's selection**: it reproduces the v2 Standard
  product exactly (R41), and every such row has DOF > 1.1. `quality` 0 rows
  reach DOF 4.19 (CrIS) and 2.63 (AIRS).
- **R45:** on some `quality` 0 rows the ratio kernel is fill at its lowest
  levels.
- **Sarkar et al. (2026)** used v1 only (DOF >= 1, COD <= 0.5).

### V7. Chunks and compression

As v1 (C7): the same chunk rule, and blosc zstd 5 + shuffle on the 2-D
arrays. That means the ratio kernel and the joint kernel store's four
arrays; default compression elsewhere. Uncompressed sizes:
- CrIS: ratio kernel ~5.4 GB, joint kernel store ~21.7 GB, each 17-level
  store ~0.32 GB;
- AIRS: ~1.2 GB and ~4.8 GB.

`granules_per_commit` about 1.3 M obs per commit: AIRS 30 (one commit),
CrIS 30 (~5).

### V8. Next, after review

1. **The `air_density` row** (Q2) in style_guides, shown to the user before
   commit.
2. **Shared change: multi-array variable stores (N18).** The joint kernel
   store is the first; TES and IASI need it too. Fixture test of every
   product after it.
3. **The reader's v2 mode**, each piece tested:
   - the `Full` type in `FILE_RE` and the listing;
   - Full-only granules;
   - the level cut with its declared copies;
   - `altitude` at the retrieval pressures;
   - `air_density` / N_A;
   - `quality`;
   - the four kernel blocks;
   - `LEVELS` taken from config, not 17 fixed (v1 keeps 17);
   - the key's rows for the v2 sources.
4. **Configs and fixtures:** AIRS three days, and CrIS with an R37 repeat
   (06-01 .. 06-03), cut small.
5. The full fixture test, a bench (a week of each), production, then
   finalize with sign-off on every `--apply`.
6. **Appending later days** (decision 3): each append is a build that
   resumes, then a verify and a new tag. For CrIS the R37 count is
   re-declared first: a later day adds repeats with the previous one.

### V9. Code design (for review, 2026-10-28)

Step 1 is done: `air_molar_density` is in style_guides `4711fe4`. What
the code does today, and what v2 needs:
- **One key per source.** The config's `source` picks the reader and the
  key. v2 maps some canonical names onto different source datasets than v1
  (`pressure` comes from `pressure_ret`, `altitude` from the forward-model
  grid), so one key cannot serve both.
- **Several arrays in one store already works.** The geolocation store is
  one: `store_sources` returns one source per array, and the build, the
  verifier and per-array compression all loop over it.
- **The verifier reads every source whole** with h5py and applies only
  fill and the unit factor. v2's stores are not whole sources: they are cut
  to 17 levels, and `altitude` is picked from another grid.

**D1. A v2 reader and key: `products/tropess_v2.py` and
`nomenclature-key_tropess_v2.md`, with `source: tropess_v2`.**
- The reader imports what v1 and v2 share from `products/tropess.py`:
  the listing (with the `Full` type), time decoding and header checks, and
  the R37 selection. It has no merge.
- The v1 reader and key are left as they are, so the finalized v1 stores
  can still be re-verified.
- No new config key: "`source` picks the reader and key" still holds.
- *Alternative:* a `nomenclature_key` override in config. That is a shared
  change at ~15 call sites, for one product.

**D2, decided (user, 2026-10-28): general source slices, a shared change
shaped for TES as well.**
- **Slices are written in the key's `original_variable_name`**, numpy style
  with `:` for the obs axis: `x[:, 0:17]` here, and `ConstraintVector[17:34]`
  or `AveragingKernel[0:17, 17:34]` for TES (`tes.md`, E1).
  - The key's uniqueness rule becomes one canonical name per source
    *slice*, so one source can feed several stores.
  - The build slices the reader's array; the verifier slices raw on its
    own.
- **The config declares what the slices leave out** (`source_remainders`,
  per source path): a range on an axis that must be `empty` (fill or NaN),
  or `equal` to another range (v2 `pressure_ret` and `air_density` 17-33;
  TES `Pressure`).
  - The key's slices plus the declared remainders must cover every value
    of the source, or the config is refused.
  - A remainder that breaks its rule fails the build and the verifier.
- **A lookup onto another grid** (`level_lookups`, for v2 `altitude`): the
  value at the forward-model level whose pressure equals each retrieval
  pressure, found exactly once per written level.
- **Other products are unaffected:** no current config declares any of
  this, so their code path is unchanged; the fixture test of every product
  confirms it. IASI's proxy split (`musica_wvp_apriori[:, 0]`) fits the
  same slice form; its rank padding is a separate need.

**D3. Matrix stores (N18), a shared change.**
- **The key:** a "Matrix Store Key" table gives the store's canonical name
  (it has a nomenclature row), its arrays in order (each a variable row),
  and the store's long name.
- **The config** lists the store's name in `variables`. It fails if one of
  the store's arrays is also listed as a store of its own.
- **The code:** `store_sources` returns the store's arrays. The build, the
  verifier and per-array compression need no change beyond that, since
  geolocation is the precedent. The store gains an attribute naming its
  arrays and the matrix they form.
- **Tests:** the TROPESS v2 fixtures exercise it, and `test_pipeline.py`
  gains cases for a malformed table and an array listed twice.

**D4. The key rows** for v2 (`nomenclature-key_tropess_v2.md`):
- the v1 rows, with v2's source paths;
- `quality` → `quality_flags_retrieval` (a quality flag, so the config
  must list it);
- `retrieval/air_density` → `air_molar_density`, `x 1 / N_A`;
- the four kernel blocks.

Then the configs, fixtures, the full fixture test of every product, and the
bench (V8, steps 4 and 5).

**Done 2026-10-28 (V8 steps 1-4):**
- the `air_molar_density` row (style_guides `4711fe4`);
- the shared changes D2 and D3, plus `withheld_standard_names` (Q2's
  exception, declared);
- the v2 reader and key (D1, D4), with `retrieval/air_density`'s axis
  renamed to `level` (Full declares it on `level_fm`; R42);
- `config/airs_fs_v2/` and `config/cris_jpss1_fs_v2/`. The R37 count, from
  the reader's rule over every file, is 11,382, as the audit found;
- the fixtures: 2026-06-01, 02 and 04 of each, cut, without the packed
  blocks; 03 is a declared gap; CrIS keeps 38 repeats.

Both v2 fixtures pass every case, new ones included: a wrong remainder fails
both the build and the verifier from raw; an uncovered slice, a lookup off
its grid, a matrix array listed twice and a stray withheld name are refused.
The verifier now tallies a declared fill over the whole source as read
(R42's padding holds `observation_error_h2o`'s -999, which levels 0-16 never
do).

## CrIS: handoff (written 2026-10-23, for a new session)

AIRS v1 is finished; CrIS is the user's next task (chosen 2026-10-22: CrIS
once AIRS is finalized). Nothing about CrIS has been built. Follow the AIRS
path: decisions with the user, then the audit, the production subset
reviewed in place, the reader at fixture level, the full fixture test, a
bench, production, and finalize with sign-off on every `--apply` (CLAUDE.md;
STATE.md, How we work).

**Settled already (user):**
- one product per platform, stream and collection version, each its own
  config, obs axis and stores (Product scheme). Product tokens `cris_snpp`
  and `cris_jpss1`, with `source: tropess`, so the stores are
  `wisosat.cris_snpp.v_1.rs...`, `wisosat.cris_jpss1.v_1.fs...` and so on;
- Summary merged into Standard per day, R22 masked as declared, rows in
  source order with the repeat check (style-guide exception, style_guides
  `43b6b51`), RS and FS kept separate. All were decided for TROPESS, not for
  AIRS alone, but confirm each carries over before building;
- AIRS v2 (30 days, 2026-06) is designed together with CrIS-JPSS1 v2 (138
  days); v2's layout differs (R25) and is a separate `v_2` store set.

**On disk** (`raw/CRIS/`; every collection complete to its cutoff,
`~/work/data_access/access_tropess/HANDBACK.md`). Measured 2026-10-23 on one
file each: `Platform` is `SUOMI-NPP` or `JPSS-1`, `Instrument` `CrIS`, 17
levels in v1, and the variables are AIRS's apart from the instrument's own
geolocation (`cris_atrack`, `cris_xtrack`, `cris_fov`, `cris_granule`,
`cris_view_ang`), which AIRS does not store. So the AIRS 18-variable subset
(P3) should carry over; confirm with the user.

| candidate product | collections | days | note |
| --- | --- | --- | --- |
| `cris_snpp` v1 RS | `TRPSYL2HDOCRSRS_1-20240923_230130/` (flat) | 1,865, 2015-12-01 .. 2021-05-21 | **Summary only**: there is no RS Standard collection upstream |
| `cris_snpp` v1 FS | `TRPSDL2HDOCRSFS.1/`, `TRPSYL2HDOCRSFS.1/` | 110, 2021-02-01 .. 05-21 | R1p11, R1p12; overlaps SNPP RS (R26) and JPSS1 FS |
| `cris_jpss1` v1 FS | `TRPSDL2HDOCRS1FS_1-20240912_023602/` (flat) and `TRPSDL2HDOCRS1FS.1/`; `TRPSYL2HDOCRS1FS.1/` | 1,887, 2021-04-01 .. 2026-05-31 | R1p12 .. R1p24; the backfill duplicates (R18) |
| `cris_jpss1` v2 FS | `TRPS{D,Y,F}L2HDOCRS1FS.2/` | 138, 2026-06-01 .. 10-16 | with AIRS v2; layout R25; Full 85.8 GB |
| `cris_snpp` SC (Australian fires) | `TRPSDL2HDOCRSAUS.1/` | 91, 2019-11 .. 2020-01 | Standard only, R1p9, stream token `SC_AUS`; in or out? |

**Decisions for the user, before code:**
1. **SNPP RS has no Standard upstream.** A Summary-only product would have
   only DOF > 1.1 rows and no kernel, prior or errors. Build it as
   Summary-only (the reader's obs axis becomes Summary's rows), or leave it
   out? Sarkar et al. (2026) list CrIS 2016-2024 from "Summary products and
   standard products" without naming collections; before 2021 only this RS
   Summary exists, so it is likely theirs (inferred).
2. **SNPP FS** (110 days) overlaps SNPP RS on the same targets (R26) and
   JPSS1 FS (7 weeks). Its own product, or left out?
3. **R18:** where two JPSS1 FS Standard files exist for one date (5 dates,
   an old name and an R1p24 backfill), which to keep? The listing refuses
   two files per date today; whichever is chosen should be declared in
   config (declared, never detected), with the other file checked.
4. **SC Australian fires:** in or out (CLAUDE.md lists SC as out of the
   initial scope only by omission)?
5. **v2**, for AIRS and CrIS-JPSS1 together: Standard on 34 levels cut at
   DOF >= 1.1 vs Full with every row (R25); which, and with what subset.

**Answers (user, 2026-10-26):**
- **2. SNPP FS is its own product**, `cris_snpp` v1 FS, as AIRS's streams
  are.
- **3. R18: the R1p24 replacement is kept** on each of the 5 dates; the old
  file is declared and checked.
- **4. The SC Australian-fires collection is left out.**
- **1. SNPP RS is built as a Summary-only product**, `cris_snpp` v1 RS:
  its obs axis is the Summary's rows (DOF > 1.1 only), with no kernel,
  prior or error stores, and its metadata says so. Decided after a
  re-check against the raw files and CMR (2026-10-26), at the user's
  request:
  - all 1,865 files in `TRPSYL2HDOCRSRS_1-20240923_230130/` are Summary:
    `ShortName` `TRPSYL2HDOCRSRS`, `VersionID` 1, `Platform` `SUOMI-NPP`,
    R1p17 F0p8_J0, one per date, 2015-12-01 .. 2021-05-21;
  - **134 dates in that span have no file.** CMR lists 1,865 granules, so
    they are upstream gaps, not download gaps (R35);
  - CMR lists 16 TROPESS HDO collections (live query 2026-10-26), the same
    16 as the download's 2026-10-22 query, and **no `TRPSDL2HDOCRSRS`**.
    The granule counts are unchanged too (SNPP RS 1,865, SNPP FS 110 + 110,
    JPSS1 FS v1 1,887 + 1,887);
  - the Summary holds no kernel (`averaging_kernel`), prior (`xa`),
    `observation_error*`, `signal_dof`, `x_test`, `surface_temperature`,
    `cloud_top_pressure` or `average_cloud_eod`; it adds `dd_004`,
    `dd_col_p(_error)`, `x_h2o_col_p(_error)`, `target_id` and the
    microwindows;
  - **the DOF > 1.1 cut holds for CrIS:** on SNPP FS 2021-03-01 and
    2021-05-15, the Summary rows are exactly the Standard rows with
    `signal_dof` > 1.1 (6,498 of 18,788; 12,513 of 26,303), matched on time,
    lat and lon. SNPP RS Summary has no Standard to compare with, so the cut
    is inferred there.

**Reader changes known to be needed** (`products/tropess.py`):
- **Filter by instrument:** `list_granules` selects folders by stream and
  collection only; under `raw/CRIS` the SNPP and JPSS1 FS v1 folders both
  match, and every overlapping day would fail as "two Standard files". Match
  the folder's `instrument` group (`CRS` vs `CRS1`) to the config, e.g. from
  `platform` or a new listing option.
- **Summary-only granules** (decision 1): a product with no Standard
  folders reads Summary files alone; today a missing Standard file is
  allowed only on declared one-sided days.
- **Declared duplicate files** (R18): keep the R1p24 replacement, declare
  the old file and check it.
- **`FILE_RE`** accepts only `RS|FS`; the `SC_AUS` files are skipped
  silently, which is right now that decision 4 is out. The skip should
  still be stated in config rather than left silent.
- **The audit script** `tools/survey/tropess_file_audit.py` is generalised
  (2026-10-26): `--products` names entries of `PRODUCTS`, files are matched
  on the platform token, every file of an R18 day is audited, and every
  dataset's `standard_name`, `long_name`, `units` and `_FillValue` is
  scanned for change. A 4-day probe ran clean. Next: run it on every CrIS
  v1 file (develop job, ~1 core-hour for AIRS).

**Lessons from AIRS to apply up front:**
- **Scan every file's variable attributes for changes over the record**
  (`standard_name`, `units`, `long_name`) in the audit. R33
  (`day_night_flag`'s `standard_name`, renamed mid-FS) reached production
  because neither the fixture nor the bench month held an early file; it
  cost a rebuild and two re-verifies. A declared `standard_name` must be
  one the source uses (the verifier checks it).
- Choose the fixture and bench days to span the algorithm versions, the
  folder layouts (flat and per-year) and one-sided days.
- Seams between FS days overlap in time (R32): the repeat check covers
  them, so expect `time_order: source`.
- Fill values must occur in the record to be declared (the verifier fails
  otherwise): take them from the audit, and the bench config's from the
  bench month (`validation/stage_bench_tropess.py` reports them).
- Compression: blosc on the 2-D arrays, default on `pressure` (Tier 2d);
  re-measure only if CrIS differs.
- The fixture test now takes ~12 min (the AIRS fixtures ~5 of it); CrIS
  fixtures should be cut small, as the AIRS FS one is (400 rows).
- `qstat` may not list a job id for some seconds after `qsub`; a wait loop
  must not treat "not listed" as "finished" on its first check.

## CrIS v1 production subset (approved 2026-10-26)

Drafted for the user's in-place review, on the AIRS v1 subset below: where a
point is the same as AIRS's, it says so and points there. **Approved
2026-10-26**, with Q1 yes and Q2 as proposed. Facts are from the full CrIS audit (TESTING.md finding 16) and the
R37 probes. Decisions already made: the CrIS handoff's Answers, R36, R37,
R38. Open questions are marked **Q**.

### C1. Products, names and provenance

- **Three products, one config each** (`config/cris_snpp_rs/`,
  `config/cris_snpp_fs/`, `config/cris_jpss1_fs/`; `source: tropess`,
  `version_product: rs` or `fs`):

  | product | `product` | stores named | days (span) | obs |
  | --- | --- | --- | --- | --- |
  | SNPP RS | `cris_snpp` | `wisosat.cris_snpp.v_1.rs.inst.native_swath.<variable>.zarr` | 1,865 (2015-12-01 .. 2021-05-21; 134 missing, R35) | 2,597,674 (Summary only) |
  | SNPP FS | `cris_snpp` | `wisosat.cris_snpp.v_1.fs.inst.native_swath.<variable>.zarr` | 110 (2021-02-01 .. 2021-05-21; none missing) | 2,858,343 |
  | JPSS1 FS | `cris_jpss1` | `wisosat.cris_jpss1.v_1.fs.inst.native_swath.<variable>.zarr` | 1,887 (2021-04-01 .. 2026-05-31; none missing) | 47,391,889 |

  The obs are the audit's rows less the rows R37 leaves out, measured with
  the reader's rule over every file (2026-10-26) and declared in each config
  (`expected_left_out`): SNPP RS 620 (on 417 days), SNPP FS 8,057 (106),
  JPSS1 136,707 (1,765). JPSS1's is 16 below its 136,723 repeat pairs: a
  footprint in three files is three pairs but two rows left out.
- **The checked version** is `v_1.rs` or `v_1.fs`, from `ShortName` and
  `VersionID` as for AIRS (P1). `ShortName`s: SNPP RS `TRPSYL2HDOCRSRS`;
  SNPP FS `TRPS{D,Y}L2HDOCRSFS`; JPSS1 `TRPS{D,Y}L2HDOCRS1FS`.
- **The platform is checked on every file** (the reader's `PLATFORM_ATTR`,
  as GOSAT-2's): `Platform` `SUOMI-NPP` or `JPSS-1`, and `Instrument` `CrIS`.
- **Per granule, in the granule index:** algorithm, format and joint flag of
  each file, as AIRS (P1); and, new, **the rows left out under R37** per
  granule. `granule_source_rows` keeps each file's own count.
- **Store attributes:** as AIRS (P1), plus:
  - SNPP RS: that it is the Summary product only (DOF > 1.1, no kernel,
    prior or errors), because no RS Standard exists upstream;
  - the R36 mask, the R37 rule with its counts, and R18 (which old files
    were superseded);
  - the overlaps, as pointers: SNPP RS and SNPP FS retrieve the same targets
    over 2021-02-01 .. 05-21 (R26); SNPP FS and JPSS1 FS overlap
    2021-04-01 .. 05-21 (two satellites). R37 applies within a product only,
    so these overlaps are kept.

### C2. Granules and sources

- **A granule is one day**, as AIRS (P2). The folders:

  | product | Standard | Summary |
  | --- | --- | --- |
  | SNPP RS | none upstream | `CRIS/TRPSYL2HDOCRSRS_1-20240923_230130/` |
  | SNPP FS | `CRIS/TRPSDL2HDOCRSFS.1/<YYYY>/` | `CRIS/TRPSYL2HDOCRSFS.1/<YYYY>/` |
  | JPSS1 FS | `CRIS/TRPSDL2HDOCRS1FS_1-20240912_023602/` and `CRIS/TRPSDL2HDOCRS1FS.1/<YYYY>/` | `CRIS/TRPSYL2HDOCRS1FS.1/<YYYY>/` |

  - **Files are matched on the platform token** (`CrIS-SNPP`, `CrIS-JPSS1`)
    and stream as well as the type, so the SNPP and JPSS1 folders never mix.
  - `SC_AUS` files (out of scope) are skipped by name, stated in config.
- **SNPP RS is Summary only:** its granule is one Summary file, and its obs
  axis is the Summary rows. A config key declares the product Summary-only;
  the reader refuses a Standard file for it.
- **R18, declared:** JPSS1 2021-05-21, 2022-03-08, 2022-08-13, 2023-12-27 and
  2024-08-21 each have an old file and an R1p24 replacement. The config
  lists the 5 old files as superseded; the reader confirms each replacement
  exists, has a newer algorithm and a later `ProductionDateTime`, and reads
  only the replacement. Any other date with two files of one type fails, as
  today.
- **One-sided days:** none in SNPP FS or JPSS1 (every day has both files).
- **Missing days** declared: SNPP RS 134 (R35: 2015-12-05, 2015-12-30 ..
  2016-01-01, 2017-12-24, 2019-02-17, 2019-03-27 .. 2019-07-31, 2021-01-14);
  none in the FS products.
- **Row order: the source order** (`time_order: source`), approved for
  CrIS by the user 2026-10-26 (R40, option 1; not carried over from AIRS
  without asking). Day edges, a 64 s jitter and, in JPSS1, some blocks put
  rows out of time order; the index records each day's earliest and latest
  time.
- **R37, decided:** each repeated footprint stored once, newest algorithm
  then latest `ProductionDateTime`; look-back 2 files, look-ahead 2 files
  (`docs/cris-repeats-r37.md`, Decision). `check_repeats` runs on the stored
  rows with a look-back of 2 and must find none.

### C3. Stores

**SNPP FS and JPSS1 FS: AIRS's 19 stores, unchanged** (P3): geolocation; `x`
and `x_h2o`; the five merged from Summary; DOF and COD; the four Sarkar
outputs; the a priori, kernel and H2O error; `pressure` and `altitude`. Every
nomenclature row exists (style_guides `f18168e`); none is new. The CrIS
files carry the same attributes as AIRS's (checked 2026-10-26 on SNPP RS,
SNPP FS R1p11, JPSS1 R1p12 and R1p24): `x`'s comment "HDO / H2O ratio
(includes bias correction)", the same `source`s, and Summary `x_h2o`'s
`standard_name` `dry_atmosphere_volume_mixing_ratio_of_water_vapor`, so the
bias-correction comments and retained `standard_name` carry over (P3).

**SNPP RS: 12 stores**, the ones Summary holds:

| store | from |
| --- | --- |
| geolocation | `time`, `latitude`, `longitude` |
| `water_vapor_hdo_h2o_ratio`, `water_vapor_h2o_mole_fraction_dry_air` | `x`, `x_h2o` |
| the five 850-250 hPa and `_004` fields | `dd_col_p`, `dd_col_p_error`, `x_h2o_col_p`, `x_h2o_col_p_error`, `dd_004` |
| `land_flag`, `day_night_flag` | `geophysical/*` |
| `pressure`, `altitude` | `pressure`, `altitude` |

No DOF, COD, cloud top, surface temperature, a priori, kernel or H2O error:
Summary has none. R22 does not apply (Summary's row 0 is the retrieval, and
there is no `x_test` to confirm against).

**Flags:**
- **`land_flag`, R36 (decided):** masked to fill on the 324 declared files
  (SNPP FS all 110; JPSS1 2021-04-01 .. 10-31 and 2021-11-10). The config
  lists them; the reader and the verifier each confirm every row of each is
  1 before masking. **Q1, decided (user, 2026-10-26): yes**, the verifier
  also fails on an *undeclared* file whose `land_flag` is 1 on every row (a
  check, not an action, so "declared, never detected" holds).
- **`day_night_flag`, R38 (decided):** the store carries
  `sunlit_binary_mask`, declared in config, the old name in its `comment`.
  It covers more than JPSS1's early files: **SNPP FS Standard says
  `day_binary_mask` in all 110 files** while its Summary files say
  `sunlit_binary_mask`; SNPP RS says `sunlit_binary_mask` throughout. So all
  three products declare `sunlit_binary_mask`, which every product's files
  use somewhere.

**Q2, decided (user, 2026-10-26): left out, as proposed. The CrIS instrument indices** (`cris_atrack`, `cris_xtrack`,
`cris_fov`, `cris_granule`, `cris_view_ang`; present in every file). AIRS
left its four out because no row was left out, so an obs's position and the
granule index give its source row (P3, Q4). Under R37 rows are left out, so
that no longer holds. Options:
- **leave them out** (chosen): the R37 rule is deterministic from raw and
  declared, and the index records the rows left out per granule, so a source
  row can still be found; no new nomenclature rows;
- store a source-row store (the row's index in its file), as TROPOMI's
  `scanline_index` / `ground_pixel_index` serve: one new row;
- store the five indices: five new rows.

**Always out**, as AIRS: `observation_error` (R11), `x_test` (R21),
`target_id` (and it is not unique in practice, R37), `x_raw` / `x_h2o_raw`,
`year_fraction`, the microwindows, `datetime_utc` (used only to check
`time`).

That makes **50 stores**: SNPP RS 12, SNPP FS 19, JPSS1 FS 19.

### C4. Time

As AIRS (P4): TAI93 less the leap seconds from the pinned table (9 to 10 at
2017-01-01 in SNPP RS), checked against `datetime_utc` on every row (the
audit found no mismatch); stored in seconds.

### C5. Declared, never detected

- **R18:** the 5 superseded old files (C2).
- **R22:** row 0 of every Standard file (SNPP FS, JPSS1), as AIRS.
- **R36:** the 324 `land_flag` files (C3).
- **R37:** the repeat rule, with the exact counts per product once measured.
- **R38:** `sunlit_binary_mask`.
- **The Summary merge** on every day with both files (SNPP FS, JPSS1), as
  AIRS; the audit found it exact on all 1,997.
- **Missing days** (R35, SNPP RS only), and SNPP RS declared Summary-only.

### C6. Filtering guidance in the metadata

As AIRS (P6), plus:
- **Sarkar et al. (2026)** gridded CrIS from Summary before 2021 (SNPP RS,
  2015-12 .. 2021-05) and Standard after (JPSS1, 2021-04 .. 2024-09) with
  DOF >= 1 and COD <= 0.5. Their scripts very likely counted the R37
  repeats twice and read the old R18 files.
- **SNPP RS** is pre-filtered (DOF > 1.1; R31 holds for CrIS, checked on the
  merge days).
- **R36** masks `land_flag` on early files; anyone filtering on land/ocean
  before 2021-11 has no flag there.

### C7. Chunks and compression

As AIRS (P7): the same chunk rule (scalars 4,194,304 obs, profiles 524,288,
kernel 32,768) and blosc zstd 5 + shuffle on the six 2-D arrays, default
elsewhere. Sizes uncompressed: JPSS1 kernel ~54.8 GB (1,447 chunks), each
JPSS1 17-level store ~3.2 GB; SNPP FS kernel ~3.3 GB; SNPP RS profiles
~0.18 GB each. Re-measure compression only if the bench differs from AIRS's.
`granules_per_commit`, ~1.3 M obs per commit: SNPP RS 1,000 days (2
commits), SNPP FS 50 (3), JPSS1 50 (~38).

### C8. Next, after review

1. **No nomenclature rows** (Q2 adds none).
2. **The reader and shared changes**, each tested (**done 2026-10-26**: the
   fixture test passes 350 cases over 9 fixtures, the three CrIS ones
   included; SNPP RS needs `time_order: source` too, as 1,347 of its seams
   step back in time):
   - the instrument filter and Summary-only products (C2);
   - superseded files (R18);
   - whole-file declared masks (R36), with Q1's check;
   - the R37 rule: look-ahead in the build, the selection in the verifier,
     per-granule counts in the index, look-back 2 in `check_repeats`;
   - `sunlit_binary_mask` declared for all three (R38). SNPP FS's Standard
     files never use it, only its Summary files, so the verifier's check
     (a declared `standard_name` must be one the source uses) must see the
     Summary file's attribute; the SNPP FS fixture tests that.
3. **Done 2026-10-26: the exact R37 counts** (C1), from a dry pass of the selection over every
   file (light: time, lat, lon and attributes only), then declared.
4. **Done 2026-10-26: fixtures** (`validation/stage_tropess.py`), cut small
   (~100-300 rows a file, the last 20 rows kept so seams step back) and
   chosen to span: SNPP RS with a
   repeat and a leap second; SNPP FS with the R36 defect and a repeat;
   JPSS1 with an R18 date, the R36 boundary (2021-10-31 / 11-01), an
   algorithm-change repeat and a lag-2 repeat (2023-09-28 .. 30).
5. The full fixture test (done), a bench (**done 2026-10-26**, TESTING.md
   Tier 2e: 0 failures on all three), production (**built and verified
   2026-10-26**, 0 failures on all three; TESTING.md, CrIS v1 run log),
   finalize (**done 2026-10-26**, tag `v1-verified-20261026`).

## AIRS v1 production subset (reviewed 2026-10-23)

Drafted for the user's in-place review (`#@CLAUDE` comments), as
`sciamachy.md`'s P1-P6. **Approved 2026-10-23**, including Q1, Q3 and Q4 as
proposed, Q2c as the user named it, and Q2b (`column` dropped). A
full-record audit (P8) follows and may revise the facts here.

### P1. Products, names and provenance

- **Two products, one config each** (`config/airs_rs/config_zarr.yaml`,
  `config/airs_fs/config_zarr.yaml`; `product: airs`, `source: tropess`,
  `version_product: rs` or `fs`):

  | product | stores named | days (span) | obs |
  | --- | --- | --- | --- |
  | RS | `wisosat.airs.v_1.rs.inst.native_swath.<variable>.zarr` | 6,363 (2002-08-30 .. 2020-03-31; 61 missing) | 17,109,546 |
  | FS | `wisosat.airs.v_1.fs.inst.native_swath.<variable>.zarr` | 1,820 (2021-02-01 .. 2026-05-31; 126 missing) | 47,882,856 |

  The obs counts are Standard's rows plus the rows of Summary-only days (R23):
  RS 1,588, FS 53,455.
- **The checked version** is `v_1.rs` or `v_1.fs`. The reader derives it from
  each file's `ShortName` and `VersionID` (Standard `TRPSDL2HDOAIRS{ORS,FS}`,
  Summary `TRPSYL2HDOAIRS{ORS,FS}`, `VersionID` 1). Every file must match the
  config.
- **Per granule, in the granule index** (approved 2026-10-22; shared change):
  the algorithm (`R1pNN`), format (`F0pN`) and joint flag of each of the
  granule's two files. Both file names go in `granule_file`. As built:
  `granule_algorithm` (e.g. `R1p17; R1p17`) and `granule_format`
  (`F0p4; F0p4`, with `_J0`/`_J1` appended where the name has a joint flag),
  in `granule_file` order (the reader's `INDEX_EXTRA`).
- **Store attributes:**
  - both collections (`ShortName`, version, DOI);
  - the span of each algorithm version;
  - the Summary merge (Product scheme);
  - the declared defect (R22);
  - the pointer to the other stream, and the seam (Product scheme).

### P2. Granules and sources

- **A granule is one day**, from the files below. `*_target.nc` (R5) and
  `AIRS_TROPESS_gridded_*` (R6) are skipped.
- **Efficiency** (the user's question, answered 2026-10-23): one granule per
  day costs neither compute nor read speed.
  - **Commits are set separately.** The build reads granules in batches of
    `granules_per_commit` and writes each batch as one commit (P7).
  - **Chunks are fixed by observation count**, so how a finished store reads
    does not depend on the granule.
  - **Reading is cheap.** Granules are read in a process pool with the next
    batch prefetched, so opening two files per day (~0.35 s each on Lustre)
    is hidden.
  - **The granule is the provenance unit:** one granule-index entry per day
    (RS 6,363, FS 1,820), as the style guide requires. A larger granule (a
    month) would lose that and gain nothing.

  | product | Standard | Summary |
  | --- | --- | --- |
  | RS | `TRPSDL2HDOAIRSORS.1/<YYYY>/` | `TRPSYL2HDOAIRSORS_1-20240806_185241/` |
  | FS | `TRPSDL2HDOAIRSFS_1-20240912_174250/` and `TRPSDL2HDOAIRSFS.1/<YYYY>/` | `TRPSYL2HDOAIRSFS.1/<YYYY>/` |

  The reader fails if a date has two files of one type.
- **One-sided days (R23), Q1: keep every row** (approved 2026-10-23).
  - **Standard only** (RS 2, FS 6 days): the five Summary fields are NaN.
  - **Summary only** (RS 1, FS 5 days; 55,043 rows): the Standard-only
    fields are NaN. These are the kernel, prior, errors, DOF and cloud. It
    also includes `x` row 0's defect check, which needs Standard.

  The alternative is to leave Summary-only days out, which would drop
  observations.
- **Missing days** are declared (`expected_missing_days`): RS 61 and FS 126,
  all upstream gaps (CMR, 2026-10-22).
- **Row order: the source order is kept (user decision 2026-10-23), so `time`
  is not monotonic.** TROPESS files are not in time order (R32), so the style
  guide's two rules conflict: keep the source order, and `time` never
  decreases. The style guide gains an exception for sources not in time
  order (drafted 2026-10-23, for review).
  - Each day stays one contiguous granule, its rows as published.
  - The granule index records each day's earliest and latest time.
  - The stores' metadata says `time` is not monotonic.
  - Sorting within each day was the alternative (with a new store of source
    row positions). It would still leave `time` decreasing at 175 FS day
    seams.

### P3. Stores

Rows marked *new* need adding to `nomenclature_data.md` (reviewed in
style_guides before commit). Dims are `(obs)` unless shown. Fill (-999 and
-9999, R2) is masked to NaN; integers are stored as int32 with a `_FillValue`
(R16).

**Geolocation:** `time`, `lat`, `lon` (no pixel corners are published).

**Core: the retrieval.**

| source | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- |
| `x` | `water_vapor_hdo_h2o_ratio` *new* | unitless | (obs, level) | none; row 0 of each Standard file masked (R22) |
| `x_h2o` | `water_vapor_h2o_mole_fraction_dry_air` *new* | 1e-6 | (obs, level) | x 1e6 from `1` (mol mol-1) |

Both names are implied by the grammar (`docs/model-comparison-naming.md`,
names table). The evidence that they are the right quantities (checked
2026-10-23 at the user's request):

- **`x` is the HDO/H2O mole ratio profile:**
  - its attributes, in every AIRS collection (RS Summary and Standard R1p6,
    FS R1p11): `comment: "HDO / H2O ratio (includes bias correction)"` and
    `source: "Derived: MUSES:Lite:Species: (x_hdo / x_h2o)"`;
  - its `long_name`, which varies only in case and suffix:
    `bias_corrected_hdo_to_h2o_ratio_profile` (RS Summary, RS Standard, FS
    Summary, and 1,551 FS Standard files), `bias_corrected_HDO_to_H2O_ratio`
    (233 FS Standard files), `bias_corrected_hdo_to_h2o_ratio` (31); units
    `1` throughout;
  - the User Guide, 4.1: "After this operation one can compare the modified
    HDO/H2O profile (x̂) to the "x" variable in the netcdf product file";
  - the User Guide, 4.3: x̂_R "is the (log) of the ratio of HDO and H2O", with
    "x̂_R = X". The file stores the ratio itself; the kernel acts on its log;
  - Sarkar et al. (2026), Methods: "the source Level-2 files provide HDO/H2O
    ratio profiles";
  - the values: p50 2.3e-4, which is δD ≈ -260 per mil against TROPESS's
    3.11e-4 (`dd_col_p`'s `source`).

  It is a ratio of two mole fractions, so `hdo_h2o_ratio` with no basis, as
  the existing row `water_vapor_hdo_h2o_ratio_apriori` ("a priori HDO/H2O
  mole ratio of water vapor").
- **`x_h2o` is the H2O dry-air mole fraction profile:**
  - in Summary (RS and FS), the same values (identical on matched rows; see
    Summary vs Standard) carry `long_name:
    "bias_corrected_dry_air_volume_mixing_ratio_of_water_vapor"` and
    `standard_name: "dry_atmosphere_volume_mixing_ratio_of_water_vapor"`;
  - in Standard, `long_name` `bias_corrected_h2o_vmr_profile` (RS, and 1,551
    FS files) or `bias_corrected_H2O` / `bias_corrected_h2o` (264 early FS
    files), units `1`. The `source` is identical in both types: `"Derived:
    MUSES:Lite:Species: (species[:][17:])"`;
  - the READMEs (Table 3 and 4.1): `x` is the "Retrieved state, as volume
    mixing ratio (VMR) relative to dry air";
  - Sarkar et al. (2026): "water vapor volume mixing ratio (VMR, relative to
    dry air)", and Table 1: "VMR … relative to dry air";
  - for an ideal gas a volume mixing ratio is a mole fraction, so `1` is
    mol mol-1, and x 1e6 gives the canonical `1e-6`.

  **The source `standard_name` is retained.** The style guide says a source
  `standard_name` is kept unchanged. Summary carries one for these values and
  Standard does not, so the store keeps Summary's
  `dry_atmosphere_volume_mixing_ratio_of_water_vapor`.
- **Both stores say they are bias corrected** (user requirement 2026-10-23).
  The nomenclature rows stay general (TES and IASI share them), so the bias
  correction goes in each store's variable metadata, three ways:
  - **`comment`, set in config** so it is the same on every store whatever
    the first granule says. It states that the profile is TROPESS's
    bias-corrected product, quoting the source (`x`: "HDO / H2O ratio
    (includes bias correction)"; `x_h2o`: "H2O only (includes bias
    correction)"). It cites the User Guide 5.1 ("The data are bias corrected
    based on comparison with the aircraft measurements (Herman et al. 2014,
    2020)"), and notes that the uncorrected `retrieval/x_raw` and `x_h2o_raw`
    are in the source files but not stored (Q4).
  - **`original_long_name`**, kept from the source, e.g.
    `bias_corrected_hdo_to_h2o_ratio_profile`.
  - **`source`**, TROPESS's derivation attribute, retained as published.

  The verifier checks that the `comment` is present on both stores.

**Merged from Summary** (NaN where DOF <= 1.1). The definitions come from each
variable's `comment` and `source` attributes (RS and FS Summary, all files),
and were reproduced from the profiles on RS 2010-06-15, FS 2022-06-01 (R1p17)
and FS 2025-06-01 (R1p24).

| source | canonical_name | units | conversion |
| --- | --- | --- | --- |
| `dd_col_p` | `water_vapor_delta_d_850_250hpa` *new* | 1e-3 | none |
| `dd_col_p_error` | `water_vapor_delta_d_850_250hpa_standard_error` *new* | 1e-3 | none |
| `x_h2o_col_p` | `water_vapor_h2o_mole_fraction_dry_air_850_250hpa` *new* | 1e-6 | none |
| `x_h2o_col_p_error` | `water_vapor_h2o_mole_fraction_dry_air_850_250hpa_standard_error` *new* | 1e-6 | none |
| `dd_004` | `water_vapor_delta_d_004` *new* (user's name, approved 2026-10-23, Q2c) | 1e-3 | none |

- **The range is every level of the profile from 250 hPa up to, but not including, 850 hPa** (`250 <= p < 850`; R30).
  - **Usually 8 levels:** 825.4, 749.9, 681.3, 619.0, 510.9, 421.7, 348.1 and
    287.3 hPa (98% of rows on RS 2010-06-15 and FS 2022-06-01).
  - **5-9 over high ground.** Grid levels below the surface drop out, and the
    surface level counts when its pressure is in the range (on 66 and 640
    rows of those two days).
  - `dd_col_p`: `long_name` "mean_delta_d_from_850_to_250_hpa"; `comment`
    "Averaged deuterated water vapor content for the partial column between
    850 and 250 hPa, expressed in parts per thousand relative to the
    deuterium content of ocean waters"; `source` "delta_d = 1000 *
    (np.mean(x_hdo[:] / x_h2o[:]) / 3.11e-4 - 1)".
  - `x_h2o_col_p`: `comment` "Column averaged dry air mixing ratio of water
    vapor content for the partial column between 850 and 250 hPa"; `source`
    "np.mean(species[:][17:])".
  - Every other range misses `dd_col_p` by 19-114 per mil: 200-850, 250-900,
    and the User Guide's 825-421 example (its `dd_825_421`, not in these
    files).
- **Both are unweighted means of the level values** (confirmed 2026-10-23 at
  the user's request).
  - **Reproduced exactly** in RS 2010-06-15, FS 2022-06-01 (R1p17) and FS
    2025-06-01 (R1p24):
    - `dd_col_p` = 1000 × (mean of `x` over those levels / 3.11e-4 − 1), to
      0.0001 per mil, the mean of the ratio;
    - `x_h2o_col_p` = mean of `x_h2o` over those levels x 1e6, to 2e-7.
  - **Every weighting misses:**

    | weighting | `dd_col_p`, max diff (per mil) | `x_h2o_col_p`, max relative diff |
    | --- | --- | --- |
    | pressure thickness | 27-38 | 0.39-0.46 |
    | log pressure | 56-80 | 0.59-0.60 |
    | H2O-weighted, or air mass (H2O x dp) | 160-216 | 6.1-6.6 |
    | ratio of the means (mean HDO / mean H2O) | 160-214 | — |

  - **What the documentation says:**
    - **In the files:** each variable's `source` attribute gives the formula
      as `np.mean(...)`, an unweighted arithmetic mean.
    - **The Standard Product User Guide**, 4.4, gives the recipe for its
      `dd_825_421` example: "M is a vector with values of 1/5 corresponding to
      the 5 pressure levels between 825 and 421 hPa and 0 for all other
      levels". That is equal weights per level, the same method over another
      range. (The grid has 6 levels in 421.7-825.4 hPa, not 5.)
    - **The Summary Product User Guide** (2021), Table 2, and the `comment`
      attributes say only "Averaged …" and "Column averaged …" "for the
      partial column", with no weighting. Read alone, "column averaged"
      suggests a pressure-weighted column average, which these are not.
- **The errors are 1-sigma**, so `standard_error` is right. `dd_col_p_error`
  (`source` "Derived:MUSES:Lite:ObservationErrorCovariance") reproduces as
  (1000 + δD) × √(M S Mᵀ). M is the same equal-weight averaging over those
  levels and S is Standard's `observation_error`; the match is to 7e-8 on RS
  2010-06-15. The -9999 on ~70% of RS rows (R17) is not a negative variance
  (M S Mᵀ >= 0 on every row); its cause is open for the audit.
- **Q2b, decided (user, 2026-10-23): `column` dropped.** TROPESS calls these "column averaged" over a
  "partial column", but they are unweighted means of level values, not
  pressure-weighted column averages. The grammar's `column` means "total or
  column-averaged"; no vertical form means "a value at a level, or a layer
  mean". So the names are:
  - `water_vapor_delta_d_850_250hpa` (+ `_standard_error`);
  - `water_vapor_h2o_mole_fraction_dry_air_850_250hpa` (+ `_standard_error`);
  - a `long_name` that says "unweighted mean over the retrieval levels
    between 850 and 250 hPa".

- **`dd_004`:** `comment` "Delta-D 004: Deuterated water vapor content for
  water vapor volume mixing ratio of 0.004, expressed in parts per thousand
  relative to the deuterium content of ocean waters"; `source` "delta_d =
  1000 * (x_hdo_004 / x_h2o_004 ) / 3.11e-4 - 1)". That is, δD where the H2O
  mole fraction is 0.004. It does not reproduce from the stored profiles: log
  interpolation of `x` to `x_h2o` = 0.004 misses by p50 ~40 per mil (p50 30
  from the raw profiles). So TROPESS computes it some other way, likely on its
  finer internal grid (the `_004` inputs are not in the files).
- **Q2c, `water_vapor_delta_d_004`: no conflict with the style guide.** The
  guide requires only that names come from `nomenclature_data.md`, through a
  row added first. Two project conventions it does touch:
  - **The grammar asks for a qualifier at a level or range**, and `004` is
    one, but it is TROPESS's token, not a physical label like `850_250hpa`
    or `2365nm`.
  - **SCIAMACHY's P3a** set the precedent that "a data-lake name must say
    what it measures without the product's context". Read alone, `004` does
    not say what it is.

  **Decided (user, 2026-10-23): the name stands.** Its row's `long_name`
  carries the meaning: "delta D of water vapor where the H2O dry-air mole
  fraction is 0.004 (4 per mil)".

**Filter inputs** (Sarkar et al. filter FS on DOF >= 1 and COD <= 0.5).

| source | canonical_name (proposed) | units | conversion |
| --- | --- | --- | --- |
| `observation_ops/signal_dof` | `water_vapor_hdo_h2o_ratio_degrees_of_freedom_for_signal` *new* | unitless | none ("trace of averaging kernel") |
| `geophysical/average_cloud_eod` | `cloud_effective_optical_depth` *new* | unitless | none |

**Q3: Sarkar et al.'s other Standard outputs: include all four** (approved
2026-10-23).
They are cheap (one value per obs), and `day_night_flag` documents R13.

| source | canonical_name (proposed) | units | conversion |
| --- | --- | --- | --- |
| `geophysical/cloud_top_pressure` | `cloud_top_pressure` *new* | Pa | x 100 from `hPa` |
| `geophysical/surface_temperature` | `temperature_surface` *new* (quantity first, as `albedo_surface_2365nm`) | K | none |
| `geophysical/land_flag` | `land_flag` *new* | unitless | none (1 land, 0 other; int32) |
| `geophysical/day_night_flag` | `day_night_flag` *new* | unitless | none (1 day, 0 night, -999 fill on up to ~2% of FS rows; int32) |

**Model comparison** (rows exist, named 2026-10-19).

| source | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- |
| `observation_ops/xa` | `water_vapor_hdo_h2o_ratio_apriori` | unitless | (obs, level) | none |
| `observation_ops/averaging_kernel` | `water_vapor_hdo_h2o_ratio_averaging_kernel_log` | unitless | (obs, level, level_2) | none; rows retrieved, columns true (confirmed exactly) |
| `observation_ops/observation_error_h2o` | `water_vapor_h2o_mole_fraction_dry_air_observation_standard_error_log` | unitless | (obs, level) | none; never scaled (R8); 1-sigma assumed (R12) |
| `pressure` | `pressure` | Pa | (obs, level) | x 100 from `hPa` |

**Q4 (approved 2026-10-23): `altitude` in; `x_raw`, `x_h2o_raw` and
`target_id` out.**
- **`altitude`** (m, on `level`). Sarkar et al. grid it, and IASI reports on
  altitude levels. Proposed: **include** as `altitude` *new* (m, (obs,
  level)), so TIR products can be compared by height.
- **`retrieval/x_raw`, `x_h2o_raw`** (before bias correction). Absent from
  264 FS files (R1p11 and early R1p12). Proposed: leave out, since the
  bias-corrected profile is TROPESS's product.
- **`target_id`.** Unique across TROPESS products (O3, CO, TATM), so useful
  for matching other species, but absent from early FS Standard (R4).
  Proposed: leave out; time and position match as well.
- Always out:
  - `observation_error` (R11) and `x_test` (R21);
  - `airs_atrack`, `airs_xtrack`, `airs_granule`, `airs_view_ang` (no rows
    are left out, so the granule index gives each obs's source row);
  - `year_fraction`, the microwindow variables;
  - `datetime_utc`, which is used only to check `time` (P4).

That makes **19 stores per product** with Q3 and Q4 as proposed:
- geolocation;
- 2 core;
- 5 merged from Summary;
- 2 filter inputs;
- 4 Sarkar outputs;
- 3 model comparison, `pressure` and `altitude`.

That is **14 new nomenclature rows**.

### P4. Time

- `time` is TAI93 (R3), in whole seconds in every file probed. The reader
  subtracts the leap seconds since 1993 from a fixed table (1993-07-01 to
  2017-01-01, 10 seconds by 2017). No new leap second has been announced,
  and the table is pinned in code with a test.
- Every row's result must equal `datetime_utc`, or the build fails. The
  verifier repeats the check from raw.
- The stored unit is **seconds**: the coarsest unit that holds the source
  exactly (GOSAT uses ns, TROPOMI ms).

### P5. Declared, never detected

- **R22:** row 0's `x` in every Standard file is masked. The reader confirms
  it equals `x_test` before masking, so a file where it does not fails the
  build.
- **The Summary merge** is checked on every day: Summary rows are exactly the
  Standard rows with DOF > 1.1, in order, with identical shared variables
  (Product scheme).
- **Missing days** (P2), and the one-sided days (Q1).
- **No `declared_rows_left_out`:** every row has time, lat and lon (to be
  confirmed by the audit), so none is left out.

### P6. Filtering guidance in the metadata

Recorded, not applied:
- **Sarkar et al. (2026):** FS filtered with DOF >= 1 and COD <= 0.5. RS was
  gridded from Summary, which is Standard with DOF > 1.1.
- **TROPESS:**
  - the Summary product is the Standard rows with DOF > 1.1 (measured; not
    stated by TROPESS);
  - the User Guide's rule of thumb is "DOFS > 0.7";
  - the User Guide says "the degrees of freedom for signal are 0.8 or larger
    for all profiles", which the Standard files contradict (DOF down to
    ~0.001).
- **The seam** between RS and FS (Product scheme), and R22.

### P7. Chunks and compression

- **Chunk rule** (obs 4,194,304, halved until the chunk fits 40 MiB):
  - scalars: 4,194,304 obs (16 MiB);
  - 17-level profiles: 524,288 obs (34 MiB);
  - the 17 x 17 kernel: 32,768 obs (36 MiB).
- **The kernel** is FS 55.4 GB and RS 19.8 GB uncompressed, in 1,462 and 523
  chunks. That is few enough that no shards are needed (TROPOMI's ~249,000
  were the reason for its shards).
- **Each 17-level store** is FS 3.3 GB and RS 1.2 GB.
- **Compression, decided 2026-10-23 (user) from the bench** (TESTING.md Tier
  2d): blosc zstd 5 + byte shuffle on the kernel, `altitude`, the ratio, its
  a priori, H2O and H2O's error (5-28% smaller than the default zstd; ~9 GB
  over both streams). `pressure` keeps the default, which beats blosc on it
  by 2-7%, as do the 1-D arrays.
- **`granules_per_commit`** (P2), to be set at the bench. Each commit rewrites
  every store's partial last chunk (at most ~36 MiB for the kernel), so fewer,
  larger commits keep superseded copies few.
  - A starting point is ~1.3 M obs per commit: **RS 500 days, FS 50**. That
    makes ~13 and ~37 commits.
  - At ~1.7 KB per obs over all stores, that is ~2.2 GB per batch, with two
    in flight.

### P8. Next, after review

1. **Done 2026-10-23: the 14 new nomenclature rows** (style_guides
   `f18168e`).
2. **Done 2026-10-23 (TESTING.md finding 15): a full-record audit, as a batch job shown first.** Every RS and FS file
   (~142 GB), checking:
   - layout per version;
   - time against `datetime_utc` with the leap table;
   - R22 on every Standard file;
   - the Summary merge on every day;
   - fill patterns (R10, R15, R17);
   - dtype drift;
   - every row has time, lat and lon;
   - `dd_004` and the column means (Q2).
3. The reader and fixture. The shared changes:
   - multi-file Standard + Summary granules;
   - per-granule versions in the granule index;
   - declared masking;
   - the TAI93 decode.

   Then the test over every product, the bench and production.

## Summary vs Standard, v1 (measured 2026-10-23)

Five day pairs tested: RS 2003-03-01 and 2010-06-15; FS 2021-02-01 (R1p11),
2022-06-01 (R1p17) and 2025-06-01 (R1p24). Sampled Standard files for R22: 40
across RS and every FS version.

1. **Same rows, filtered.** Summary is exactly Standard's rows with
   `signal_dof` > 1.1, in the same order, with no mismatches in any pair.
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
   rows with DOF <= 1.1.
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
- **The product type** sets the DOF > 1.1 filter (Summary keeps 65% of RS
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
- TROPESS HDO/H2O Level 2 Summary Product User Guide (2021):
  https://docserver.gesdisc.eosdis.nasa.gov/public/project/TROPESS/User_Guides/TROPESS-HDO_L2_Product_Quick_Start_User_Guide_Summary_only.pdf
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
| R7 | **`x_h2o` reaches 0.93 (RS) and 0.985 (FS) mol mol-1** over the record (audit 2026-10-23), which is unphysical. | record only |
| R8 | **`observation_error_h2o` is a ln-space relative error** with units `1`, sitting next to mole-fraction variables. | open: must never be scaled x 1e6 (project rule) |
| R9 | **RS Summary files are pre-filtered**; FS Standard files are not (DOF down to ~0). The documents disagree on which type is filtered (Format). | record only |
| R10 | **Level 0 of `pressure` is fill on 25-64% of rows in every version**, RS included (resolved 2026-10-22; first read as version drift). Levels below the surface are fill, and the lowest valid level holds the surface pressure. | record only; the fill is masked as usual |
| R11 | **FS `observation_error` is not a valid covariance.** Its `source` attribute says `obs_dd + obs_hh - obs_hd - obs_dh`, which must be symmetric with a non-negative diagonal. Negative variances appear in all three files sampled (AIRS R1p11 2021-02-10, CrIS-JPSS1 R1p17 2022-07-10, AIRS R1p20 2023-06-15), in 16-31% of targets at 750-619 hPa, where the kernel is largest. R1p17 and R1p20 are also asymmetric, by as much as the variances (2026-10-19). The audit's probes (2026-10-23) found a negative variance somewhere in the profile on every row of RS 2010-06-15 and FS 2022-06-01, and FS's asymmetric on every row; RS Standard (R1p6) has the same defect. | decided (user, 2026-10-19): left out, with no nomenclature row (`docs/model-comparison-naming.md` N16). Revisit if TROPESS documents or fixes it; worth reporting to them |
| R12 | **`observation_error_h2o` looks 1-sigma**: p50 0.093, against p50 0.089 for the square root of TES's H2O observation-error variance. Neither the files nor the User Guide state it. | open |
| R13 | **AIRS FS is almost all daytime**: ~13:30 local solar time, against both overpasses in RS (55-57% local night in RS Summary and RS Standard). Night-side FS rows only at \|lat\| ~67-76 in summer. The READMEs say both streams have "day and night time coverage". A property of the stream, not the type (2026-10-23). | record only |
| R14 | **AIRS FS fills 6-10x more 0.7° boxes per day than RS** (corrected 2026-10-23; first read as FS not being box-sampled). All four v1 collections take about one target per box per overpass, as the READMEs describe, measured on 5 days each. <br>- Obs per day, record average: RS 1,739 Summary and 2,689 Standard; FS 10,514 and 26,352. <br>- Boxes filled per day: RS 1,352-2,691; FS 6,788-29,539. <br>- Nearest-neighbour spacing, p50: RS ~110 km; FS 54-78 km. <br>The stream sets the boxes covered. The type thins further (Summary = DOF > 1.1: 65% of RS rows, 40% of FS). Why RS fills so few boxes is not documented. | record only |
| R15 | **`observation_error_h2o` fill changes by version:** from R1p12 F0p2 it is written below the surface (level 0 fill 0-3% vs 53-64% for `x`); from R1p15 its top level (0.1 hPa) is fill on ~96-98% of rows. Confirmed over the record by the audit (2026-10-23), version by version. That fill is **NaN**, not -999: 42.2 M NaN and 210,014 -999 values in FS, and 2,388 NaN and 4,371 -999 in RS. | handled: the reader masks NaN as well as -999 |
| R16 | **FS integer dtypes drift:** int32 → int16 (`airs_*` indices, `day_night_flag`), int32/int64 (`land_flag`, `target_id`). The 52 FS R1p15 F0p3 Standard files store `target_id` as int32, which **overflows** (e.g. -1585826092, against Summary's 24006205300); the audit found every Summary `target_id` disagreeing on those 52 days. `target_id` is not stored (Q4). | open: store the flags and indices as int32 with a `_FillValue` (existing rule) |
| R17 | **`dd_col_p_error` is -9999 on ~70% of RS Summary rows** (747 of 1,017; 1,454 of 2,019; 1,170 of 1,588 in three files), where `dd_col_p` is written. Where written it equals (1000 + δD) × √(M S Mᵀ) to 7e-8. **Cause found (2026-10-23):** it is -9999 exactly where some level between 850 and 250 hPa has a negative `observation_error` variance (R11). That matches 100% of rows on RS 2010-06-15 and 99.6% on FS 2022-06-01; M S Mᵀ itself is usually >= 0. Over the record: RS 8,017,256 of 11,063,132 rows (72%), FS 13,225,737 of 19,071,666 (69%), plus NaN on 195 RS and 73,836 FS rows. | record only; stored as published, with the cause in the metadata |
| R18 | **CrIS-JPSS1 FS Standard v1 was backfilled upstream in 2025:** 108 granules with algorithm R1p24 dated before its R1p24 period (2021-05-21 ..). 5 replace files we hold under older names (2021-05-21, 2022-03-08, 2022-08-13, 2023-12-27, 2024-08-21; upstream updated 2025-09-04 .. 09-11); others fill days missing at our download. One file per date upstream. The 5 new files are downloaded and the old ones kept (the old ones are no longer in CMR). | open, for CrIS: which granule to keep where two exist |
| R19 | **Days not downloaded at first:** AIRS FS Standard 2023-07-21 and 2023-10-19; CrIS-JPSS1 FS Standard 46 dates within our window (2022-05-29 .. 2024-09-01). | handled: downloaded 2026-10-22 |
| R20 | **The README's Summary column kernel is absent** from the RS Summary HDO files (v1). | record only |
| R21 | **`x_test` is one 17-level profile per file** (target 0), not per target: the guide's check of the kernel convention, and the value written over `x[0]` (R22). | handled: not stored |
| R22 | **`x` of the first target in every Standard file is `x_test`, not the retrieval** (all 8,177 Standard files, audit 2026-10-23: RS R1p6 and every FS version R1p11 .. R1p24). It is the kernel applied to the true profile, which Summary holds where that row has DOF > 1.1 (it reproduces to 5e-8). It differs from the retrieval by up to ~6%. Only `x` is affected; the rest of the row is identical to Summary's. One obs per file: 8,177 in AIRS v1. | decided (user, 2026-10-23): masked as a declared defect, recorded in docs and metadata; confirmed from raw (row-0 `x` equals `x_test`) on every file at build and verify |
| R23 | **Standard and Summary dates differ slightly:** RS 2 Standard-only days (2002-08-30, 08-31) and 1 Summary-only (2020-03-31); FS v1 6 Standard-only and 5 Summary-only (listed under Summary vs Standard). | decided (user, 2026-10-23, Q1): every row kept |
| R24 | **AIRS FS v1 has 72 upstream gap days after 2024-09-05**, in 18 runs (e.g. 2024-09-17 .. 19, 2024-10-04 .. 19). | record only (`known_data_gaps`) |
| R25 | **v2 (R1p25, format F2p10) changes the layout:** <br>- Standard is on 34 levels, cut at DOF >= 1.1, and adds `averaging_kernel_h2o`, the five column fields and `air_density`; `target_id` becomes a 36-character string. <br>- Summary stays on 17 levels with the same rows as Standard. <br>- Full keeps every row, on 67 forward-model and 34 retrieval levels, with every HDO/H2O kernel and covariance block (some as compressed int8 bytes). | record only; v2 designed with CrIS (user, 2026-10-23) |
| R26 | **CrIS-SNPP RS and FS retrieve the same targets where they overlap** (2021-02-01 .. 05-21): on 2021-03-01, 326 of RS's 1,111 targets are also in FS (R1p17 vs R1p11). `x` differs by p50 0.17%, up to 10%, and the matched times differ by up to 87 s. TROPESS 1.10 "Fixed to use correct observation time in CrIS products". | open, for CrIS |
| R27 | **Each file runs from ~00:05 UTC to ~00:05 the next day**, so its last AIRS granule ends past midnight: 69,024 RS and 209,149 FS Standard rows are dated the next day. They are not duplicates: consecutive days share no rows. | handled: the granule is the file; every row keeps its own time |
| R28 | **`signal_dof` goes negative**, to -0.90 (RS) and -0.90 (FS). | record only |
| R29 | **More fill to mask**, counted over the record by the audit: `day_night_flag` -999 on 28 RS and 793,403 FS rows; `x_h2o_col_p_error` -999 on 223,959 FS Summary rows; `dd_col_p_error` NaN as well as -9999 (R17). | handled: -999, -9999 and NaN all masked |
| R30 | **The 850 hPa end of the 850-250 hPa means is exclusive**: one FS row (2024-07-01) has its surface at exactly 850.0 hPa, and TROPESS leaves it out. With `250 <= p < 850` both fields reproduce on every row. | record only (in the variables' metadata) |
| R31 | **The Summary rule is strict, DOF > 1.1**: the only 5 rows that broke `>= 1.1` (RS 2010-03-27; FS 2023-03-17, 2023-08-23, 2025-05-21, 2026-03-22) have DOF exactly 1.1 (float32), and Summary leaves each out. | handled: the merge check uses > 1.1 |
| R32 | **TROPESS rows are not in time order** (2026-10-23). <br>- **RS** lists each AIRS granule's rows south to north (latitude increases on 96% of steps), so time runs forward on daytime ascending passes and backward on night-time descending ones. The backward jumps are short (p50 64 s, max 6.4 min; on RS 2010-06-15 sorting would move rows a median of 11 places). <br>- **FS** interleaves AIRS granules from different times of day, apparently in processing order. 36% of steps go back, up to 23 h; sorting would move rows a median of 8,212 places (FS 2022-06-01). <br>- Across days, RS never overlaps, but 175 FS files hold observations later than the next file's first, with no row in both (12 seams checked, 6,929 rows). <br>- **Repeats:** the audit found 0 repeated time, lat and lon within the Standard file of all 8,169 days with both files (`duplicate Standard keys 0`, audit log); the seams were sampled only. In place of the time check, the build and the verifier check every granule and every seam for a repeated observation (user decision 2026-10-23), so production completes the full-record check and stops on any repeat. | decided (user, 2026-10-23): source order kept, with the repeat check; style-guide exception reworded to require it (awaiting review) |
| R33 | **`day_night_flag` changes `standard_name` within FS** (production verify 7924572, 2026-10-23; header scan of every FS file). Standard files 2021-02-01 .. 2022-03-27 (R1p11, R1p12, R1p13, R1p14 and R1p15 to 03-27; 360 files) say `day_binary_mask`; Standard from 2022-03-28 (mid-R1p15) and every Summary file say `sunlit_binary_mask`, as RS does throughout. The first production FS store took the first file's name, and the verifier failed it. | decided (user, 2026-10-23, option A): the FS store carries `sunlit_binary_mask`, declared in config `variable_attrs`, with the old name and the date of the change in its `comment`. The verifier checks a declared `standard_name` is one the source uses; the FS fixture's 2022-06-17 Standard file carries the early name |
| R34 | **RS covers 50°S to 70°N only** (production `--attrs` dry run and stored geolocation, 2026-10-23): latitude -50.0 to 70.0 exactly, 1 observation at -50 and 5 at 70. FS reaches ~67°S to 85°N. | record only |
| R35 | **CrIS-SNPP RS Summary has 134 dates without a file** in 2015-12-01 .. 2021-05-21 (1,865 of 1,999 days; scan of every file, 2026-10-26). CMR lists 1,865 granules, so the gaps are upstream. | open, for CrIS: list them in `expected_missing_days` from the audit |
| R36 | **CrIS `land_flag` is 1 on every row of 324 Standard files** (audit 2026-10-26, TESTING.md finding 16): all 110 SNPP FS days (R1p11, R1p12 F0p1) and JPSS1 2021-04-01 .. 10-31 plus 2021-11-10 (R1p12 F0p1, F0p2; 214 files). Open-ocean rows (central Pacific, southern Indian Ocean) are flagged 1 in those files and 0 from 2021-11-01. On JPSS1 2021-05-21 the old R1p12 file flags all 15,571 targets it shares with the R1p24 replacement 1; the replacement flags 4,028 of them 0. The Summary files of those days carry the same values. SNPP RS (R1p17) and AIRS F0p1 are not affected. | decided (user, 2026-10-26): masked as a declared defect on the listed files, after the reader and the verifier each confirm every row is 1 (a new kind of declared mask: whole files, not a first row) |
| R37 | **CrIS rows repeat across days** (probes 2026-10-26, finding 16). No file repeats a row within itself, but a row of one day's file can have exactly the time, lat and lon of a row of the day before's: SNPP RS 620 Summary rows on 417 days; SNPP FS 8,057 Standard and 2,797 Summary rows; JPSS1 FS 136,702 Standard and 72,574 Summary rows (0.3%) through 2026-05-31, plus 21 and 19 that repeat a row two days back. The repeated rows' times spread over the whole of both days, not the midnight seam: each file holds up to 48 h either side of its date. Every repeat is the same footprint (CrIS indices equal). Compared in every dataset on sampled pairs: identical, SNPP RS 7%, SNPP FS 82%, JPSS1 44%; same retrieval with different errors, SNPP FS 17% (every level), JPSS1 55% (`observation_error_h2o` below the surface only); different retrieval, SNPP RS 93%, SNPP FS 0.5%, JPSS1 1% (and every repeat at an algorithm change). `check_repeats` fails on these, and checks only the day before. Detail and options: `docs/cris-repeats-r37.md`. | decided (user, 2026-10-26): each repeat stored once, the copy from the newest algorithm, then the latest `ProductionDateTime`; declared in config, applied from raw by the build and the verifier; an approved exception to keeping every observation (`docs/cris-repeats-r37.md`, Decision) |
| R38 | **JPSS1 FS `day_night_flag` changes `standard_name`** as AIRS FS's did (R33): `day_binary_mask` in 364 files, 2021-04-01 .. 2022-03-30 (two of them R18 old files); `sunlit_binary_mask` from then and in the R1p24 backfill. Nine `long_name`s change case or wording at 2021-09-24 and again in 2021-11 (e.g. `bias_corrected_HDO_to_H2O_ratio` to `..._profile`); `units` and `_FillValue` never change. `retrieval/mw` is `m-6` in most files and `cm-1` in 2023-11 (not stored). SNPP's attributes never change. | decided (user, 2026-10-26): `sunlit_binary_mask` declared, the old name and dates in the `comment`, as for AIRS FS |
| R40 | **CrIS rows are not in time order** (measured on every file, R37's rows left out, 2026-10-26). A file is mostly its UTC day in time order, with: <br>- **edge rows:** the first and last minutes of the neighbouring days at its start and end (SNPP RS 0.5%, SNPP FS 0.5%, JPSS1 0.4% of rows; a few strays further out), so time steps back at 1,350 of 1,864, 106 of 109 and 1,812 of 1,886 day seams; different observations, not copies (those are R37); <br>- **a 64 s jitter** (two 32 s CrIS granules) within the day: SNPP FS 9,272 steps, JPSS1 ~30,900; <br>- **larger blocks** in JPSS1 only: 13,260 steps back of more than 2 minutes, up to a day; SNPP RS has 11 within-day steps of ~24 h. <br>Far closer to time order than AIRS FS (36% of steps back, R32). | decided (user, 2026-10-26, option 1 of three): the source order is kept (`time_order: source`) for all three CrIS products, with the repeat check (look-back 2) in place of the time order. The alternatives were sorting within each file (the seams still step back) and regrouping granules by observation day |
| R41 | **v2 Standard is v2 Full's rows with `quality == 1`** (probes 2026-10-28, one day each): same order, same `target_id`s, shared datasets identical except below-surface `observation_error_h2o` and `altitude` (R43). Summary is Standard's levels 0-16 on the same rows. R25's "cut at DOF >= 1.1" undercounts the cut: DOF alone would keep ~13-19% more rows. | open: confirm over every v2 file in the audit |
| R42 | **v2's 34 retrieval levels are v1's 17, padded** (probes 2026-10-28): every retrieval-grid array, the joint 34x34 blocks included, holds values only on levels 0-16. Full `pressure_ret` repeats the grid in 17-33; Standard `air_density` has two identical halves. **Full `air_density` is Standard's 34-wide array** (x N_A, to 1e-7) in the first 34 slots of a 67-wide array declared on `level_fm`, the rest fill: it is not on `pressure_fm`. No document explains the 34: the GES DISC catalog entries for every v2 HDO collection (Standard and Full) say "reported at 17 vertical levels from the surface to 0.1 hPa", and the README in the v2 folders is still the 2023-05-09 v1 text. The pattern matches a joint HDO+H2O state vector (17 + 17) used to size every retrieval-level array. `tools/survey/tropess_v2_levels.py` checks every v2 file. Confirmed on every 10th day of both instruments, all three types (51 files; TESTING.md finding 17). | decided (user, 2026-10-28): store levels 0-16 only. The build and the verifier fail on any value in 17-33, except declared copies (`pressure_ret`, `air_density`) that must equal 0-16; Full `air_density` slots 34-66 must be fill |
| R43 | **v2 Standard `altitude` belongs to other targets** (probes 2026-10-28). Flattened to (2n, 17), its first n rows are exactly the altitudes of targets 0..n-1 (Summary's, which equal Full's at the retrieval pressures), on every row of AIRS and CrIS 2026-06-01. So Standard row i holds target 2i's altitude in levels 0-16 and target 2i+1's in 17-33, and rows n/2 .. n-1 are zeros. It looks like an (n, 17) array written into an (n, 34) one through the flat buffer. Only row 0's levels 0-16 are its own. This explains the R37 copies whose `altitude` differs: each file's shift is different. Summary and Full `altitude` are physically consistent (hypsometric layer temperatures 255-313 K). Confirmed on every 10th day (TESTING.md finding 17). | decided (user, 2026-10-28): `altitude` from Full, read at the 17 retrieval pressures (equal to Summary's); Standard's is never read |
| R44 | **v2 Full `species` is the HDO mole fraction** on 67 levels, roughly `x` x `x_h2o` (ratio p50 1.0036, 0.98-1.15), though its `standard_name` is `molar_ratio_of_hdo_to_h2o` and units `mol mol-1`. `constraint_vector` is exactly `xa` x `h2o_constraint_vector`. | open: only if a Full store uses them |
| R45 | **v2's ratio kernel has a square block of fill at its lowest levels** on some `quality` 0 rows (audit 2026-10-28): 898 AIRS rows (30 days) and 113 CrIS rows (137 days), up to 6x6 values where `pressure_ret` is written. The four joint blocks are complete on those rows. | record only; stored as published (NaN) |
| R46 | **AIRS v2 Full has two layouts** (audit 2026-10-28): from 2026-06-03 the files carry a dimension-scale dataset `l1b_source_file` (an upstream `ncrename` of the `l1b_source` dimension). No stored source changes. | record only |
| R39 | **CrIS integer dtypes drift as AIRS's do (R16):** SNPP RS Summary has 4 layouts, differing only in `land_flag` and `day_night_flag` int16/int32/int64; JPSS1 has 11 Standard and 8 Summary layouts, from the same drift, the `cris_*` indices int32 to int16, and unstored variables (`target_id`, microwindows, `retrieval/x_raw`) coming and going. | handled as for AIRS: flags stored int32 |
