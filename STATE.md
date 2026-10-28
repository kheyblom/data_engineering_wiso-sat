# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Where we are (2026-10-26)

**Nothing is running.** No batch jobs are queued.
- **Current task: TROPESS v2 (AIRS and CrIS-JPSS1 together).** **Decision 5
  answered 2026-10-28; first probes done** (`tropess.md`, "v2: answers
  (user, 2026-10-28) and first probes"; R41-R44). The user chose both
  Standard and Full, v1's variables plus v2's new ones, to build now, and
  v1 exceptions only where the situation is the same. **The probes found
  v2 Standard to be exactly Full's `quality == 1` rows with identical
  values**, so building both stores the same values twice. Since decided
  (2026-10-28, after a scan of every 10th day, TESTING.md finding 17): 17
  levels (R42), `altitude` from Full (R43), v1's 19 stores plus `quality`,
  `averaging_kernel_h2o`, `air_density` and the three cross kernels. **Full only
  (user, 2026-10-28).** The v2 Full audit ran (job 7989391, TESTING.md
  finding 18; R45, R46). **The v2 production subset is approved
  (2026-10-28, Q1-Q3 as proposed)** (`tropess.md`, "v2 production subset", V1-V8;
  Q1 `averaging_kernel_h2o` as the joint store's H2O block, Q2 the
  `air_density` row, Q3 non-CF retained `standard_name`s). **Code done
  2026-10-28** (V9 design, user-approved: D1 a v2 reader and key, D2 general
  source slices shaped for TES, D3 matrix stores, D4 the key; `tropess.md`
  V8 "Done"): configs `config/airs_fs_v2/`, `config/cris_jpss1_fs_v2/`
  (22 stores each), fixtures staged. **The full fixture test passes 445 cases over
  11 fixtures** (2026-10-28, the two v2 included). **The v2 bench passed**
  (2026-10-28, TESTING.md Tier 2f): 9 days each, 1,018 and 1,065 checks, 0
  failures, ~0.6 core-hours. **v2 production is built and verified**
  (2026-10-28, from `5148f6c`; TESTING.md, TROPESS v2 run log; ~2.3
  core-hours): AIRS 22 stores, 1,028,658 obs, 1,018 checks; CrIS-JPSS1 22
  stores, 4,676,513 obs, 1,065 checks; **0 failures**. The v2 bench data is
  deleted (user approved). `finalize --attrs` applied on all 44 stores
  (user sign-off 2026-10-28). **Next: `--tag v2-verified-20261028`, its
  `--apply` signed off by the user.**
  Exceptions that match v1: R11, R32 (AIRS), R37 and R40 (CrIS). R22 does
  not occur in v2. The v1/v2 seam shares no rows.
- **Earlier handoff text:** read `docs/products/tropess.md`, section "v2:
  handoff", first. It holds what
  is settled (a separate `v_2` store set), what is on disk (AIRS 30 days,
  CrIS-JPSS1 139 days, each in Summary, Standard and Full), the layout
  known from R25, the decision to lay out for the user (which type: Standard
  is already cut at DOF >= 1.1, Full keeps every row at 9-13x the size; the
  variables; when; the v1/v2 seam), and the code that assumes v1. **No v1
  exception carries over without the user's approval** (R40 time order,
  R37 repeats): measure, then ask.
