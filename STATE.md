# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Where we are (2026-10-19)

- **Tasks 1-5 are done.** The shared pipeline (`CLAUDE.md`, Layout) and the
  testing tiers (`TESTING.md`) are in place. The fixture test passes 46 cases
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
- **GOSAT production is built and verified** (2026-10-19; jobs 7874257 and
  7874258, ~0.2 core-hours).
  - 11 stores in `/glade/derecho/scratch/kheyblom/data/wisosat/zarr/gosat/`:
    the geolocation store, with `pressure`, and 10 variable stores, including
    the kernel, the a priori and the pressure weight.
  - 8,856,028 observations, 946 MB. 359 checks, 0 failures.
  - **Not yet finalized.** Run `--attrs` then `--tag
    v3.0.1-verified-20261019`, each as a dry run and then with `--apply` on
    the user's sign-off (commands in CLAUDE.md). `--status` shows nothing
    unreachable, so no `--gc` is needed. The run log is in TESTING.md,
    Tier 3. Check `--status` first: this may already be done.

## Next task: TROPOMI's model-comparison stores (TASKS.md task 7, step 3)

**Read first:**
- `docs/products/tropomi.md`, sections Model-comparison variables (the
  mapping) and Variable inventory (the size estimates and how they were
  measured);
- `docs/model-comparison-naming.md`, the rules (N1-N18);
- TESTING.md, Tier 3, "Additions decided 2026-10-18". It is the corner
  rebuild, the precedent for this task's geolocation step.

**What to build** (names, units and conversions in `tropomi.md`):
- 5 variable stores on `layer` (50), all float32:
  - the H2O and HDO column kernels;
  - the H2O and HDO a priori partial columns (x 1e4 / N_A);
  - `dry_air_partial_column` (x 1e4 / N_A).
- `pressure` on `level` (51) in the geolocation store, in Pa as published
  (no conversion).
- Set `VERTICAL_ORDER = 'top_first'` in `products/tropomi.py`: level 0 is
  0 Pa. `DIMENSION_RENAMES` needs nothing, since `nlayer`/`nlevel` lose
  their `n`.
- **~29 TiB estimated**, against 1.8 TiB for the 19 existing stores.

**What GOSAT already proved in the shared code** (2026-10-19, `8398108`):
- 2-D variable stores;
- a coordinate with a unit conversion;
- `vertical_order`, set by the build and checked by the verifier;
- the chunk rule. 50 layers take 131,072 obs per chunk, and 51 levels the
  same (25.5 MiB).

TROPOMI needs no new shared code, unless the steps below find some.

**Steps, in order:**
1. **Measure kernel compression** with a scratch script on a login node,
   reusing the Variable inventory's method (one orbit, in-memory zarr,
   zstd). The 29 TiB is an estimate; the kernels may compress better.
   Report it to the user before going on.
2. **Key rows and configs.** Add the 5 rows and the `pressure` coordinate
   row to `nomenclature-key_tropomi.md` (the rows exist in style_guides
   `fee64ec`). Add the 5 variables to all three TROPOMI configs.
   - **Fill:** SRON declares none, so the new float sources will hold the
     netCDF default 9.96921e+36 where unwritten. Declare each in
     `source_fill_values` only where it occurs: the verifier fails a
     declared value that never occurs over the record, and fails an
     undeclared default fill.
   - **Rows left out:** `meteo/*` may be written on rows that have no
     position (the 6 rows of finding 10 hold SZA). If so the build fails,
     with "cannot be left out". Check, then ask the user before adding to
     `allowed_on_rows_left_out`.
3. **Fixture:** `uv run python validation/stage_tropomi.py --restage`. It
   copies only the sources in the key, so the new ones arrive only on a
   restage. Then run the pipeline test (both products).
4. **Decide with the user how `pressure` reaches the geolocation store.**
   A finalized store's index is complete, so a normal build writes nothing
   to it, and the verifier would fail it for a missing array.
   - **The precedent** (corners, 2026-10-18): move the geolocation store
     aside as a backup, and rebuild it from granule 0 in the same pass as
     the new stores. The 16 old variable stores are no-ops. Then verify the
     new stores, run `--phases structure,index` over all of them, finalize
     the new ones, and delete the backup only with approval.
   - **The alternative:** a shared path that writes one new array onto a
     complete store. That is new code, so the user decides.
5. **Bench** (`config_zarr_bench.yaml`, 2020-07, 390 orbits), then production.
   Show every job and its cost first.
   - **Memory is the main risk.** At 60 granules per commit, the new arrays
     are ~1 GB per orbit (~850k obs x 301 values x 4 B), so ~60 GB a batch
     with two in flight. Develop has given 32 GB. The bench must set
     `granules_per_commit` (per config; condition 3) or the queue (main has
     the whole node and 12 h).
   - **Time:** the corner rebuild was ~3.7 h to build and ~3.3 h to verify
     on develop. ~29 TiB of new data will take several times longer. Builds
     resume, so chain them `afterany`. The verifier does not resume, and
     cannot split one store. A geolocation verify that includes `pressure`
     may not fit develop's 6 h, so the bench must measure it.
   - **Finalize:** the new stores, and the rebuilt geolocation store, get
     the tag `v8.1-verified-<date>`.

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

- **The data-lake home of the TROPOMI stores** is undecided. Scratch is
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
- **Filtering guidance** in the metadata is Table 1 in full, plus the
  inferred reduced chi-squared.
- **Naming rule:** the quantity first, then qualifiers general to specific.
  Established terms stay whole; unitless quantities use `unitless`.

## Open questions

- **TROPOMI `pressure`:** rebuild the geolocation store, as with the corners,
  or write one new array onto the complete store (step 4 above).
- **TROPOMI scale for the 2-D stores:** `granules_per_commit` and the queue,
  from the bench (step 5).
