We need to build one codebase that prepares zarr stores for all of the WISO-SAT Level 2 data products (TROPOMI, SCIAMACHY, GOSAT, GOSAT-2, AIRS, CrIS, IASI, TES), with separate configs and nomenclature keys for each product. We design around TROPOMI first, then extend to the other products. (Restructured 2026-10-14 from a TROPOMI-only codebase; approved by the user.)

Raw data is located here: @/glade/u/home/kheyblom/scratch/data/wisosat/raw/
We will create one zarr store per variable covering the full record of each product (changed from one store per day, 2026-10-14). Level 2 data only.

# 1. init CLAUDE.md for the codebase [COMPLETED 2026-10-13]
Create a CLAUDE.md for this codebase. (Moved to the repo root 2026-10-14.)

# 2. init a git repo [COMPLETED 2026-10-13]
Check if a repo already exists for this codebase (data_engineering_wiso-sat). If the repo does not exist, initalize a github repo and connect to the remote (see general notes).

# 3. Collaborate to update style guides [COMPLETED 2026-10-14]
The data is different the previous data engineering codebases that have been built. Previous projects have only dealt with gridded datasets. This is a level 2 satellite retrieval product. Thus, we will likely need to work on creating the standards that will go into updating the style guide.

This data also uses variables that are not in the style guide. We will work together to add all of the new variables that we need to.

Progress: Level 2 rules written into the style guide and pushed 2026-10-14 (style_guides `7bc9f72`, `7137951`). TROPOMI production subset chosen and its 16 rows added to `nomenclature_data.md` 2026-10-14 (style_guides `fd94a93`; see `docs/products/tropomi.md`). Other products add their rows when their readers are built.

# 4. Plan and build the codebase [COMPLETED 2026-10-14]
I want you to build the codebase. Design the codebase to be consistent with the other data_engineering codebases (see general notes).

## Design notes:
- The environment is already created. See @./pyproject.toml.
- Make sure to follow the style guides outlined in @/glade/u/home/kheyblom/work/style_guides.
- Follow the structure and style in the past data_engineering products: @/glade/u/home/kheyblom/work/data_engineering. Make sure that we are consistent with each of those.
- We will only produce zarr stores for a subset of the available variables. The config needs to be flexible to specify which variables we want to run the stores for during a production run.
- One codebase for all products: a reader per product (`products/<product>.py`), with configs and nomenclature keys per product. Everything downstream of reading a source file is shared. Agreed conditions (2026-10-14):
    - before any TROPOMI production run, build a second, deliberately different product reader at fixture level only, to prove the shared interface;
    - every product keeps a tiny fixture, and the shared end-to-end test runs all of them after any change to shared code;
    - scale settings (batching, caches, memory) live in per-product config, not code.

Progress: Shared pipeline, TROPOMI reader, key, configs and fixture built 2026-10-14; the end-to-end fixture test passes (17 cases). Store naming and the one-pass build decided 2026-10-14. Second reader (GOSAT, DED and H2O merged per day, approved 2026-10-14) built at fixture level 2026-10-14; the test passes 34 cases over both products. The four new nomenclature rows were reviewed and committed (style_guides `3966e69`), which closes the task.


# 5. Create a testing plan for the codebase [COMPLETED 2026-10-18]
Develop a plan to test this codebase so that we know that it works before we move to production runs.

Progress:
- TESTING.md written 2026-10-14. Tiers 0-1 (fixtures for TROPOMI and GOSAT)
  pass 46 cases.
- The TROPOMI download was found incomplete (339 orbits, 12 days); see
  docs/products/tropomi.md (T7). It was re-downloaded and fully audited on
  2026-10-16.
- The Tier 2 bench passed 2026-10-16.
- Tier 3, TROPOMI production, ran 2026-10-16 to 10-18; its findings are 9-11.
- The plan stands for every later product: fixture, then bench, then
  production.

# 6. Production runs: create the final prooduct zarr stores.
One product at a time, starting with TROPOMI.

Progress: TROPOMI production built, verified and finalized on 2026-10-18.
- 17 stores, 32,657,526,234 observations, 1.3 TiB. Two index stores and the
  corners joined on 2026-10-18: 19 stores, ~1.8 TiB.
