# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Where we are (2026-10-16)

- **Tasks 1-4 are done.**
  - The shared pipeline is built: TROPOMI reader, GOSAT second reader at
    fixture level, verifier, finalize and batch wrapper.
  - Layout and usage are in `CLAUDE.md`.
- **Task 5 (testing plan) is in progress.** `TESTING.md` holds the tiers and
  findings 1-8.
  - Tiers 0-1 pass: `validation/test_pipeline.py`, 38 cases over TROPOMI and
    GOSAT (~75 s, login node).
  - **Tier 2, the TROPOMI bench, passed on 2026-10-16.** Build 189 s and
    verify 328 s for July 2020 (390 files, 8 workers); 529 checks, 0
    failures. The results, timing breakdown and full-record extrapolation
    are in `TESTING.md` (Tier 2).
- **The TROPOMI raw tree is final and fully audited (2026-10-16).**
  - 38,648 files, 2017-11-08 to 2025-11-29.
  - Every gap and defect is declared in `config/tropomi/config_zarr.yaml`.
  - All facts, issues (T1-T21) and the defect orbit lists are in
    `docs/products/tropomi.md`.
  - Each sensor's doc carries its own **Known data issues** table; add new
    findings there.

## Next (in order)

1. **Tier 3, the TROPOMI production chain, is planned and awaits the user's
   approval.** The commands, the store groups and the costs are in
   `TESTING.md` (Tier 3). Submit nothing until the user says so. The steps:
   - step 0: a minutes-long check, on the bench stores, that `VERIFY_ARGS`
     survives `qsub -v`;
   - B1 and B2: the build, then a resume guard;
   - V1-V3: verification split by `--stores`, all chained `afterany`;
   - then `finalize`: `--status`, `--attrs`, `--tag`, and `--gc` (dry run
     first).

   **Submitted 2026-10-16 with the user's approval:**
   - step 0, job 7840965: **passed**. Both `--stores` names arrived whole
     through `qsub -v`.
   - **First chain (7840968-72) failed at once.** B1 segfaulted (exit 139)
     listing granules: netCDF4/HDF5 crashes opening the declared-unreadable
     orbit 3335 instead of raising. `afterany` then ran B2 and V1-V3
     through, all dead within a minute (~0.3 core-hours). The open probe now
     runs in a child process (commit `7220460`, test 38/38).
   - **The chain was resubmitted the same day, with the same commands.** Each
     job is `afterany` the one before:

     | job | id |
     | --- | --- |
     | B1 | 7841000 |
     | B2 | 7841009 |
     | V1 | 7841010 |
     | V2 | 7841011 |
     | V3 | 7841012 |

     The first B2 and V1-V3 (7841001-04) were deleted by mistake, while B1
     was running, and resubmitted unchanged.

   - **B1 progress check, 13:50 MDT:** batch 277 of 645, no errors.
     - Listing found 38,645 granules, with 77 missing days as declared.
     - Batches started at ~20 s and are now ~26 s. Expected end ~16:30 MDT,
       ~4.4 h in all.
     - Memory: PBS reports ~32 GiB because it counts the file cache. The
       processes hold ~8.3 GiB: main 7.1 GiB, workers 0.1-0.27 GiB.
     - The whole chain should end ~02:00-03:00 MDT on 2026-10-17.
   - **The build is done.**
     - B1 ran 4 h 24 min, exit 0, all 645 batches. Peak memory was 11.04 GiB
       main and 0.40 GiB per worker.
     - B2 was a no-op ("every store is already complete"), exit 0.
     - The stores hold 32,657,526,240 obs and 1.3 TiB on disk.
   - **V1 started 16:27.** Its structure and index phases pass: 38,645
     granules match the raw listing, and every store's obs length agrees. The
     values phase runs at ~16 s per 60 granules, so V1 should end ~19:30-20:00.
   - **To check on resume:**
     - B1's `Exit_status` and its `peak memory` / `done :-)` lines;
     - that B2 was a no-op;
     - then each verify run's `stores verified` line and its stores.

   - **The audit opened every file with h5py, not netCDF4.** Another file
     could still crash a build worker. The build would then fail loudly and
     resume from its last commit.
   - Logs: `logs/<id>.desched1.OU`, `logs/wisosat_zarr_tropomi.log` and
     `logs/verify_wisosat_zarr_tropomi.log`.
   - When V3 ends, check that each run says `stores verified` and covers its
     stores, then run `finalize --status`.
