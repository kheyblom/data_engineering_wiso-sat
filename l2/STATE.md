# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Where we are (2026-10-28)

**Current task: TES (user, 2026-10-28).** Nothing is running; no batch job
is queued. Decisions T1-T12 are laid out in `docs/products/tes.md`
("Decisions for the user"), from probes of three files and the upstream
listing; waiting on the user's answers. Found: v006 (on disk) is retired
from CMR, and V007 lacks 2005-01 .. 2008-11 upstream (T1, E7); time is
TAI93 (E4); the kernel is rows retrieved, columns true, as stored (E6,
settled from the Lite HDO bias correction); 2,825,124 rows in 71.5 GB.
Next: the user's answers, then the audit of every file (a batch job, shown
first).

**Finished products** (every store finalized: `--attrs` and a tag, each
`--apply` signed off by the user). Facts, decisions and issues are in each
`docs/products/<product>.md`; audits, benches and run logs in TESTING.md.

| product | stores | tag | zarr folder under `.../data/wisosat/zarr/` | obs |
| --- | --- | --- | --- | --- |
| TROPOMI | 19 + 6 model-comparison | `v8.1-verified-20261018`, `v8.1-verified-20261022` | `tropomi/` (~21 TiB) | 32,657,526,234 |
| GOSAT | 12 | `v3.0.1-verified-20261019` | `gosat/` | 8,856,028 |
| GOSAT-2 | 12 | `v3.0.1-verified-20261022` | `gosat2/` | 1,620,006 |
| SCIAMACHY | 22 | `v8.1-verified-20261022` | `sciamachy/` (87.5 GiB) | 78,666,297 |
| AIRS v1 RS, FS | 19 + 19 | `v1-verified-20261023` | `airs/` | 17,109,546; 47,882,856 |
| CrIS v1 SNPP RS, SNPP FS, JPSS1 FS | 12 + 19 + 19 | `v1-verified-20261026` | `cris_snpp/`, `cris_jpss1/` | 2,597,674; 2,858,343; 47,391,889 |
| AIRS v2, CrIS-JPSS1 v2 (Full) | 22 + 22 | `v2-verified-20261028` | `airs/`, `cris_jpss1/` (4.1 GB, 22 GB) | 1,028,658; 4,676,513 |

