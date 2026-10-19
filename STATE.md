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
- **GOSAT** has a reader and a fixture only, for the 1-D subset. Next it
  gains its model-comparison variables, then goes to production.

## Next task: the model-comparison stores (TASKS.md task 7, step 3)

**The naming pass is done (2026-10-19).** Every product's kernels, priors,
dry-air columns, covariances and pressure grid are named in
the docs. Read both before writing any key rows:
- each product's sources, names, units, dims, conversions and stores are in
  the Model-comparison variables section of `docs/products/<product>.md`;
- the grammar, the layout rules and the decisions (N1-N18) are in
  `docs/model-comparison-naming.md`.

**What it settled, in short:**
- `pressure` is a geolocation coordinate, in Pa.
- Vertical dims are `level` / `layer`; a matrix's second axis is `level_2`.
- Each source keeps its vertical order, recorded in `vertical_order`.
- A matrix published in pieces is one store (TES, IASI). That needs
  multi-array variable stores in the shared code, which does not exist yet.
- Left out: GOSAT `dry_column` (held, G7) and the TROPESS ratio covariance
  (R11).

**Next, in order:**
1. GOSAT: add the kernel, prior, pressure weight and pressure rows to its
   key and config, then extend the reader and fixture. Then fixture, bench
   and production, as for TROPOMI.
   - `xh2o_averaging_kernel` and `h2o_profile_apriori` are in the H2O file
     only. They are absent (NaN) on DED-only soundings, like the other H2O
     variables.
   - `pressure_levels` and `pressure_weight` are in both files, and
     identical where both hold a sounding. So `pressure` is written for
     every sounding.
   - **The shared code is already generic over secondary dims.**
     `squeeze_dims` renames them, `obs_chunk` sizes them, and the absent
     mask broadcasts over them. The corners proved this, but only in the
     geolocation store, so the GOSAT fixture is the first test of a 2-D
     variable store.
   - **To add:**
     - `pressure` in the coordinate key. Check that the coordinate
       table can carry a numeric conversion: hPa x 100 to Pa;
     - the `vertical_order` attribute (`surface_first` for GOSAT).
   - Test every product's fixture after each shared change.
2. TROPOMI: measure kernel compression first (scratch script, login node).
   Then build 5 new stores, plus `pressure` in the geolocation store
   (`top_first`). Show the user the job and its cost first: ~29 TiB
   estimated.
3. Later, for TES and IASI: multi-array variable stores (N18), and the
   per-product open issues listed under Other open items.

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
- **Finalize is typed by hand**, one action per call (`CLAUDE.md`). `--gc
  --apply` is irreversible and needs approval. So does any `rm -rf`.
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

- None at present. The pressure coordinate question was settled by N3/N4.
