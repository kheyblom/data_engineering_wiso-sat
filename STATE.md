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

1. **Decide the production scale settings** with the user:
   - **Workers.** The log timestamps say the build is write-bound: the
     serial commit of 17 stores takes ~6 s of each ~9 s batch, and reads are
     prefetched. More workers can cut at most ~1/3 of the build. The verifier
     does not prefetch, and its store reads and compares run serially in
     main. Options: keep 8; bench 16 to confirm (show the job first); or
     prefetch raw reads in the verifier, a code change.
   - **Chunks.** `chunks.obs` 4,194,304 gives ~11 MiB stored per float32
     chunk, inside the guide's 5-40 MiB (uncompressed). The int stores
     compress far more (flags ~0.6 MiB per chunk); decide whether that
     matters.
   - **Queue and walltime.** The estimate at 8 workers is ~5.2 h build and
     ~9 h verify. Derecho main charges a whole node (128 cores) for up to
     12 h, so ~5.2 h there would be ~670 core-hours, against ~42 on 8
     develop cores. Develop's walltime limit was not visible from
     `qstat -Qf develop` (it is a routing queue), so check it. Cost-minimise:
     the allocation is finite.
2. **Plan Tier 3**, the TROPOMI production run, and show the user every job
   before submitting.
   - Config `config/tropomi/config_zarr.yaml`. It is never run, and its
     settings come from step 1.
   - Build, then verify chained `afterany`, then the `finalize_wisosat_zarr.py`
     sequence: `--status`, `--attrs`, `--tag`, and `--gc` (dry run first).
   - The build fails loudly on anything undeclared in the raw tree, by
     design.
3. Later, not blocking TROPOMI:
   - the cross-product naming pass for kernels, priors and dry-air columns,
     which GOSAT production waits on;
   - GOSAT-2 configs (`product: gosat2`), which need a small shared change so
     the reader and key can be named apart from the product;
   - task 6, the other products.

## Things the next session needs to know

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
