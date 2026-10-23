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
- **Summary's `target_id`** fills in where the Standard file lacks it (FS
  R1p11 and early R1p12), if the audit confirms it agrees wherever both have
  it.
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
