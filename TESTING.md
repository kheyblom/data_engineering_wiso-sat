# Validating the WISO-SAT L2 build

How the pipeline is tested before anything runs at production scale, what has
been found, and how to reproduce it. It is tiered like `data_engineering_mswep`
and `_gleam`, for the same reason: a bug found on a fixture costs seconds, and
the same bug found on the full TROPOMI record (38,648 orbit files) costs
core-hours against a finite allocation.

| Tier | What it is | Cost | Status |
|------|-----------|------|--------|
| 0 | Guards that refuse a bad config or raw tree before anything is written | seconds | **passed** (2026-10-14, in the Tier 1 test) |
| 1 | Per-product fixtures, end to end: build, verify, resume, tamper, finalize | ~75 s, login node | **passed** (2026-10-16): 38 cases, TROPOMI and GOSAT |
| 2 | One real month of TROPOMI, production settings, throwaway stores | develop-queue job | **passed** (2026-10-16): build 189 s, verify 328 s, 0 failures |
| 3 | Production builds and verification, one product at a time | batch chain | TROPOMI: **done** (2026-10-18): built, verified with 0 failures, finalized. GOSAT: waits on the kernel naming pass |

## Tier 0 and 1: the fixture test

Design condition 2: every product keeps a tiny fixture, and one test runs them
all after any change to shared code.

```bash
uv run python validation/stage_tropomi.py   # once: 5 orbits cut to 23-47 scanlines
uv run python validation/stage_gosat.py     # once: 4 real days, both files
TMPDIR=/glade/derecho/scratch/$USER/tmp uv run python validation/test_pipeline.py
```

Per product, the test:
1. **Builds and verifies.** Every observation of every store is compared with
   raw, bit for bit.
2. **Re-runs** the build, which must write nothing.
3. **Resumes.** One store is reset to empty and one to its first commit, as a
   killed run leaves them; the build is re-run and re-verified.
4. **Tampers.** One stored value is changed, and the verifier must fail,
   naming the store.
5. **Exercises the guards.** The build must refuse:
   - an undeclared missing day;
   - a wrong version;
   - a run without the quality flags;
   - an unknown variable;
   - an undeclared empty granule directory (TROPOMI).

   A refused version must leave no store behind.
6. **Finalizes.** `--attrs` must refuse an unverified store. Then `--attrs`,
   `--tag` and `--gc` run in that order, and the stores still verify.

What each fixture exercises is listed at the top of its config.

## Findings so far

### 1. An append replaces the store's global attributes

Each append is written with xarray's `append_dim`, and that rewrote the group
attributes with the appended dataset's, which were empty. So the second commit
stripped every global attribute the first had written. `xr.merge` also dropped
them on the first write. `write_append` now carries the stored attributes onto
every append. The verifier's required-attribute check is what caught it.

### 2. A resumed run must read every source of every incomplete store

The first version fixed its read list from the first batch's stores. A store
that was ahead at the restart point then had its variable read by nothing once
the pass caught up with it, and the build crashed. Found by the resume case of
the test.

### 3. Fill must be masked before a unit conversion

`9.96921e36 x 1000` overflows float32 to inf. It was masked to NaN afterwards,
so no value was wrong, but the overflow warning would have hidden a real one.
Fill is now masked first. Any value that still overflows after conversion
fails the build: that would be an undeclared fill.

### 4. Time needs a unit per product

The guide asks for the coarsest unit that holds the source times exactly.
- **TROPOMI:** milliseconds, because time is broken down to the millisecond.
- **GOSAT:** nanoseconds. FOCAL's float64 seconds sit on no coarser grid: in
  an exact round trip of 38,003 sampled times, ms failed 99% and us 76%.

The unit now comes from each key's coordinate table. The build fails if the
reader decodes to any other unit.

### 5. The TROPOMI download was incomplete (re-downloaded 2026-10-16)

Found while staging the bench. 692 orbit directories are empty, and 70 days
have no directory. Checked one by one against the upstream server:
- 353 empty orbits and 58 days are real upstream gaps, and are now declared;
- **339 orbits and 12 days exist upstream but are missing here.**

The build refused to run until they were downloaded. The user re-downloaded
on 2026-10-16:
- the gaps are filled;
- the record now runs to 2025-11-29 (38,648 orbit files);
- the 19 new missing days are all real upstream gaps (404);
- 2025-11-30 exists upstream only as empty orbit directories.

See `docs/products/tropomi.md` (T7).

### 6. A source `calendar` attribute blocks the time write

FOCAL's time carries `calendar: standard`, and xarray refuses to write a time
whose attributes already hold an encoding key. It is now kept as
`original_calendar`; the store's calendar is `proleptic_gregorian`.

### 7. Every TROPOMI file audited (2026-10-16, develop job 7839486, 8 min)

