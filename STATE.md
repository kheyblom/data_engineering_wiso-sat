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
  - **Tier 2, the TROPOMI bench, ran and passed on 2026-10-16. Its results
    are below and are NOT yet written into `TESTING.md`.** That is the next
    step.
- **The TROPOMI raw tree is final and fully audited (2026-10-16).**
  - 38,648 files, 2017-11-08 to 2025-11-29.
  - Every gap and defect is declared in `config/tropomi/config_zarr.yaml`.
  - All facts, issues (T1-T21) and the defect orbit lists are in
    `docs/products/tropomi.md`.
  - Each sensor's doc carries its own **Known data issues** table; add new
    findings there.

## Tier 2 bench: results (to record in TESTING.md)

**Setup:**
- Config `config/tropomi/config_zarr_bench.yaml`: production settings, with
  `chunks.obs` 4,194,304, `granules_per_commit` 20 and `num_workers` 8.
- Data: July 2020, symlinked by `validation/stage_bench_tropomi.py`. That is
  390 orbit files and 346,391,445 obs, ~1.06% of the record's ~3.27e10 obs.
  The month has no defects.
- Jobs: develop queue, 8 cores and 32 GB each. Submitted with
  `submit_wisosat_zarr.sh`: build **7840626**, then verify **7840628**
  (`afterany`).

| | wall | per orbit | peak memory | result |
| --- | --- | --- | --- | --- |
| build | 189 s (11:29:57-11:33:06) | 0.48 s | 2.93 GiB main, 0.31 GiB per worker | 17 stores, 20 commits each |
| verify | 328 s (11:33:40-11:39:08) | 0.84 s | 4.24 GiB main, 0.31 GiB per worker | **529 checks, 0 failures**, 0 mismatches over 346,391,445 obs |

**Compressed sizes** (`du`, MiB), 14.2 GiB in all:

| store | MiB |
| --- | --- |
| float32 retrieval, aerosol, albedo and chi-squared stores | ~925-990 each |
| `solar_zenith_angle` | 1,219 |
| `height_scattering_layer` | 764 |
| `iterations_retrieval` | 135 |
| `spectral_point_count_retrieval` | 61 |
| `quality_flags_retrieval` | 55 |
| `spectral_point_count_prefit` | 49 |
| `geolocation` (time int64, lat, lon) | 2,493 |

- Uncompressed float32 is ~1,321 MiB per store, so the zstd default
  compresses to ~0.70 of that.
- At `chunks.obs` 4,194,304, a float32 chunk is 16 MiB uncompressed (~11 MiB
  stored); a store has ~83 chunks for the month.

**Extrapolated to the full record** (x ~94), at the same 8 workers. Both are
estimates:
- **Build:** ~5.2 h wall, which fits one 12 h main-queue job or several
  chained develop jobs. **Verify:** ~9 h wall.
- **Storage:** ~1.3 TiB for the 17 stores.

## Next (in order)

1. **Write the Tier 2 outcome into `TESTING.md`**, from the results above.
   The bench stores and logs are:
   - stores: `/glade/derecho/scratch/kheyblom/data/wisosat_bench/zarr/tropomi/`;
   - logs: `logs/wisosat_zarr_tropomi_bench.log` and
     `logs/verify_wisosat_zarr_tropomi_bench.log`, plus the PBS output
     `logs/7840626.desched1.OU` and `logs/7840628.desched1.OU` (`logs/` is
     gitignored).
2. **Decide the production scale settings** with the user:
   - **Workers.** It is not yet known whether build and verify are read-bound
     (Lustre latency) and would scale with more workers. A second bench at
     `num_workers` 16 or 32 would answer it. Show the user the job before
     submitting.
   - **Chunks.** `chunks.obs` 4,194,304 gives ~11 MiB stored per float32
     chunk, inside the guide's 5-40 MiB (uncompressed). The int stores
     compress far more (flags ~0.6 MiB per chunk); decide whether that
     matters.
   - **Queue and walltime.** Derecho main is a whole node (128 cores) for up
     to 12 h; develop is shared. Cost-minimise: the allocation is finite.
3. **Plan Tier 3**, the TROPOMI production run, and show the user every job
   before submitting.
   - Config `config/tropomi/config_zarr.yaml`. It is never run, and its
     settings come from step 2.
   - Build, then verify chained `afterany`, then the `finalize_wisosat_zarr.py`
     sequence: `--status`, `--attrs`, `--tag`, and `--gc` (dry run first).
   - The build fails loudly on anything undeclared in the raw tree, by
     design.
4. Later, not blocking TROPOMI:
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
