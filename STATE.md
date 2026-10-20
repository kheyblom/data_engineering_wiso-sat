# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Where we are (2026-10-19, updated after the TROPOMI 2-D bench)

- **Tasks 1-5 are done.** The shared pipeline (`CLAUDE.md`, Layout) and the
  testing tiers (`TESTING.md`) are in place. The fixture test passes 59 cases
  over TROPOMI and GOSAT.
- **TROPOMI production is finished** (task 6, first product).
  - 19 stores in `/glade/derecho/scratch/kheyblom/data/wisosat/zarr/tropomi/`,
    all finalized under tag `v8.1-verified-20261018`:
    - the geolocation store: time, lat, lon and the pixel corners;
    - 16 variable stores;
    - `scanline_index` and `ground_pixel_index`.
  - 32,657,526,234 observations, ~1.8 TiB.
  - The run log (every job, finding and decision) is in `TESTING.md`,
    Tier 3; findings 9-11 come from it. Product facts and the variable
    inventory are in `docs/products/tropomi.md`.
- **The cross-product naming pass is done** (task 7, steps 1-2,
  2026-10-19). Its rows and rules are pushed: style_guides `a585066`,
  `fee64ec`.
- **GOSAT production is finished** (2026-10-19; jobs 7874257 and 7874258,
  ~0.2 core-hours), and **reworked** the same day (jobs 7874907, 7874909,
  7874913, ~0.25 core-hours) so `pressure` is its own store.
  - 12 stores in `/glade/derecho/scratch/kheyblom/data/wisosat/zarr/gosat/`:
    the geolocation store (time, lat, lon), `pressure`, and 10 variable
    stores, including the kernel, the a priori and the pressure weight.
  - 8,856,028 observations. The rebuilt pair: 102 checks, 0 failures; the
    shared index over all 12: 373 checks, 0 failures.
  - **All 12 finalized** with the user's sign-off, tag
    `v3.0.1-verified-20261019`; every store reports "remaining nothing,
    finalized". Run logs in TESTING.md, Tier 3.
  - **The old geolocation store is backed up** in
    `/glade/derecho/scratch/kheyblom/data/wisosat/zarr/gosat_backup_20261019/`.
    Delete it only with the user's approval.
  - Its data-lake home is undecided, as for TROPOMI.

## Next task: TROPOMI's model-comparison stores (TASKS.md task 7, step 3)

**Read first:**
- `docs/products/tropomi.md`, sections Model-comparison variables (the
  mapping) and Variable inventory (the size estimates and how they were
  measured);
- `docs/model-comparison-naming.md`, the rules (N1-N18);
- TESTING.md, Tier 3, "Additions decided 2026-10-18". It is the corner
  rebuild, the precedent for this task's geolocation step.

**What to build** (names, units and conversions in `tropomi.md`):
- 6 variable stores, all float32:
  - on `layer` (50): the H2O and HDO column kernels, the H2O and HDO a priori
    partial columns (x 1e4 / N_A), and `dry_air_partial_column`
    (x 1e4 / N_A);
  - on `level` (51): `pressure`, in Pa as published. **Its own store, not in
    the geolocation store** (user decision 2026-10-19): it would have made
    that store ~6x larger (0.68 to ~4 TiB) for users who need only position
    and time. So the finalized geolocation store is not rebuilt.
- **~19 TiB estimated** with the chosen codec (~20-21 TiB on disk), against
  1.8 TiB for the 19 existing stores.

**Steps 1-3 are done (2026-10-19):**
1. **Compression measured** on orbits 14069 and 32414: ~29 TiB with the
   default zstd, ~19 TiB with blosc zstd 5 + byte shuffle (lossless). **The
   user approved blosc** for the six new arrays only. That is new shared
   code: the config's `compression` block, applied in `build_encoding`, and
   checked per array by the verifier (`compressor_matches`). Every other
   array keeps the default, so the finalized stores are unchanged; GOSAT's
   pass `--phases structure` with the new check (323 checks).