`tools/survey/tropomi_file_audit.py` checked all 38,648 files. For each it
recorded whether it opens, its version, and whether every source the pipeline
reads was written.

| result | files |
| --- | --- |
| OK | 38,459 (99.5%) |
| partial: time written for only some rows, or some sources never written | 77 |
| shell: nothing written | 109 |
| unreadable, and byte-identical upstream: orbits 3335, 7821, 7844 | 3 |

Plus 353 empty orbit directories, all real upstream gaps. The defects
cluster in 2019 (93 shells, 74 partial); 2017, 2020 and 2025 are clean.

The output is in `/glade/derecho/scratch/$USER/data/wisosat/audit/`.

### 8. Rows SRON never processed are left out, checked (user decision 2026-10-16)

In the partial files, `time`, lat/lon and SZA are fill on the same rows: 93-100%
of each file. Across all 48.7 million such rows, none of the 20 other sources
the pipeline reads holds a value.

So **an observation is a row whose time is written**:
- **The rule.** Unprocessed rows are left out, but only after the reader
  confirms that every source it read is fill on them; otherwise the build
  fails. The verifier finds such rows from the raw time on its own and fails
  if any carries data.
- **What it means for the defect files.** A shell becomes a granule with no
  observations. A new index field, `granule_source_rows`, keeps every file's
  own row count, so nothing is left out invisibly.
- **The three unreadable files** are declared in
  `expected_unreadable_granules`. The build confirms each still fails to open.
- **The fixture** carries one real shell, one real partial file and one real
  truncated file, as stand-ins in 2020-06-16.
- **One new fill declaration.** 238 processed rows in partial files have no
  flags written, so -2147483647 is now declared for
  `processing_quality_flags`.

**Not affected:** the bench month, July 2020, where all 390 files are OK.

### 9. HDF5 segfaults on one corrupt file rather than raising (2026-10-16)

The first production build (job 7840968) died with exit 139 a second into
listing granules, with no traceback.
- **The cause:** netCDF4 segfaults opening orbit 3335 (bad fractal heap
  header). The other two corrupt files raise `OSError`. The audit had used
  h5py, which raises on 3335, so the audit never saw the crash.
- **The fix:** the reader now probes declared-unreadable files in a child
  process.
- **The test:** the fixture links 3335, so it meets this case. The guard for
  an undeclared unreadable file now undeclares only the truncated file: an
  undeclared crashing file still stops the build, but with no message to
  match.

The chain is `afterany`, so it ran all its jobs through in a minute. That cost
little this time, but **watch the first job of a chain until it commits**, and
delete the rest if it dies.

### 10. Six rows with a time but no position (2026-10-17)

The first production verification (V1-V3, jobs 7841010-12, ~97 core-hours)
failed. Every value matched raw, but `instrument/latitude_center` and
`longitude_center` held 6 netCDF default fills on stored rows.
- **The rows:** orbit 8480 (1 row), 8674 (2) and 8726 (3), all June 2019 (see
  `docs/products/tropomi.md`, T8).
  - Each is the only row with a time in its file.
  - SRON wrote time, SZA (~101 deg, night) and other viewing angles, and
    nothing else: no position, retrieval or flags.
- **Why they were stored:** under finding 8 a row with a time was an
  observation. The geolocation store held 9.97e36 for their lat/lon; the
  other stores held fill, except SZA.
- **The fix (user decision):** an observation needs time, lat and lon all
  written, and the rule is now shared code for every product (`RowRule` in
  `utils/granules.py`). A row left out may hold values only in the config's
  `allowed_on_rows_left_out`. TROPOMI allows SZA, so these rows' SZA goes
  with them.
- **The test:** the fixture links orbit 8480, and a guard checks that the
  build refuses when SZA is not allowed. 39 cases pass.
- **Why the audit missed it:** it checked whether each dataset was written at
  all, not row by row.

### 11. A dirty working tree in the build's provenance (2026-10-18)

The build of the corner geolocation store and the two index stores was stamped
`@ e743105-dirty` on all 645 commits.
- **The cause:** when it started, `git status` showed untracked marimo
  notebooks (`.gitignore` covered only `testing*.ipynb`), and perhaps the
  marimo entry in `pyproject.toml` and `uv.lock`. No pipeline code differed
  from `e743105`, and no pipeline library changed version.
- **The stores:** the stamp in their commit messages is permanent. Their
  `history` explains it, through `finalize --dirty-notes`.
- **The fix:**
  - `notebooks/` is ignored;
  - a build refuses a dirty tree, at submit and at start (`check_clean_tree`);
  - only fixture configs may set `allow_dirty_tree`.
- **The test:** an untracked probe file makes the tree dirty, and the build
  must refuse without the fixture's allowance. A global check confirms that
  no other config sets it. 46 cases pass.

