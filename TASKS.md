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


# 5. Create a testing plan for the codebase
Develop a plan to test this codebase so that we know that it works before we move to production runs.

Progress: TESTING.md written 2026-10-14. Tiers 0-1 pass (fixtures for TROPOMI and GOSAT). The Tier 2 TROPOMI bench is staged; its job commands await approval. Found the TROPOMI download incomplete (339 orbits, 12 days); see docs/products/tropomi.md (T7). Re-downloaded and fully audited 2026-10-16. Tier 2 bench passed 2026-10-16 (build 189 s, verify 328 s, 0 failures); see TESTING.md. Scale settings decided 2026-10-16; the Tier 3 TROPOMI chain is planned in TESTING.md and awaits approval.

# 6. Production runs: create the final prooduct zarr stores.
One product at a time, starting with TROPOMI.


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