2. **Key rows, configs and reader.** The 5 rows, the `pressure` coordinate
   row and `VERTICAL_ORDER = 'top_first'` are in. All three configs list the
   5 variables and the `compression` block.
   - **Fill (scanned 2026-10-19, all 77 partial files, with the reader's own
     row rule):** all six sources hold fill on kept rows, always whole rows.
     Production and fixture declare all six. The bench declares only the
     kernels, since the others hold fill only in partial files and 2020 has
     none.
   - **No new source is written on a row left out**, including finding
     10's six rows, so `allowed_on_rows_left_out` is unchanged.
   - **T22 (record only):** pressure near the North Pole reaches 1.2e8 Pa
     in 4 pixels of orbit 14069; stored as published.
3. **Fixture restaged; the test passes 50 cases** (4 new: the verifier fails
   on a codec the config does not set, and the build refuses compression of
   an unknown array, for each product).

4. **Done (2026-10-19): `pressure` is a variable store in every product**
   (style_guides `65ac688`; repo `afbbac2`). TROPOMI's geolocation store is
   not rebuilt; GOSAT's was (above).
5. **Done (2026-10-19): shards and snapshot expiry** (user chose option C of
   the file-count analysis; its full text is in this file at `5261f04`):
   - `compression.shard_obs` packs the six arrays' 131,072-obs chunks into
     shards of 4,194,304 obs (= `chunks.obs`): ~7,800 files per store
     rather than ~249,000. The verifier checks the shard shape.
   - Each commit rewrites the partly filled last shard (~2.5 /
     `granules_per_commit` of the bytes stay superseded until expiry; ~12%
     at 20). `finalize --expire`, after `--attrs` and `--tag`, drops the
     build snapshots of a sharded store; `--gc` then deletes them. It
     refuses an untagged store, and `--status` lists it as remaining.
   - The test passes 59 cases.
6. **Bench done (2026-10-19; TESTING.md Tier 2b, finding 12):** build
   7875114 (37 min) and verify 7875115 (46 min, **313 checks, 0 failures**),
   11.2 core-hours. 19.9 TiB projected; superseded shards 11.7%; peak memory
   56 GiB build, 65 GiB verify.
   - **At bench rates production would cost ~1,050 core-hours** (build 469,
     verify 583), and the verifier cannot run it: no resume, no split of a
     store, and it always re-verifies geolocation (~73 h for one run).
   - **Finding 12:** the build uses ~4x the CPU its stages account for
     (~38 s per orbit against ~11 s profiled). Kernel time was 3x user time
     in a login-node probe: memory churn suspected, possibly
     `MALLOC_TRIM_THRESHOLD_=0`. Since `b94038c` runs log their CPU split.
7. **Cost work (2026-10-19, all approved by the user):**
   - **Diagnostic job 7877379** (~2 core-hours): `MALLOC_TRIM_THRESHOLD_=0`
     cost ~22% of the build's CPU; the rest of the excess was shipping ~1.1
     GB per orbit between processes (TESTING.md finding 12).
   - **Fixed in code:** no `MALLOC_TRIM_THRESHOLD_`; `own_process_stores`
     for the six; the verifier scans (group x granule range) in parallel,
     returning counts only, and `--stores` no longer re-compares
     geolocation. Test: 63 cases.
   - **Re-bench done** (jobs 7877506, 7877507; TESTING.md Tier 2b): 297
     checks, 0 failures; 5.9 core-hours against 11.2. **Production at these
     rates: ~555 core-hours** (build ~295, verify ~262), against ~1,050.
   - **Awaiting the user:** production now at ~555, or one more diagnostic
     (~1-2 core-hours) on the remaining kernel time (page faults on
     multi-GB arrays; buffer reuse or huge pages), maybe toward 350-450.
     Production should request ~128 GB at 10 granules per commit.
8. **Production**, chained `afterany`; finalize the 6 stores with
   `v8.1-verified-<date>`, then `--expire` and `--gc`.

**Later:** multi-array variable stores for TES and IASI (N18), and the
per-product open issues under Other open items.

### History of the naming pass

- **The proposal:** four review rounds on 2026-10-19. The full discussion is
  in the git history of `docs/model-comparison-naming.md`, up to `e87a8e1`.
  The file is now a short reference.
- **Rows:** 48 new and 2 renamed in style_guides `fee64ec` and `a585066`.
- **The rename:** `water_vapor_column_mole_fraction_dry_air[_standard_error]`
  became `water_vapor_column_h2o_mole_fraction_dry_air[_standard_error]`.
  The GOSAT key and configs follow it.