- **TROPESS v2, finished 2026-10-28** (`tropess.md`: "v2: answers" and the
  "v2 production subset" V1-V9; issues R41-R46; TESTING.md findings 17-18,
  Tier 2f and the TROPESS v2 run log; ~3.3 core-hours in all):
  - built from the **Full** files only (the v2 Standard product is exactly
    Full's `quality == 1` rows, R41), on v1's **17 levels** (the 34-wide
    retrieval dimension is 17 padded, R42), `altitude` read from Full's
    67-level grid at the retrieval pressures (Standard's is misplaced, R43);
  - 22 stores each: v1's 19, `quality_flags_retrieval`, `air_molar_density`
    (new style_guides row `4711fe4`; source `standard_name` withheld, an
    approved exception) and the joint HDO/H2O kernel as one matrix store;
  - v1 exceptions carried only where the situation is the same (user rule
    2026-10-28): R11 (left out), R32 and R40 (source order), R37 (CrIS
    repeats, 11,382 left out). R22, R36 and R38 do not occur in v2. The
    v1/v2 seam shares no observation;
  - **later days are appended** as the data-access session downloads them
    (CrIS v2 grows daily upstream): stage nothing, but re-declare CrIS's R37
    count first (measure with the reader's rule), then build (resumes),
    verify, finalize with a new tag (`tropess.md` V8, step 6). Show each job.
- **Shared code added for TROPESS v2** (CLAUDE.md, "Added for TROPESS v2"):
  source slices in the key with checked remainders, `level_lookups`, matrix
  stores (N18), `withheld_standard_names`. Slices and matrix stores were
  shaped for **TES**'s stacked HDO/H2O state (`tes.md` E1), which now needs
  no new mechanism for its blocks.
- **The fixture test passes 445 cases over 11 fixtures** (~15 min, login
  node, 2026-10-28).
- **Tasks 1-5 and the cross-product naming pass (task 7) are done**
  (`docs/model-comparison-naming.md`, N1-N18).
- **Compute used:** TROPOMI ~380 core-hours for the 19 stores and ~835 for
  the 6 model-comparison stores (the overrun approved by the user); GOSAT
  ~0.5; GOSAT-2 ~0.2; SCIAMACHY ~8; AIRS v1 ~6.6; CrIS v1 ~5.3; TROPESS v2
  ~3.3.

## Next: candidates (ask the user which)

The data-lake home for finished stores is not a candidate: the user will say
when it is time (2026-10-22).

1. **The other products** (task 6): IASI and TES, the last two. Each gets
   the same path as TROPESS v2: lay the decisions out for the user, an audit
   of every file, the production subset reviewed in place, the reader at
   fixture level, the full fixture test, a bench, production, finalize.
   Their open issues are under Open items.
   - **TES:** matrix stores and source slices now exist (its 34-level
     stacked state splits by slice; its 4 blocks per matrix are one store
     each). Raw `TES/TL2HDOLN_6-*/`, monthly files; 2011-2015 absent.
   - **IASI:** the store version (I7) must be decided first; the rank
     padding to the record maximum (N10, I6) is still to build.
2. **GOSAT `dry_column`** (held, N11; `gosat.md` G7): ~1/4 of the
   hydrostatic dry column, with no area in its unit. Resolve from the
   GHG-CCI PSD v3 or by asking IUP, then add as `dry_air_partial_column`
   (GOSAT-2 has the same variable, so both products would get it).
3. **Optional cost work before the next large product** (TESTING.md finding
   12): the build still uses ~2.5x the CPU its stages need, mostly kernel time
   from page faults on multi-GB arrays (glibc maps every allocation over 32
   MB fresh). Untested remedies: buffer reuse, transparent huge pages. Verify
   is worse: ~2x the re-bench CPU per granule-store with 64 processes on one
   node.

## Open items

- **Throwaway data on scratch** (delete only with approval):
  `/glade/derecho/scratch/kheyblom/data/wisosat_bench/tropomi` (25 bench
  stores of 2020-07, roughly 280 GiB with the 2-D stores' superseded
  shards; every other bench is deleted) and `wisosat_fixture/` (staged raw
  and stores rebuilt by the test, ~100 MB of raw).
- **Audit outputs** under `/glade/derecho/scratch/kheyblom/data/wisosat/audit/`
  (`tropess_v2_audit.*`, `tropess_v2_levels.*` and the v1 ones): the
  evidence behind TESTING.md findings 15-18; small, keep.
- **Deleted 2026-10-22 with the user's approval:** the SCIAMACHY bench (22
  stores, 2.2 GiB, and its 3 raw symlinks) and the raw tree's 22 hidden
  `.ArchiveServiceTemp.sb-*` folders (S5; 3,350 duplicate orbit files, 13
  GB). The raw root's `.DS_Store` is left.
- **SCIAMACHY orbits were not checked against an upstream listing** (4525 to
  52867 numbered, 41,616 present); stated in `known_data_gaps`. Possible if
  the user knows the download source.
- **Leftover small files:** each of the 6 TROPOMI 2-D stores keeps ~3,870
  transaction logs and ~3,870 `overwritten/` entries that `--gc` does not
  delete. Harmless; worth a look before moving to the data lake.
- **Open issues from the naming pass**, to settle when each reader is built
  (full lists in each `docs/products/<product>.md`, Known data issues):
  - **IASI I7 (blocks the store names):** the processor version changes in
    2019, 030201 to 030300, and MetOp-C joins (AB to ABC). Decide the store
    version with the user.
  - **IASI I6:** the record maximum of `wv_avk_rank` and `wv_xavkat_rank`,
    for the padding (N10): a header scan of 4,568 files.
  - **IASI I8:** declare `K-1` on `musica_wvp_xavkat_val` (approved, N17).
  - **TROPESS R10:** FS `pressure` level 0 is -999 in R1p17 and R1p20, not in
    R1p11.
  - **TROPESS R11:** `observation_error` left out (approved, N16); reporting
    it to the TROPESS team is optional.
  - **TROPESS R12:** confirm that `observation_error_h2o` is 1-sigma.
  - **TES:** `ObservationErrorCovariance` has no `Units`; declare
    `ln(vmr)^2`. The kernel convention is settled (E6, 2026-10-28). The rest
    is in `tes.md` T1-T12.
  - **TROPESS v2, for later:** the int8-packed 67x67 blocks and the
    67-level `species` / prior (R44) are left out; addable as stores of
    their own (the packed ones need TROPESS's `tropess_compression` and an
    independent decoder in the verifier).
- **Elsewhere:** GLEAM and MSWEP carry a deferred task 2 (add `cdm_data_type:
  Grid`; `standard_name` from the source only).

## How we work (user preferences)

- **Show every batch job before submitting it**, with its cost; wait for
  approval. Go tiny fixture, then bench, then production. The allocation is
  finite. When a running job will cost more than approved, say so at once
  with the new figure.
- **Builds start only from a clean commit.** The build and the wrapper both
  refuse a dirty tree. Commit before submitting; while builds are queued,
  commit any edit at once (each later job stamps the new revision; harmless,
  but it shows in `history`).
- **Never run two verifies of one config at once** (shared evidence log;
  CLAUDE.md). Chain them `afterany`.
- **No exception to the style guide or the project rules without the
  user's approval** (2026-10-26), even one approved for another product:
  `time_order: source` was carried from AIRS to CrIS without asking and
  had to be held, measured and put to the user (R40). Measure first, lay
  out the options, let the user decide.
- **Edits to style_guides** are shown to the user before commit; they review
  in place with `#@CLAUDE` comments.
- **Proposals for the user** go in a repo doc reviewed in place with
  `#@CLAUDE` comments (example: `docs/model-comparison-naming.md` up to
  `e87a8e1`).
- **Claude runs finalize, one action per call; the user signs off on each
  `--apply`** (CLAUDE.md). Order: `--attrs`, `--tag`, `--expire` (sharded
  stores only), `--gc`. `--expire --apply` and `--gc --apply` are
  irreversible. Any `rm -rf` needs approval too. Finalize ran without
  permission refusals in the 2026-10-22 session.
- **No pipeline runs on the login node** beyond the fixture test, finalize,
  metadata-only verifier phases and small one-file probes: a 4-orbit build
  there was killed by the login node's limiter (2026-10-19).
- **Verify only new or changed stores**; then a cheap `--phases
  structure,index` over every store confirms the shared index.

## Things the next session needs to know

- **PBS:** a job's `.OU` file appears while it runs (`Keep_Files = od`).
  Check `job_state` with `qstat -f <id>.desched1` and `Exit_status` with
  `qstat -xf`; a fresh job id can take a few seconds to show. A job stopped
  by walltime exits -29. Watch a chain's first job until it commits.
  Background watchers end with the Claude session; re-check by hand after a
  reconnect.
- **Commands** (repo root):
  - test: `TMPDIR=/glade/derecho/scratch/$USER/tmp uv run python validation/test_pipeline.py`
    (stage each product's fixture once first: `validation/stage_<product>.py`);
  - batch: `bash -lc 'cd ~/work/data_engineering/data_engineering_wiso-sat && CONFIG=... [VERIFY=1] [VERIFY_ARGS="..."] [AFTER=<jobid>] QUEUE=develop NCPUS=.. MEM=.. WALLTIME=.. ./submit_wisosat_zarr.sh'`
    (`bash -lc` for `PBS_ACCOUNT`). The wrapper checks `num_workers`, or
    `verify_num_workers` for a verify with the values phase, against the
    cpus granted.
- **Sizes that worked (develop, 6 h maximum; develop allows up to 256
  cores):**
  - TROPESS v2 build or verify: 8 cores, 48 GB, 5 days per commit (the
    padded 34x34 kernels are read whole, ~1 GB a day); CrIS 137 days ~8 min
    build, ~6 min verify. Every other TROPESS product: 8 cores, 32 GB.
  - TROPOMI 1-D build or verify: 8 cores, 32 GB, ~4 h each.
  - TROPOMI 2-D build: 8 cores, 128 GB, 10 granules per commit, ~46 h in
    6 h jobs chained `afterany` (builds resume). Verify: 64 cores, 200 GB,
    three stores per job, ~3.5 h each (the verifier does not resume).
- **Shared design added 2026-10-19** (CLAUDE.md, Layout): per-array
  compression and shards (`compression`), `own_process_stores`, range scans
  in the verifier (`verify_granules_per_task`, `verify_num_workers`),
  `finalize --expire`, CPU split in every run's log, no
  `MALLOC_TRIM_THRESHOLD_`.
- **TROPOMI's history attributes:** the 19 first stores needed
  `--build-revisions 7220460@0,24186fe@7020` and the corner build
  `--dirty-notes` (text in `logs/finalize_wisosat_zarr_tropomi.log`). The 6
  model-comparison stores name `4945839`, `157d4af`, `53c063b` (identical
  build code).

## Decisions in force (user)

- **Store names:** `wisosat.<product>.<version>.inst.native_swath.<variable>.zarr`;
  the version from the files' attributes, no product token (2026-10-14).
- **One pass, many stores** (2026-10-14): each granule is read once and
  written to every store of a config, **except** stores in
  `own_process_stores`, each built in a process of its own that reads only
  its sources (2026-10-19, finding 12).
- **GOSAT DED and H2O are merged into one product** per day (2026-10-14).
- **An observation is a row with time, lat and lon all written**, for every
  product (2026-10-16/17). Other rows are left out, checked; a row left out
  may hold values only in `allowed_on_rows_left_out`. `granule_source_rows`
  keeps each file's row count. Corrupt upstream files are declared and left
  out.
- **The TROPOMI subset:** the core 7, the 9 inputs to the Schneider et al.
  (2022) Table 1 filters, `scanline_index` and `ground_pixel_index`, the
  pixel corners (in geolocation), and the 6 model-comparison stores. Others
  only when asked (`tropomi.md`, Variable inventory).
- **Model-comparison naming** (2026-10-19; `docs/model-comparison-naming.md`):
  - grammar `<quantity>[_<vertical form>]_<species>[_<basis>][_<role>]`;
    species always explicit, no `profile` token, `partial_column` per layer;
  - **`pressure` is a variable store of its own, in Pa, with a nomenclature
    row** (revises N3; style guide rule, style_guides `65ac688`), in every
    product; the geolocation store holds time, lat, lon only;
  - vertical dims `level` and `layer`, a matrix's second axis `level_2`
    (rows retrieved, columns true); each source keeps its vertical order,
    recorded in `vertical_order`;
  - ln-space kernels end in `_log`, off-diagonal blocks in
    `_cross_<quantity>`, both cross blocks kept;
  - a matrix published in pieces is one store with each piece an array
    (TES kernel and covariances, IASI SVDs); IASI SVD vectors split per
    proxy state, `rank` padded to the record maximum with NaN;
  - left out: GOSAT `dry_column` (held) and the TROPESS ratio covariance.
- **Chunks:** `chunks.obs` 4,194,304, halved per array until it fits 40 MiB,
  so every store's chunk boundaries align (2026-10-18).
- **Compression and shards (2026-10-19):** blosc zstd 5 + byte shuffle and
  shards of 4,194,304 obs for wide arrays, set per array in config (TROPOMI's
  6); everything else keeps zarr's default zstd, unsharded. Sharded stores
  have their build snapshots expired at finalization.
- **Filtering guidance** in the metadata is Table 1 in full, plus the
  inferred reduced chi-squared.
- **SCIAMACHY (2026-10-22):** stores `v_8_1`; no δD (SRON publish none); the
  1-D stores align with TROPOMI's, plus what Sarkar et al. (2026) filter on.
  - **S8:** orbit 15838 keeps the first of its three identical copies.
  - **S9, a one-time exception** to "never select observations": the last 32
    rows of 45262, a second retrieval of 45263's first 32 scenes, are left
    out. Checked against 45263 and named in the metadata. Not a precedent.
- **Naming rule:** the quantity first, then qualifiers general to specific.
  Established terms stay whole; unitless quantities use `unitless`.
- **TROPESS products (2026-10-22, revised 2026-10-23; `tropess.md`, Product
  scheme):**
  - one product per platform, stream and collection version; Summary is
    merged into Standard, with no summary/standard token in the name;
  - the version slot follows the style guide's `v_3_5.nrt` form:
    `wisosat.airs.v_1.rs...` and `wisosat.airs.v_1.fs...`;
  - RS and FS stay separate; R22 masked as a declared defect; rows kept in
    source order (`time_order: source`, R32);
  - FS v2 (2026-06 on) is a separate `v_2.*` store set; Full products are
    added when downloaded;
  - per-granule algorithm, format and joint flag go in the granule index, a
    shared change approved for every product that needs it;
  - CrIS products carry the platform: `cris_snpp`, `cris_jpss1`.
- **CrIS (2026-10-26; `tropess.md` CrIS handoff, Answers):** rows in source
  order (R40, approved per product after measurement); SNPP RS built
  Summary-only; SNPP FS its own product; R18 keeps the R1p24 replacement;
  the SC Australian fires left out; R36 `land_flag` masked on the 324
  defective files, declared; R38 `sunlit_binary_mask` declared; **R37 each
  repeated footprint stored once, newest algorithm then latest
  `ProductionDateTime`** (an approved exception, `docs/cris-repeats-r37.md`).
- **TROPESS v2 (2026-10-28; `tropess.md` v2 answers and V1-V9):** Full
  only, a separate `v_2.fs` product per platform; 17 levels kept, the rest
  checked; `altitude` from Full; v1's 19 stores plus the quality flag, air
  molar density (no `standard_name`, Q2) and the joint kernel as one matrix
  store (`averaging_kernel_h2o` is its H2O block, Q1); non-CF source
  `standard_name`s retained (Q3); the int8-packed blocks and the 67-level
  fields left out; built now, appended later.
- **A v1 exception carries over to a new collection only if the situation is
  the same** (user, 2026-10-28); where the setup or the need differs, the
  user approves it again. Measure, then say which.
- **Downloads are done outside this repo** (2026-10-22): a separate
  data-access session fetches raw data; this repo only reads it.