2. **Scale settings, decided with the user on 2026-10-16** and set in
   `config/tropomi/config_zarr.yaml`:
   - 8 workers: the build is write-bound;
   - `chunks.obs` 4,194,304;
   - `granules_per_commit` 60, to cut commits and objects per store; history
     is kept;
   - the develop queue: 8 cores, 32 GB, 6 h limit (NCAR docs), at ~125
     core-hours estimated, against ~670+ on main.
3. Later, not blocking TROPOMI:
   - the cross-product naming pass for kernels, priors and dry-air columns,
     which GOSAT production waits on;
   - GOSAT-2 configs (`product: gosat2`), which need a small shared change so
     the reader and key can be named apart from the product;
   - task 6, the other products.

## Things the next session needs to know

- **PBS writes a job's `.OU` file while it runs** (`Keep_Files = od`).
  The file's existence does not mean the job ended. Check `job_state` with
  `qstat -f <id>.desched1`, and `Exit_status` with `qstat -xf`. Plain
  `qstat -u $USER` may not list held jobs.
- **Commands.** Run from the repo root:
  - test: `TMPDIR=/glade/derecho/scratch/$USER/tmp uv run python validation/test_pipeline.py`;
  - batch: `bash -lc 'cd ~/work/data_engineering/data_engineering_wiso-sat && CONFIG=... [VERIFY=1] [AFTER=<jobid>] QUEUE=develop NCPUS=8 MEM=32GB WALLTIME=01:00:00 ./submit_wisosat_zarr.sh'`.
    Tool shells do not read `~/.bashrc`, so `bash -lc` is needed for
    `PBS_ACCOUNT`.
- **A develop node reports 64 cpus to `os.sched_getaffinity` even when 32
  are requested** (seen in the audit job). The wrapper only checks that
  `num_workers` <= cpus available; the config sets the real count.
- **Scratch is purged.** These are disposable or reproducible: the audit
  output at `/glade/derecho/scratch/kheyblom/data/wisosat/audit/`, the
  fixture at `.../data/wisosat_fixture/` and the bench at
  `.../data/wisosat_bench/`. The durable record is in the docs (defect lists
  in `tropomi.md`).
- **The bench stores are throwaway.** Delete them before re-running the
  bench: builds resume, so a complete store is a silent no-op.
- **Elsewhere:** GLEAM and MSWEP carry a deferred task 2 (add `cdm_data_type:
  Grid`; `standard_name` from the source only). Both are pushed.

## Decisions in force (user)

- **Store names:**
  - `wisosat.<product>.<version>.inst.native_swath.<variable>.zarr`;
  - the version comes from the files' attributes, with no product token
    (2026-10-14).
- **One pass, many stores:** each granule is read once and written to every
  store of a config (2026-10-14).
- **GOSAT DED and H2O merged into one product** per day (2026-10-14).
- **TROPOMI rows with unwritten time are left out**, checked, and
  `granule_source_rows` keeps each file's row count (2026-10-16). The three
  corrupt upstream files are declared and left out.
- **The TROPOMI subset is 16 one-dimensional stores:** the core 7 plus the 9
  inputs to the Schneider et al. (2022) Table 1 filters.
- **Kernels, priors, dry-air columns and the pressure grid are deferred** to
  the cross-product naming pass. Measure kernel compression with a scratch
  script, which needs no rows.
- **Filtering guidance** in the metadata is Table 1 in full, plus the
  inferred reduced chi-squared.
- **Naming rule:** quantity first, then qualifiers general to specific;
  established terms stay whole; unitless quantities use `unitless`.

## Open questions

- **Coordinate naming in the geolocation store.** `pressure` follows the
  `time`/`lat`/`lon` convention (no nomenclature row) unless the user says
  otherwise. It only matters once the model-comparison set is produced.
