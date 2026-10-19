# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Where we are (2026-10-18)

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
- **GOSAT** has a reader and a fixture only. Its production waits on the
  naming pass below.

## Next task: the cross-product naming pass (TASKS.md task 7, first step)

**Goal:** canonical names, units and layouts for every product's model
comparison variables, decided once across all products:
- column averaging kernels;
- a priori profiles;
- dry-air partial columns;
- the vertical grid, pressure.

GOSAT production waits on it, so that its kernel and prior stores are built
with the rest.

**Read first:**
- the style guide's Level 2 section. Split stacked arrays into one store per
  quantity, and split matrices into blocks, keeping the cross blocks. The
  vertical grid goes in the geolocation store;
- `nomenclature_data.md`, and the naming rule under Decisions below;
- `docs/l2-survey.md`: units per product, and the kernel and covariance
  layouts (TES 34 x 34 HDO/H2O blocks, TROPESS log-space ratio kernels);
- `docs/products/<product>.md` for each product. TROPOMI has the full
  variable inventory with size estimates (deferred group: ~29 TiB).

**The layouts differ by product:**
- column kernels: TROPOMI, SCIAMACHY, GOSAT;
- block matrices: TES;
- log-space ratio kernels: TROPESS (AIRS, CrIS);
- SVD components: IASI;
- priors as partial columns (TROPOMI) or mole fractions.

A TROPOMI-only name would fix the pattern too early.

**Deliverable, in order:**
1. A proposal for the user. For each product and source: canonical name,
   units, dims, and how it is split.
2. The agreed rows in `nomenclature_data.md`. The user reviews before
   commit (see How we work).
3. Then the stores: GOSAT production; the TROPOMI model-comparison stores on
   the existing obs axis, without rebuilding the 19.
   - Before any 2-D store, measure kernel compression with a scratch script
     (login node, no rows needed).
   - The chunk rule already sizes 2-D arrays: 50 layers take 131,072 obs.

No compute is needed for steps 1-2.

## Other open items

- **The data-lake home of the TROPOMI stores** is undecided. Scratch is
  purged, so ask the user before moving them.
- **GOSAT-2 configs** (`product: gosat2`) need a small shared change, so the
  reader and key can be named apart from the product.
- **The other products** (task 6): SCIAMACHY, AIRS, CrIS, IASI, TES. Each
  gets a reader at fixture level first.
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
- **Kernels, priors, dry-air columns and the pressure grid** wait for the
  naming pass (task 7).
- **Chunks:** `chunks.obs` 4,194,304, halved per array until it fits 40 MiB.
  That keeps every store's chunk boundaries aligned (2026-10-18).
- **Scale (TROPOMI):** 8 workers, 60 granules per commit, develop queue
  (2026-10-16).
- **Filtering guidance** in the metadata is Table 1 in full, plus the
  inferred reduced chi-squared.
- **Naming rule:** the quantity first, then qualifiers general to specific.
  Established terms stay whole; unitless quantities use `unitless`.

## Open questions

- **Coordinate naming in the geolocation store.** `pressure` follows the
  `time`/`lat`/`lon` convention (no nomenclature row) unless the user says
  otherwise. Settle it in the naming pass.