- **CrIS v1 is finished (task 6): 50 stores finalized 2026-10-26**, tag
  `v1-verified-20261026`, in
  `/glade/derecho/scratch/kheyblom/data/wisosat/zarr/cris_{snpp,jpss1}/`.
  The history of the CrIS work follows. **`docs/products/tropess.md`,
  section "CrIS: handoff"**
  holds what is settled, the five decisions the user must make before any
  code (SNPP RS is Summary-only upstream; SNPP FS overlaps; R18 duplicate
  files; the SC Australian-fire collection; v2 with AIRS v2), the reader
  changes known to be needed (filter by instrument first: SNPP and JPSS1 FS
  folders would otherwise collide), and the lessons from AIRS (scan every
  file's attributes in the audit: R33 reached production).
  - Settled: tokens `cris_snpp` and `cris_jpss1` with `source: tropess`;
    AIRS v2 is designed with CrIS-JPSS1 v2.
  - **Answered 2026-10-26** (handoff, "Answers"): SNPP FS is its own
    product; R18 keeps the R1p24 replacement; the SC Australian fires are
    out; SNPP RS is built Summary-only (re-checked from raw and live CMR
    first). Decision 5 (v2) waits.
  - **The CrIS v1 audit ran** 2026-10-26 (develop job 7960036, ~0.6
    core-hours; TESTING.md finding 16). The AIRS assumptions hold; new
    issues R36-R39 in `tropess.md`. Decided 2026-10-26: R36 `land_flag`
    masked as a declared defect on the 324 files; R38 `sunlit_binary_mask`
    declared as for AIRS FS; R37 each repeated footprint stored once, the
    newest algorithm's copy, then the latest `ProductionDateTime`
    (`docs/cris-repeats-r37.md`, Decision).
  - **The CrIS production subset is approved** (2026-10-26; Q1 yes, Q2 as
    proposed): `tropess.md`, "CrIS v1 production subset" (C1-C8; 50
    stores).
  - **The reader, shared changes, configs and fixtures are done**
    (2026-10-26; CLAUDE.md, "Added for CrIS"): `config/cris_snpp_rs/`,
    `config/cris_snpp_fs/`, `config/cris_jpss1_fs/`; R37 counts measured
    and declared (620, 8,057, 136,707). **The fixture test passes 350
    cases over 9 fixtures** (~15 min).
  - **The CrIS bench passed** (2026-10-26, TESTING.md Tier 2e): one month
    per product, 568, 883 and 884 checks, 0 failures; ~0.5 core-hours.
    Compression as AIRS. **The CrIS bench data is deleted** (user approved
    2026-10-26): its stores and symlink trees in `wisosat_bench/`. The
    configs and stager stay, to rebuild it.
  - **CrIS v1 production is built and verified** (2026-10-26, from
    `537d3ca`; TESTING.md, CrIS v1 run log; ~4.2 core-hours): SNPP RS 12
    stores, 2,597,674 obs, 568 checks; SNPP FS 19 stores, 2,858,343 obs,
    883 checks; JPSS1 FS 19 stores, 47,391,889 obs, 885 checks; **0
    failures**, R37, R36, R22, R18 and R38 confirmed on the full record.
    **Finalized 2026-10-26**, tag `v1-verified-20261026` on all 50 stores
    (`--attrs` and `--tag`, each signed off by the user; no `--expire` or
    `--gc` needed). **CrIS v1 is finished.** Decision 5 (v2 for AIRS and
    CrIS-JPSS1) still waits.
    Was: the reader and shared changes
  - **R40 decided (user, 2026-10-26): CrIS keeps the source row order**
    (`time_order: source`, option 1), approved per product after
    measuring every file; it had been carried over from AIRS without asking
    and was held until then. (instrument filter,
    Summary-only granules, R18 declared file, whole-file declared mask,
    the R37 rule with look-ahead), fixtures, the full test, a bench.
  - Every CrIS collection is on disk under `raw/CRIS/` (downloaded
    2026-10-22; `~/work/data_access/access_tropess/HANDBACK.md`).
  - Start by laying the collections and decisions out for the user (as for
    AIRS), then generalise and run the audit.
- **AIRS v1 is finished: 38 stores, all finalized** 2026-10-23, tag
  `v1-verified-20261023`, in
  `/glade/derecho/scratch/kheyblom/data/wisosat/zarr/airs/`: two products of
  19 stores each (geolocation, `pressure`, 17 variable stores), on their own
  obs axes.
  - **RS** `wisosat.airs.v_1.rs.*`: 6,363 days, 2002-08-30 .. 2020-03-31,
    17,109,546 obs, 50°S to 70°N (R34), 20.1 GiB; 842 checks, 0 failures.
  - **FS** `wisosat.airs.v_1.fs.*`: 1,820 days, 2021-02-01 .. 2026-05-31,
    47,882,856 obs, 55.6 GiB; 843 checks, 0 failures.
  - Decisions, evidence and issues R1-R34: `docs/products/tropess.md`
    (Product scheme; production subset P1-P8). Audit, bench and run:
    TESTING.md finding 15, Tier 2d and the AIRS v1 run log.
  - Summary merged into Standard per day; the row-0 `x` defect (R22) masked
    as declared; rows in source order with the repeat check in place of the
    time order (R32; style_guides `43b6b51`); blosc on the six 2-D arrays;
    FS `day_night_flag` carries `sunlit_binary_mask`, TROPESS renamed it
    mid-record (R33).
  - Shared code added for it (CLAUDE.md, Layout): `version_product`,
    `time_order`, `check_repeats`, `declared_masked_values`, `source_dtypes`,
    `expected_partial_granules`, a reader's `LISTING_OPTIONS` and
    `INDEX_EXTRA`, and declared `standard_name`s checked against the source.
  - ~6.6 core-hours in all: audit ~1, benches ~0.1, production ~5.5 (with
    the R33 rebuild and two FS re-verifies).
- **The AIRS bench data is deleted** (user approved 2026-10-23): its stores
  and symlink trees in `wisosat_bench/`. The configs and stager stay, to
  rebuild it.
- **The fixture test passes 445 cases** over 11 fixtures (~15 min, login
  node), 2026-10-28.

- **Tasks 1-5 are done.** The shared pipeline (`CLAUDE.md`, Layout) and the
  testing tiers (`TESTING.md`) are in place.
- **TROPOMI is finished: 25 stores, all finalized**, in
  `/glade/derecho/scratch/kheyblom/data/wisosat/zarr/tropomi/`, on one obs
  axis (32,657,526,234 obs, 38,645 orbits) and one granule index.
  - 19 stores, tag `v8.1-verified-20261018` (~1.8 TiB): geolocation (time,
    lat, lon, pixel corners), 16 variable stores, `scanline_index`,
    `ground_pixel_index`.
  - **6 model-comparison stores, tag `v8.1-verified-20261022`** (19.6 TiB):
    both column kernels, both a priori partial columns,
    `dry_air_partial_column`, `pressure` (its own store). Blosc zstd 5 +
    shuffle, sharded at 4,194,304 obs, build snapshots expired and
    garbage-collected (~7,800 chunk files per store).
  - Run logs, every job and its cost: `TESTING.md` Tier 2, 2b and 3; findings
    9-12. Product facts, issues T1-T22 and the variable inventory:
    `docs/products/tropomi.md`.
- **GOSAT is finished: 12 stores, all finalized**, tag
  `v3.0.1-verified-20261019`, in
  `/glade/derecho/scratch/kheyblom/data/wisosat/zarr/gosat/`: geolocation
  (time, lat, lon), `pressure`, and 10 variable stores including the kernel,
  the a priori and the pressure weight. 8,856,028 obs. The geolocation store
  was rebuilt without `pressure` on 2026-10-19; its backup is deleted.
  Re-checked complete 2026-10-22 (every store: all 4,498 raw days, one obs
  axis, tag at the tip).
- **GOSAT-2 is finished: 12 stores, all finalized** 2026-10-22, tag
  `v3.0.1-verified-20261022`, in
  `/glade/derecho/scratch/kheyblom/data/wisosat/zarr/gosat2/` (163 MB): the
  same 12 stores as GOSAT, 1,010 days, 1,620,006 obs, 478 checks and 0
  failures. Read with the GOSAT reader and key through the config's `source`;
  `platform: GOSAT2` checked on every file (both user-approved 2026-10-22; the
  51 missing days declared as found). Run log: TESTING.md, GOSAT-2 run log.
- **SCIAMACHY is finished: 22 stores, all finalized** 2026-10-22, tag
  `v8.1-verified-20261022`, in
  `/glade/derecho/scratch/kheyblom/data/wisosat/zarr/sciamachy/` (87.5 GiB):
  geolocation (with corners), the 5 core stores (no δD is published), 10
  filter and TROPOMI-aligned stores, 5 model-comparison stores and
  `pressure`. 41,616 orbits, 78,666,297 obs, 879 checks and 0 failures.
  - Decisions and evidence: `docs/products/sciamachy.md` (Production subset,
    P1-P6; issues S1-S11). Audit, bench and run: TESTING.md finding 13, Tier
    2c (finding 14) and the SCIAMACHY run log.
  - Two defects left out by `declared_rows_left_out`: S8, orbit 15838's
    repeats; S9, 45262's 32 overlap rows, **a one-time exception** to
    keeping every observation.
  - Shared code added for it: declared rows, a reader `COVERAGE_FREQUENCY`
    (monthly for SCIAMACHY), and `ChunkSpans` in the verifier, which cut
    its CPU ~10x on small granules (finding 14).
- **The cross-product naming pass is done** (task 7, steps 1-2):
  `docs/model-comparison-naming.md` (N1-N18); rows in style_guides
  `a585066`, `fee64ec`, `65ac688` (the `pressure` row and rule).
- **Compute used so far:** TROPOMI ~380 core-hours for the 19 stores, ~835
  for the 6 model-comparison stores (benches and diagnostic ~19, production
  ~815, the overrun approved by the user); GOSAT ~0.5; GOSAT-2 ~0.2;
  SCIAMACHY ~8 (audit ~0.8, two benches ~1.2, production ~5.8); AIRS v1
  ~6.6 (audit ~1, benches ~0.1, production ~5.5); CrIS v1 ~5.3 (audit
  ~0.6, bench ~0.5, production ~4.2); TROPESS v2 so far ~1 (audit and level
  scan ~0.4, bench ~0.6).

## Next: candidates (ask the user which)

The data-lake home for finished stores is not a candidate: the user will say
when it is time (2026-10-22).

1. **The other products** (task 6): TROPESS v2 (next, see above), IASI,
   TES. Each gets a reader at fixture level first, then bench, then
   production. Their open issues are under Open items. TES and IASI need
   multi-array variable stores in the shared code (N18) for their kernels.
   AIRS v1 and CrIS v1 are finished.
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
  `/glade/derecho/scratch/kheyblom/data/wisosat_bench/` (25 bench stores of
  2020-07, roughly 280 GiB with the 2-D stores' superseded shards) and
  `wisosat_fixture/` (rebuilt by the test).
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
    `ln(vmr)^2`. Confirm the TROPESS kernel's row/column convention.
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
- **Downloads are done outside this repo** (2026-10-22): a separate
  data-access session fetches raw data; this repo only reads it.