## Tier 2: the TROPOMI bench (passed 2026-10-16)

**What it is:** one real month, 2020-07: 390 orbit files and 346,391,445
observations, ~1.06% of the record's ~3.27e10. The month has no missing days
and no defect files; its five empty orbit directories are real upstream gaps.
It runs with the production config's variables, chunks and settings
(`config/tropomi/config_zarr_bench.yaml`: `chunks.obs` 4,194,304,
`granules_per_commit` 20, `num_workers` 8) into throwaway stores under
`/glade/derecho/scratch/$USER/data/wisosat_bench/`. The raw tree is 31
symlinks, made by `validation/stage_bench_tropomi.py`.

**Commands.** Build job 7840626, then verify job 7840628 chained `afterany`.
Each ran on the develop queue with 8 cores and 32 GB, under a 1 h limit.

```bash
bash -lc 'cd ~/work/data_engineering/data_engineering_wiso-sat && \
  CONFIG=config/tropomi/config_zarr_bench.yaml QUEUE=develop NCPUS=8 MEM=32GB \
  WALLTIME=01:00:00 ./submit_wisosat_zarr.sh'
bash -lc 'cd ~/work/data_engineering/data_engineering_wiso-sat && \
  CONFIG=config/tropomi/config_zarr_bench.yaml VERIFY=1 QUEUE=develop NCPUS=8 \
  MEM=32GB WALLTIME=01:00:00 AFTER=<build job id> ./submit_wisosat_zarr.sh'
```

### Results

| | wall | per orbit | peak memory | result |
| --- | --- | --- | --- | --- |
| build | 189 s | 0.48 s | 2.93 GiB main, 0.31 GiB per worker | 17 stores, 20 commits each |
| verify | 328 s | 0.84 s | 4.24 GiB main, 0.31 GiB per worker | **529 checks, 0 failures** over every observation |

- **Cost:** ~1.1 core-hours for both jobs, against the 16 allowed.
- **Fill:** each retrieval store holds 108,028,576 fill values (31% of the
  observations); the prefit stores hold 94,493,960 (27%). SZA and the flags
  hold none.
- **Geospatial bounds:** lat -83.0 to 90.0, lon -180 to 180.

**Compressed size** (`du`), 14.2 GiB for the 17 stores:

| store | MiB |
| --- | --- |
| each float32 retrieval, aerosol, albedo and chi-squared store | ~925-990 |
| `solar_zenith_angle` | 1,219 |
| `height_scattering_layer` | 764 |
| `iterations_retrieval` | 135 |
| `spectral_point_count_retrieval` | 61 |
| `quality_flags_retrieval` | 55 |
| `spectral_point_count_prefit` | 49 |
| `geolocation` (int64 time, lat, lon) | 2,493 |

- **Float32 stores** compress to ~0.70 of their uncompressed ~1,321 MiB under
  the zstd default.
- **Chunks:** a float32 chunk is 16 MiB uncompressed and ~11 MiB stored, at
  ~83 chunks per store for the month. The integer stores compress much
  further, to ~0.6 MiB per chunk for the flags.
- **Objects on disk.** One float32 store holds 144 objects in `chunks/`, 160
  in `manifests/`, and 21 each in `snapshots/` and `transactions/`. Every
  commit rewrites the six granule-index chunks and the trailing partial data
  chunk, and writes one manifest per array. `--gc` never expires history, so
  all of these stay reachable.
  - Scaled by commits to the full record (~1,930 at 20 granules per
    commit), that is ~14-21k chunks and ~15k manifests per store, in one
    directory each. The GLADE guidance is ~2-3k files per directory.
  - Production uses 60 granules per commit (user decision 2026-10-16).
    That gives ~645 commits: ~12k chunks and ~5k manifests per store.
    ~7,800 of those chunks are the final data, and they remain at any
    commit size.

**Where the build's time goes.** The build reads the next batch in the pool
while it writes the current one. Writing and committing the 17 stores one
after another in the main process takes ~6 s of each ~9 s batch: 115 s of the
181 s loop. The rest is time spent waiting on reads that the write did not
cover. So the build is write-bound in the main process, not read-bound:
- more workers can shrink only the ~66 s of read wait, so at most about a
  third of the build;
- beyond ~16 workers they should buy nothing.

This is inferred from log timestamps, not measured at another worker count.

**The verifier does not prefetch.** Each batch of 20 granules takes ~16 s:
- the raw reads run in the pool;
- the main process then reads the stores and compares them, serially.

More workers shorten only the raw-read part.

**Extrapolated to the full TROPOMI record** at the same 8 workers. These are
estimates. Times scale by file count (38,648 / 390, x99) and size by
observations (x94):
- **build:** ~5.2 h wall;
- **verify:** ~9 h wall;
- **storage:** ~1.3 TiB for the 17 stores.