## Other open items

- **The data-lake home of the TROPOMI and GOSAT stores** is undecided. Scratch is
  purged, so ask the user before moving them.
- **GOSAT `dry_column`** is held (naming pass N11): it is ~1/4 of the
  hydrostatic dry column, with no area in its unit (`gosat.md` G7). Resolve
  it from the GHG-CCI PSD v3, or by asking IUP, then add it as
  `dry_air_partial_column`.
- **GOSAT-2 configs** (`product: gosat2`) need a small shared change, so the
  reader and key can be named apart from the product.
- **The other products** (task 6): SCIAMACHY, AIRS, CrIS, IASI, TES. Each
  gets a reader at fixture level first.
- **Open issues found in the naming pass**, to settle when each reader is
  built. The full list for each product is in the Known data issues table
  of `docs/products/<product>.md`.
  - **IASI I7 (blocks the store names):** the processor version changes
    in 2019, from 030201 to 030300, and MetOp-C joins (AB to ABC). Decide
    the store version with the user.
  - **IASI I6:** the record maximum of `wv_avk_rank`, and of
    `wv_xavkat_rank`, for the padding (N10). It is a header scan of
    4,568 files.
  - **IASI I8:** declare `K-1` on `musica_wvp_xavkat_val` (approved, N17).
  - **TROPESS R10:** FS `pressure` level 0 is -999 in R1p17 and R1p20,
    but not in R1p11.
  - **TROPESS R11:** `observation_error` is left out (approved, N16).
    Reporting it to the TROPESS team is optional.
  - **TROPESS R12:** confirm that `observation_error_h2o` is 1-sigma.
  - **TES:** `ObservationErrorCovariance` has no `Units`; declare
    `ln(vmr)^2`. Confirm the TROPESS kernel's row/column convention.
- **Elsewhere:** GLEAM and MSWEP carry a deferred task 2 (add `cdm_data_type:
  Grid`; `standard_name` from the source only).

## How we work (user preferences, 2026-10-14 to 10-18)

- **Show every batch job before submitting it**, with its cost; wait for
  approval. Go tiny fixture, then bench, then production. The allocation is
  finite: TROPOMI used ~380 core-hours in all.
- **Builds start only from a clean commit.** The build and the wrapper both
  refuse a dirty tree. Commit before submitting, and keep the tree clean
  until each build job has started.
- **Edits to style_guides** are shown to the user before commit. They review
  in place, with `#@CLAUDE` comments.
- **Proposals for the user** go in a repo doc, which they review in place
  with `#@CLAUDE` comments. Answer each comment in the doc, then remove its
  marker. Example: `docs/model-comparison-naming.md` up to `e87a8e1`. Once
  agreed, move the result to where it is used and keep the discussion in
  git.
- **Claude runs finalize, one action per call; the user signs off on each**
  (2026-10-19; `CLAUDE.md`). Show the dry run, then `--apply` on approval.
  `--gc --apply` is irreversible. Any `rm -rf` needs approval too.
  - The auto-mode permission check refused finalize on 2026-10-19, even a
    dry run, so the user is adding a permission rule for it. If a call is
    still refused, list the command for the user, and do not work around
    the check.
- **Long or irreversible login-node steps** run detached (`setsid nohup`),
  so a dropped connection cannot stop them.
- **Verify only new or changed stores.** A cheap `--phases structure,index`
  run over every store then confirms the shared index.

## Things the next session needs to know

- **PBS writes a job's `.OU` file while it runs** (`Keep_Files = od`). The
  file's existence does not mean the job ended. Check `job_state` with
  `qstat -f <id>.desched1`, and `Exit_status` with `qstat -xf`. Plain
  `qstat -u $USER` may not list held jobs. Watch a chain's first job until
  it commits, and delete the rest if it dies (`afterany` runs them anyway).
- **Commands.** Run from the repo root:
  - test: `TMPDIR=/glade/derecho/scratch/$USER/tmp uv run python validation/test_pipeline.py`;
  - batch: `bash -lc 'cd ~/work/data_engineering/data_engineering_wiso-sat && CONFIG=... [VERIFY=1] [AFTER=<jobid>] QUEUE=develop NCPUS=8 MEM=32GB WALLTIME=06:00:00 ./submit_wisosat_zarr.sh'`.
    Tool shells do not read `~/.bashrc`, so `bash -lc` is needed for
    `PBS_ACCOUNT`.