- Tag `v8.1-verified-20261018`.
- See STATE.md and TESTING.md (Tier 3 run log, findings 9-11).
- Their data-lake location is still to be decided.

SCIAMACHY production built, verified and finalized 2026-10-22: 22 stores,
78,666,297 observations, 0 failures, tag `v8.1-verified-20261022`; two
upstream defects left out by declaration, one a one-time exception approved
by the user (`docs/products/sciamachy.md` P6; TESTING.md, SCIAMACHY run log).

GOSAT-2 production built, verified and finalized 2026-10-22: 12 stores,
1,620,006 observations, 0 failures, tag `v3.0.1-verified-20261022`, read with
the GOSAT reader and key (`source: gosat`; TESTING.md Tier 3).

GOSAT production built, verified and finalized 2026-10-19: 12 stores,
8,856,028 observations, 0 failures, tag `v3.0.1-verified-20261019`
(TESTING.md Tier 3).


# 7. Model-comparison stores: kernels, priors, dry-air columns, pressure grid
Added 2026-10-18 at the user's request, so these are not forgotten. They are
needed eventually; all were deferred from the first production subset.

- **What:** each product's column averaging kernels, a priori profiles,
  dry-air partial columns and pressure grid. For TROPOMI that is six sources,
  each 50 or 51 layers: ~20 TiB with blosc + shuffle (~29 TiB with the
  default codec; measured 2026-10-19).
- **First:** name them in one cross-product naming pass, before GOSAT
  production, which waits on it. The layouts differ by product: column
  kernels, block matrices, log-space ratio kernels, SVD components, priors as
  partial columns or mole fractions.
- **Then:** add the nomenclature rows (user review), and the stores.
  - For TROPOMI they go on the existing obs axis as six new stores, `pressure`
    among them (its own store since 2026-10-19); the existing 19 are not
    rebuilt.
  - Measure the compression first, and settle the 2-D chunking (the obs
    chunk must shrink for 50 layers).
- **Other possible stores** are listed with size estimates in
  `docs/products/tropomi.md` (Variable inventory). Build any of them only when
  asked.
- **Done 2026-10-18:** pixel corners in the geolocation store, and
  `scanline_index` and `ground_pixel_index` stores (19 TROPOMI stores in
  all).
- **Naming pass done 2026-10-19:** `docs/model-comparison-naming.md`
  (N1-N18). 48 rows and the XH2O rename are in style_guides `fee64ec` /
  `a585066`, along with the Level 2 rules for matrix stores and vertical
  dims.
  - GOSAT's kernel, prior, pressure weight and pressure grid: built and
    verified and finalized in production 2026-10-19 with the rest of GOSAT;
    `pressure` moved to its own store the same day.
  - TROPOMI: key rows, configs, compression, shards and `finalize --expire`
    done; bench passed 2026-10-19 (TESTING.md Tier 2b); **production built,
    verified and finalized 2026-10-22** (tag `v8.1-verified-20261022`, 19.6
    TiB, ~815 core-hours).
  - TES and IASI first need multi-array variable stores in the shared
    code (N18).

# General notes:
- all file paths are relative to this TASKS.md file (the repo root).
- the git remote is: https://github.com/kheyblom/data_engineering_wiso-sat.git
- ensure to always use proper git version controlling as changes are made
- use and update a CLAUDE.md that will take this information and effectively and efficiently handle this project. Don't be overly verbose. Keep the CLAUDE.md minimal and clean.
- use information learned in each of the directories in: @/glade/u/home/kheyblom/work/data_engineering and add to this project's CLAUDE.md. Each directory contains a codebase for creating zarr stores for our data lake.
- it is always important to minimize compute costs on derecho. we have a finite allocation and we need to managing our usage.
- keep notes on your current working state. you may lose connection to the HPC system or I may need to start new sessions, so I need you to be able to easily pick up where you left off. Create and use the file STATE.md.
- additional tasks may come up that need to occur between the above tasks. this task list can be flexible, but if substantial changes are need, I need to approve them.
- mark tasks as completed when they are completed