Partial and shell files (finding 7) hold fewer observations, so the time
figures lean high.

## Tier 3: production

Per product:
1. The build, chained `afterany` if it needs more than one walltime.
2. The verifier, over every observation, chained after the build.
3. `finalize_wisosat_zarr.py`: `--status`, then `--attrs`, `--tag`, and `--gc`
   (dry run first).

### TROPOMI (planned 2026-10-16; done 2026-10-18)

**Scale settings,** decided with the user from Tier 2, are in
`config/tropomi/config_zarr.yaml`:
- 8 workers;
- `chunks.obs` 4,194,304;
- `granules_per_commit` 60, which gives ~645 commits rather than ~1,930;
- the develop queue: 8 cores, 32 GB, and the 6 h walltime limit that NCAR
  documents for develop.

**Why the verify step is split.** At ~9 h it does not fit one 6 h job, and the
verifier cannot resume. It is split into three runs by `--stores`. Each run
also checks geolocation, the index's reference.
- `finalize` accepts this: per store, it looks for the last passing run that
  covered every phase and that store.
- The runs share one log, so they are chained, never concurrent.
- The groups are balanced by stored size from the bench.

| run | stores (plus geolocation) |
| --- | --- |
| V1 | `water_vapor_column_delta_d`, `water_vapor_column_delta_d_standard_error`, `water_vapor_column_h2o`, `water_vapor_column_h2o_standard_error`, `quality_flags_retrieval` |
| V2 | `water_vapor_column_hdo`, `water_vapor_column_hdo_standard_error`, `solar_zenith_angle`, `iterations_retrieval`, `spectral_point_count_retrieval` |
| V3 | `optical_thickness_scattering_layer`, `height_scattering_layer`, `albedo_surface_2365nm`, `chi_squared_retrieval`, `chi_squared_prefit`, `spectral_point_count_prefit` |

**The `VERIFY_ARGS` quoting.** `qsub -v` splits on commas, so the wrapper now
single-quotes `VERIFY_ARGS`. A wrong split would silently verify one store.
Step 0 proves the quoting on the bench stores before the chain relies on it.

**Commands**, from the repo root, each through
`bash -lc 'cd ~/work/data_engineering/data_engineering_wiso-sat && ...'`:

```bash
# 0. quoting check on the bench stores: metadata phases only, a few minutes
CONFIG=config/tropomi/config_zarr_bench.yaml VERIFY=1 \
  VERIFY_ARGS="--phases structure,index --stores water_vapor_column_hdo,solar_zenith_angle" \
  QUEUE=develop NCPUS=8 MEM=32GB WALLTIME=00:15:00 ./submit_wisosat_zarr.sh
# pass: the job's verify log names both stores in its 'stores:' line

# B1, B2: the build, and a resume in case B1 hits the walltime (a no-op if not)
P='CONFIG=config/tropomi/config_zarr.yaml QUEUE=develop NCPUS=8 MEM=32GB WALLTIME=06:00:00'
env $P ./submit_wisosat_zarr.sh                                  # -> B1
env $P AFTER=<B1> ./submit_wisosat_zarr.sh                       # -> B2
# V1-V3: verification, chained
env $P VERIFY=1 AFTER=<B2> VERIFY_ARGS="--stores <V1 list>" ./submit_wisosat_zarr.sh   # -> V1
env $P VERIFY=1 AFTER=<V1> VERIFY_ARGS="--stores <V2 list>" ./submit_wisosat_zarr.sh   # -> V2
env $P VERIFY=1 AFTER=<V2> VERIFY_ARGS="--stores <V3 list>" ./submit_wisosat_zarr.sh   # -> V3
```

**Cost estimate:** build ~42 core-hours and verify ~75-90 core-hours, ~125
in all. The ceiling is 5 jobs x 6 h x 8 cores = 240 core-hours. Step 0 costs
well under one core-hour.

**Space:** ~1.3 TiB, to `/glade/derecho/scratch/$USER/data/wisosat/zarr/tropomi/`
(absent before the run). Scratch is at 48.6 of 150 TiB.

**After the chain:** `finalize --status`, then `--attrs`, `--tag`, `--gc`
(dry run, then `--apply`). Scratch is purged, so the stores are moved to
their data-lake home afterwards; where is to be decided.

Blockers:
- **TROPOMI:** none. The chain above awaits approval.
- **GOSAT:** the whole record is ~9,000 small files, so a single develop job
  covers build and verification. It waits on the cross-product naming pass,
  so that its kernel and a priori stores are built with the rest.
  - Building them later is possible: a new store resumes from zero on the same
    obs axis while the others are no-ops.