- **Develop queue:** 6 h maximum walltime. 8 cores and 32 GB suit TROPOMI.
  A TROPOMI build is ~4 h and one verify run ~3.5-4 h.
- **Scratch is purged.** The audit output, the fixture and the bench under
  `/glade/derecho/scratch/kheyblom/data/` can be thrown away or
  reproduced. The durable record is in the docs.
- **The bench stores are throwaway.** Delete one before re-running it:
  builds resume, so a complete store is a silent no-op.
- **TROPOMI's history attributes needed help**, and are written now:
  - commits from before the revision stamp took
    `--build-revisions 7220460@0,24186fe@7020`;
  - the corner build took `--dirty-notes`. The exact text is in
    `logs/finalize_wisosat_zarr_tropomi.log`.

## Decisions in force (user)

- **Store names:** `wisosat.<product>.<version>.inst.native_swath.<variable>.zarr`.
  The version comes from the files' attributes, with no product token
  (2026-10-14).
- **One pass, many stores:** each granule is read once and written to every
  store of a config (2026-10-14).
- **GOSAT DED and H2O are merged into one product** per day (2026-10-14).
- **An observation is a row with time, lat and lon all written**, for every
  product (2026-10-16, extended 2026-10-17).
  - Other rows are left out, checked; a row left out may hold values only
    in `allowed_on_rows_left_out`.
  - `granule_source_rows` keeps each file's row count. Corrupt upstream
    files are declared and left out.
- **The TROPOMI subset:**
  - the core 7, plus the 9 inputs to the Schneider et al. (2022) Table 1
    filters;
  - `scanline_index` and `ground_pixel_index`, SRON's values as written;
  - the pixel corners, in the geolocation store (2026-10-18).
- **Model-comparison naming** (2026-10-19; full record in
  `docs/model-comparison-naming.md`):
  - the grammar is `<quantity>[_<vertical form>]_<species>[_<basis>][_<role>]`.
    The species is always explicit, there is no `profile` token, and
    `partial_column` is used per layer;
  - `pressure` is a geolocation coordinate in Pa, with no nomenclature row;
  - vertical dims are `level` and `layer`, and a matrix's second axis is
    `level_2` (rows retrieved, columns true). Each source keeps its
    vertical order, recorded in a `vertical_order` attribute;
  - ln-space kernels end in `_log`, and an off-diagonal block ends in
    `_cross_<quantity>`. Both cross blocks are kept, even where one is the
    exact transpose of the other (the TES covariances);
  - a matrix published in pieces is one store, named for the matrix, with
    each piece an array: the TES kernel and covariances, the IASI SVDs;
  - IASI SVD vectors are split per proxy state, with `rank` padded to the
    record maximum with NaN;
  - left out: GOSAT `dry_column` (held until its unit is resolved) and
    the TROPESS ratio covariance (invalid as published).
- **Chunks:** `chunks.obs` 4,194,304, halved per array until it fits 40 MiB.
  That keeps every store's chunk boundaries aligned (2026-10-18).
- **Scale (TROPOMI):** 8 workers, 60 granules per commit, develop queue
  (2026-10-16).
- **Compression (2026-10-19):** blosc zstd 5 + byte shuffle for TROPOMI's six
  model-comparison arrays, set per array in config. Everything else keeps
  zarr's default zstd; the finalized stores are not rebuilt to match.
- **Shards and expiry (2026-10-19):** the same six arrays are sharded at
  4,194,304 obs, and their stores' build snapshots are expired at
  finalization so `--gc` reclaims superseded shards.
- **Pressure (2026-10-19, revises N3):** a profile product's pressure grid
  is a variable store named `pressure`, not part of the geolocation store,
  in every product. GOSAT is reworked to match.
- **Filtering guidance** in the metadata is Table 1 in full, plus the
  inferred reduced chi-squared.
- **Naming rule:** the quantity first, then qualifiers general to specific.
  Established terms stay whole; unitless quantities use `unitless`.

## Open questions

- **TROPOMI 2-D production cost:** ~1,050 core-hours at bench rates; the
  diagnostic job and the verifier split decide the real figure (step 7).
