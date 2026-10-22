# Validating the WISO-SAT L2 build

How the pipeline is tested before anything runs at production scale, what has
been found, and how to reproduce it. It is tiered like `data_engineering_mswep`
and `_gleam`, for the same reason: a bug found on a fixture costs seconds, and
the same bug found on the full TROPOMI record (38,648 orbit files) costs
core-hours against a finite allocation.

| Tier | What it is | Cost | Status |
|------|-----------|------|--------|
| 0 | Guards that refuse a bad config or raw tree before anything is written | seconds | **passed** (2026-10-14, in the Tier 1 test) |
| 1 | Per-product fixtures, end to end: build, verify, resume, tamper, finalize | ~2.5 min, login node | **passed** (2026-10-22): 132 cases, TROPOMI, GOSAT, GOSAT-2 (`source` and `platform`) and SCIAMACHY (declared rows, monthly coverage), with the 2-D model-comparison stores, the per-array codec and shards, `finalize --expire`, stores in processes of their own and range scans in the verifier |
| 2 | One real month of TROPOMI, production settings, throwaway stores | develop-queue job | **passed** (2026-10-16): build 189 s, verify 328 s, 0 failures |
| 3 | Production builds and verification, one product at a time | batch chain | TROPOMI: **done** (2026-10-18): built, verified with 0 failures, finalized. GOSAT: **done** (2026-10-19): built, verified with 0 failures, finalized. GOSAT-2: **done** (2026-10-22): built, verified with 0 failures, finalized |

## Tier 0 and 1: the fixture test

Design condition 2: every product keeps a tiny fixture, and one test runs them
all after any change to shared code.

```bash
uv run python validation/stage_tropomi.py   # once: 5 orbits cut to 23-47 scanlines
uv run python validation/stage_gosat.py     # once: 4 real days, both files
uv run python validation/stage_sciamachy.py # once: 5 real orbit files, whole
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
   - an undeclared missing day (a month for SCIAMACHY);
   - a wrong version;
   - a run without the quality flags;
   - an unknown variable;
   - an undeclared empty granule directory (TROPOMI);
   - declared rows that are missing or do not match raw (SCIAMACHY), or
     that a reader cannot apply (the others). The verifier must fail a
     declaration that does not match raw.

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

### 13. Every SCIAMACHY file audited (2026-10-22, develop job 7907283, 6 min)

`tools/survey/sciamachy_file_audit.py` read all 41,616 month-folder files in
full (173 GB; 8 cores requested, 16 workers from the affinity mask; ~0.8
core-hours).
- **All 41,616 files are good:** they open, are version 8.1, share one
  layout, and hold 78,666,953 obs. No row lacks time, lat or lon, so no row
  is left out.
- **The first run reported 759 as unreadable**, but the error was the audit's
  own decoder: the millisecond field reaches 1000 (the next whole second).
  `pd.to_datetime`, which the shared `decode_time` uses, carries it. Those
  files were re-audited in place (`--redo-unreadable`, login node, 70 s).
- **Two defects break "time never decreases"** (`sciamachy.md` S8, S9): orbit
  15838 holds its 312 observations three times, and orbits 45262 and 45263
  retrieve 32 scenes twice. Both await the user (P6).
- The output is in `/glade/derecho/scratch/$USER/data/wisosat/audit/`
  (`sciamachy_file_audit.jsonl`; the first run kept as `_run1`).

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

## Tier 2b: the TROPOMI 2-D bench (2026-10-19)

The six model-comparison stores (two column kernels, two a priori partial
columns, `dry_air_partial_column`, `pressure`) over the same month as Tier 2,
2020-07: 390 orbits, 346,391,445 obs, 1.06% of the record (x 94.28 scales to
it). Built at `c7135d6` into the Tier 2 bench directory; the 19 bench stores
from 2026-10-16 were complete and skipped. Blosc zstd 5 + shuffle, shards of
4,194,304 obs, `granules_per_commit` 20, 8 workers. Develop, 8 cores, 96 GB.

| job | what | wall | CPU used | peak memory | result |
| --- | --- | --- | --- | --- | --- |
| 7875114 | build | 37 min 20 s | 4 h 05 min (7.2 cores) | 56.4 GiB main, 3.1 GiB worker | 6 stores, 20 commits each; kernels masked 5,401,428,800 values (108M rows), the others none |
| 7875115 | verify `--stores` the six (and geolocation) | 46 min 22 s | 2 h 27 min (3.8 cores) | 65.5 GiB main, 3.2 GiB worker | **313 checks, 0 failures**; every value bit for bit |

- **Cost:** 11.2 core-hours billed (5.0 build, 6.2 verify).
- **Size:** 211.2 GiB live (kernels 33.6 and 28.2, priors 39.7 each, dry air
  35.1, pressure 34.8): **19.9 TiB** scaled to the record, as estimated.
- **Superseded shards:** 11.7-11.8% of each store before `--expire`, as
  predicted (~2.5 / 20). 144 files in each store's `chunks/`.
- **Scaled to production at these rates:** build 58.7 h wall, 469
  core-hours billed; verify 72.9 h wall, 583 core-hours. **~1,050 core-hours
  in all**, against ~380 for all TROPOMI work so far.

**Finding 12: the build uses ~4x the CPU its stages account for.**
- Profiled on one orbit through the build's own functions (login node,
  2026-10-19), per orbit of 803,025 obs: reading and decompressing the six
  zlib sources 3.1 s CPU; masking and converting 1.0 s; writing with blosc 5
  and shards 6.4-7.1 s (blosc 3: 4.0 s; blosc 1: 2.6 s; default zstd 3.6 s).
  About 11 s in all, against ~38 s measured in the bench.
- The wall time matches the profile (~5.7 s per orbit, the main process
  writing six stores in turn); the CPU does not.
- A 4-orbit build on the login node showed kernel time 3x user time (15.3 s
  against 5.1 s), which points at memory management: multi-GB arrays
  allocated, zeroed and freed every batch, possibly worsened by the submit
  script's `MALLOC_TRIM_THRESHOLD_=0`. That probe was killed after 40 s,
  probably by the login node's limiter, and is not repeated there.
- Since `b94038c` every run logs its CPU split (main and workers, user and
  sys), so the next job shows where it goes.
- **The verifier cannot run production as it stands:** it does not resume,
  cannot split a store, and always re-verifies the geolocation store. One
  run over the six would take ~73 h; one store alone would not fit develop's
  6 h either.

**Finding 12, diagnosed (job 7877379, 2026-10-19, 15 min, ~2 core-hours).**
36 orbits (2020-07-01..03), the bench's settings, the CPU split from
`b94038c` (per orbit, from rusage):

| run | wall | CPU | main user / sys | workers user / sys |
| --- | --- | --- | --- | --- |
| A: as the bench (`MALLOC_TRIM_THRESHOLD_=0`, 20 per commit) | 243 s | 34 s/orbit | 12 / 13 s | 5 / 5 s |
| B: glibc's default trim, 20 per commit | 177 s | 27 s/orbit | 12 / 5 s | 5 / 5 s |
| C: default trim, 5 per commit (main peak 17 GiB) | 200 s | 24 s/orbit | 11 / 6 s | 5 / 3 s |
| verify of A (trim 0) | 273 s | 24 s/orbit | 2 / 10 s | 5 / 6 s |

- A reproduces the bench (34 against 38 s per orbit).
- **`MALLOC_TRIM_THRESHOLD_=0` costs the main process ~8 s of kernel time
  per orbit**: freed multi-GB arrays go back to the OS and are faulted in and
  zeroed again on the next batch. Default trim: -22% CPU, -27% wall.
- **What remains is moving the data between processes.** Each orbit's ~1.1
  GB of 2-D sources is pickled by a worker, pushed through a pipe and
  unpickled by the main process: workers spend ~10 s per orbit against ~3 s
  of reading, and the main process ~5 s more user time than its stages.
- The verifier has the same shape, dominated by kernel time (16 of 24 s).
- Floor from the stage profile: ~11 s per orbit.

**Finding 12, fixed (2026-10-19, user approval of all three changes):**
1. the submit script no longer sets `MALLOC_TRIM_THRESHOLD_=0`;
2. `own_process_stores`: each 2-D store is built in a process of its own that
   reads only its sources, so nothing large crosses between processes;
3. the verifier's values phase runs as scans (a group of stores over a range
   of `verify_granules_per_task` granules) in `verify_num_workers` processes,
   each returning only counts, so one store's record spreads over as many
   cores as the job has; `--stores` no longer re-compares geolocation.
The test passes 63 cases with the same check counts as before. The re-bench
measures the result.

**Re-bench with the fixes (2026-10-19, at `3753d14`, the
bench at 10 granules per commit).** The six bench stores were deleted first
(user approval).

| job | what | wall | CPU used | peak memory | result |
| --- | --- | --- | --- | --- | --- |
| 7877506 | build, six processes of their own | 23 min 27 s | 3.06 h (workers 2.10 user + 0.95 sys) | 15.6 GiB per store process | 390 granules each; masking as before |
| 7877507 | verify `--stores` the six, 48 scans x 8 processes | 20 min 52 s | 2.83 h (workers 1.02 user + 1.80 sys) | 2.5 GiB per scan | **297 checks, 0 failures** |

- **Cost:** 5.9 core-hours billed, against 11.2 (-48%). Wall -37% build, -55%
  verify.
- **Production at these rates:** build ~37 h wall (~295 core-hours), verify
  ~33 h (~262): **~555 core-hours**, against ~1,050 before the fixes.
- **Still ~2.5x the stage profile:** the build uses ~28 s of CPU per orbit
  against ~11. Kernel time is large, and dominates the verifier (1.8 of 2.8
  h): likely page faults, since glibc maps every allocation over 32 MB
  fresh, so each multi-GB array is zeroed again every batch or granule.
  Untested remedies: reusing buffers, or transparent huge pages.
- **Memory:** six store processes at 15.6 GiB can approach 94 GB; production
  should request ~128 GB at 10 granules per commit.

## Tier 2c: the SCIAMACHY bench (passed 2026-10-22)

**What it is:** three real months, 2010-09 to 2010-11: 1,026 orbit files,
1,983,046 observations (~2.5% of the record), with the S9 overlap declared
(`config/sciamachy/config_zarr_bench.yaml`; the raw tree is 3 symlinks made by
`validation/stage_bench_sciamachy.py`). Production settings: `chunks.obs`
4,194,304, `granules_per_commit` 500, `num_workers` 8, default zstd.

| job | what | wall | cpu | memory | result |
| --- | --- | --- | --- | --- | --- |
| 7908198 | build, 22 stores, 3 commits | 38 s | 1 min 10 s | 4.49 GiB main process (job 11.4 GiB) | done |
| 7908201 | verify, 11 scans x 8 processes | 3 min 45 s | 30 min 52 s (workers 0.29 h user + 0.22 h sys) | 0.58 GiB per scan | **879 checks, 0 failures**; the 32 declared rows confirmed from raw |

Both on develop, 8 cores and 32 GB; ~0.6 core-hours in all.

**Compression** (three chunks of each 2-D store, login node): blosc zstd 5 +
byte shuffle against the default zstd. The water kernels compress 1.36x and
1.70x against 1.12x and 1.19x; the priors 1.42x against 1.07x; dry air 1.73x
against 1.11x; pressure 1.82x against 1.12x. Blosc saves 18-38% of the
default size, ~26 GB of ~101 GB over the record. (A first measurement passed
blosc raw bytes, so its shuffle ran at type size 1 and did nothing.)

**Finding 14: the verifier decodes a whole chunk for every granule.** The
values phase reads each store's slice for one granule at a time. A SCIAMACHY
orbit is ~1,900 obs and a chunk 4,194,304 (1-D) or 131,072 (2-D), so each
read decodes a chunk to keep ~0.05-1.5% of it. On the bench stores, 100
orbits read one at a time took 1.45 s against 15 ms in one read (1-D), and
5.3 s against 82 ms (2-D): ~1.5 cpu-s per orbit over the 22 stores, so ~17 of
the ~21 cpu-hours a production verify would take. TROPOMI's orbits are larger
than a 1-D chunk's share, so it paid this far less.
- **Fixed** (user approval 2026-10-22): `ChunkSpans` in the verifier keeps
  each array's last decoded chunk span per scan and serves later slices from
  it, as read-only views, so each chunk is decoded about once. What is
  compared is unchanged. The fixture test passes 132 cases. The bench is
  rebuilt with blosc on the 2-D stores and re-verified to measure it.

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

### TROPOMI run log (2026-10-16 to 2026-10-18)

Moved from STATE.md when TROPOMI finished. Every job, finding and decision of
the production run, in order.

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
   - **V1-V3 all ended with exit 1 (2026-10-17).** In each, only the same 2
     checks failed (`instrument/latitude_center` and `longitude_center`: no
     undeclared netCDF default fill, 6 values); every value comparison
     passed.
     - Run times were 3.4, 4.1 and 4.6 h, ~97 core-hours in all.
     - **The cause:** 6 rows in three nearly empty partial files, orbits 8480
       (row 0), 8674 (rows 0 and 3) and 8726 (rows 0-2), all June 2019.
       They have time, SZA (~100.5-101 deg, night), solar azimuth and
       viewing zenith written, and nothing else. Lat/lon are fill, and so are
       the corners, every retrieval source and the flags.
     - They count as observations under finding 8 (time written). No fill is
       declared for lat/lon, so the geolocation store holds 9.97e36 for them,
       and the bounds read lat max 9.97e36.
     - The 16 variable stores are correct: fill or NaN on these rows, except
       SZA, which holds SRON's value.
     - **Decided (user, 2026-10-17):** a row with no position is not an
       observation. The rule is now shared code for every product (commit
       `5c88bf0`; TESTING.md finding 10).
     - **The stores were rewound, not deleted (2026-10-17).**
       - `tools/rewind_stores.py` reset all 17 stores to their commit holding
         granules 0-7019 (through orbit 08457): 4,824,553,284 obs, checked
         consistent across stores.
       - Orbit 8480, the first affected, is granule 7042.
       - The old tips are saved in `logs/rewind_wisosat_zarr_tropomi.json`
         (geolocation's was `TR6CN4DWVX26F3CV4RM0`). They are recoverable
         with `reset_branch` until `finalize --gc`.
     - **Resumed chain, submitted 2026-10-17 with the user's approval.** It
       uses the same commands as before, each job `afterany` the one before:

       | job | id |
       | --- | --- |
       | B1, resume from granule 7020 | 7855751 |
       | B2 | 7855752 |
       | V1 | 7855753 |
       | V2 | 7855754 |
       | V3 | 7855755 |

       Expect B1 ~3.7 h and V1-V3 ~12 h.
     - **The resumed chain passed (2026-10-18).**
       - B1: 3 h 41 min, exit 0, peak 11.05 GiB main. B2 was a no-op.
       - V1-V3: 3.5, 3.8 and 4.1 h. They ran 201, 200 and 231 checks with
         0 failures, and each says `stores verified`.
       - 129,562,471 rows were left out, 6 of them with a time, with 0
         values on them.
       - Bounds: lat -89.9997 to 89.9997, lon -180 to 180.
     - **`finalize --status`:**
       - every store is verified 2026-10-18, has 11 attributes pending, no
         tags, and 646 reachable snapshots;
       - the rewind's old commits are unreachable: ~1.04 TiB over 17 stores
         (geolocation 182 GiB);
       - next are `--attrs`, then `--tag`, then `--gc`.
     - **Provenance fix (user decision 2026-10-18; commit `5bfc662`).**
       - Build commits now carry their code revision.
       - `finalize` writes `history` per revision run.
       - The `verification` text now states the scope of the split runs.
     - **These stores' commits predate the stamp**, so `--attrs` takes the
       revisions checked out when each B1 started. Use exactly:
       `--build-revisions 7220460@0,24186fe@7020`
       - 7840968's B1 ran at 7220460: granules 0-7019, 2026-10-16.
       - 7855751's B1 ran at 24186fe: granules 7020 on, 2026-10-17. Its
         build code equals 5c88bf0.
       - Both checked with `git diff`.
     - **Applied 2026-10-18 08:34 MDT:** `--attrs` (one commit per store),
       then `--tag v8.1-verified-20261018` on all 17 stores (geolocation tip
       `0JYYG54RB35JDY4R5PH0`).
     - **The `--gc` dry run would delete ~1.04 TiB**, all of it the 528 commits
       per store that the rewind orphaned (geolocation 182 GiB).
     - **`--gc --apply` ran 2026-10-18 08:38-08:40 MDT**, approved by the user
       and run detached (`setsid nohup`). Output:
       `logs/finalize_gc_apply_tropomi_20261018.out`.
       - It deleted ~1.04 TiB over the 17 stores, exit 0. The rewind can no
         longer be undone.
       - The final `--status` reports every store **"remaining nothing,
         finalized"**: 647 reachable snapshots, 0 unreachable, tag
         `v8.1-verified-20261018`, 1.3 TiB in all.
     - **Open:** the stores sit on scratch, which is purged. Where they live
       in the data lake is undecided; ask the user before moving them.
     - **Additions decided 2026-10-18 (user):**
       - `lat_corners` and `lon_corners` go in the geolocation store, on
         `corner`;
       - `scanline_index` and `ground_pixel_index` become variable stores,
         SRON's values as written;
       - an array's obs chunk is halved until it fits 40 MiB, so corners
         take 2,097,152;
       - nomenclature rows: style_guides `81fef95` (the commit message of
         `3dbf1d2` misnames it `57d22cd`);
       - code: `d18e440`. Fixture: 41 cases, 0 failures.
     - **Bench for the additions, submitted 2026-10-18:** build 7861696, then
       verify 7861698 (`--stores scanline_index,ground_pixel_index`). The bench
       geolocation store was deleted first, with approval. The bench measures
       the verify time: geolocation with corners may approach the 6 h develop
       limit in production.
     - **Bench passed (2026-10-18).**
       - Build: 140 s, exit 0.
       - Verify: 118 s, 125 checks, 0 failures.
       - Geolocation grew from 2,493 to 8,162 MiB for the month; the two
         index stores are 8 MiB.
       - Scaled to the record: build ~3.9 h, verify ~3.3 h. One verify run
         fits the 6 h limit.
     - **Production, submitted 2026-10-18 with the user's approval:**
       - the old geolocation store was moved to
         `/glade/derecho/scratch/kheyblom/data/wisosat/zarr/tropomi_backup_20261018/`;
       - B1 7861748, B2 7861749, V 7861750 (`--stores
         scanline_index,ground_pixel_index`), each `afterany`.
       - The user agreed that only the new stores need value verification;
         the 16 old ones get the structure,index check.
     - **Production result (2026-10-18):**
       - B1: 3 h 43 min, exit 0, peak 10.49 GiB. B2 was a no-op.
       - V: 3 h 47 min, 129 checks, 0 failures.
       - The structure,index check over all 19 stores: 429 checks, 0
         failures. Every store's index is identical to the new geolocation
         store's.
       - The new stores were stamped `e743105-dirty`, because untracked
         marimo notebooks sat in the tree (TESTING.md finding 11). They were
         finalized with `--dirty-notes` (exact text in the finalize log),
         and the tree is now enforced clean for builds.
       - A verification-text fix (`7925c4b`) keeps the 16 older stores'
         records unchanged.
       - **All 19 stores are finalized, tag `v8.1-verified-20261018`.**
       - The old geolocation backup was deleted 2026-10-18, with the user's
         approval.
     - **Production plan (done):**
       1. Move the current geolocation store aside as a renamed backup; do
          not delete it.
       2. Build geolocation, scanline_index and ground_pixel_index from
          granule 0. The 16 variable stores are untouched.
       3. Verify the three new stores, split by the bench's timing.
       4. Run `--phases structure,index` over all 19 stores, to check the old
          stores' index against the new geolocation.
       5. Finalize the three new stores (no `--build-revisions` needed), tag
          `v8.1-verified-<date>`.
       6. Delete the backup only with the user's approval.
     - **Then finalize:** `--status`, `--attrs`, `--tag`, and `--gc` last. The
       `--gc` dry run comes first. `--gc` ends the rewind's undo window, so run
       it only after verification has passed.
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
   - the cross-product naming pass for kernels, priors and dry-air columns
     (done 2026-10-19);
   - GOSAT-2 configs (`product: gosat2`), which need a small shared change so
     the reader and key can be named apart from the product (done at fixture
     level 2026-10-22: `source` and `platform`);
   - task 6, the other products.

Blockers:
- **TROPOMI:** done. All 19 stores were finalized 2026-10-18 (run log above).
- **GOSAT:** done 2026-10-19 (run log below).
- **GOSAT-2:** done 2026-10-22 (run log below).

### GOSAT run log (2026-10-19)

No bench: the whole record (~2 GB raw) is far smaller than the TROPOMI bench
month, so the user approved going straight from the fixture to production.
Both jobs ran on the develop queue with 4 cores, 16 GB and a 1 h limit, from
commit `8398108`.

```bash
bash -lc 'cd ~/work/data_engineering/data_engineering_wiso-sat && CONFIG=config/gosat/config_zarr.yaml QUEUE=develop NCPUS=4 MEM=16GB WALLTIME=01:00:00 ./submit_wisosat_zarr.sh'
bash -lc 'cd ~/work/data_engineering/data_engineering_wiso-sat && CONFIG=config/gosat/config_zarr.yaml VERIFY=1 QUEUE=develop NCPUS=4 MEM=16GB WALLTIME=01:00:00 AFTER=7874257.desched1 ./submit_wisosat_zarr.sh'
```

| job | what | wall | peak memory | result |
| --- | --- | --- | --- | --- |
| 7874257 | build | 2 min 1 s | 0.51 GiB main, 0.12 GiB per worker | 11 stores, 4,498 days, 13 commits each; nothing masked |
| 7874258 | verify | 52 s | 0.9 GiB | **359 checks, 0 failures**; 14 arrays bit for bit over 8,856,028 obs |

- **Cost:** ~0.2 core-hours for both jobs.
- **Listing:** 4,498 days, 2009-04-23 to 2021-12-31, with the 138 declared
  missing days and no others.
- **Bounds:** lat -87.84 to 84.89, lon -180.00 to 180.00.
- **Size:** 946 MB. The geolocation store is 407 MB, the kernel 175 MB, the
  a priori 185 MB, and `pressure_weight` only ~1 MB: it compresses almost
  entirely, being nearly a fixed fraction of surface pressure (gosat.md).
- **Finalized 2026-10-19,** with the user's sign-off and nothing
  unreachable, so no `--gc`:
  - `--attrs --apply` committed the attributes to all 11 stores;
  - `--tag v3.0.1-verified-20261019 --apply` tagged those commits;
  - `--status`: every store reports "remaining nothing, finalized".

### GOSAT rework: `pressure` out of the geolocation store (2026-10-19)

The user moved `pressure` into its own variable store in every product
(style_guides `65ac688`). The finalized geolocation store was moved to
`/glade/derecho/scratch/kheyblom/data/wisosat/zarr/gosat_backup_20261019/`,
then rebuilt without it, with the new `pressure` store, from granule 0, at a
clean `5261f04`. The other 10 stores were no-ops.

| job | what | wall | peak memory | result |
| --- | --- | --- | --- | --- |
| 7874907 | build | 1 min 44 s | 0.33 GiB main, 0.13 GiB per worker | geolocation and `pressure`, 4,498 granules, 13 commits each; nothing masked |
| 7874909 | verify `--stores pressure` (with geolocation) | 2 min | 0.29 GiB | **102 checks, 0 failures**; bounds as before |
| 7874913 | verify `--phases structure,index`, all 12 stores | 8 s | 0.11 GiB | **373 checks, 0 failures**: one obs axis and index |

- **Cost:** ~0.25 core-hours. A first `structure,index` job (7874911) was
  chained to a guessed job id; it was deleted before it ran and resubmitted.
- **Finalized 2026-10-19** with the user's sign-off: `--attrs --apply`, then
  `--tag v3.0.1-verified-20261019 --apply`, on the two new stores; nothing
  unreachable. `--status`: all 12 stores "remaining nothing, finalized".
- The backup is kept until the user approves deleting it.

### GOSAT-2 run log (2026-10-22)

The GOSAT reader and key under `product: gosat2`, `source: gosat`, with
`platform: GOSAT2` checked on every file (fixture passed the same day, 97
cases over three products). No bench, as for GOSAT. Both jobs on develop, 4
cores, 16 GB, a 30 min limit, from a clean `4becc57`:

```bash
bash -lc 'cd ~/work/data_engineering/data_engineering_wiso-sat && CONFIG=config/gosat2/config_zarr.yaml QUEUE=develop NCPUS=4 MEM=16GB WALLTIME=00:30:00 ./submit_wisosat_zarr.sh'
bash -lc 'cd ~/work/data_engineering/data_engineering_wiso-sat && CONFIG=config/gosat2/config_zarr.yaml VERIFY=1 QUEUE=develop NCPUS=4 MEM=16GB WALLTIME=00:30:00 AFTER=7907020.desched1 ./submit_wisosat_zarr.sh'
```

| job | what | wall | CPU | peak memory | result |
| --- | --- | --- | --- | --- | --- |
| 7907020 | build | 44 s | 30 s | 1.4 GiB | 12 stores, 1,010 days, 3 commits each; nothing masked |
| 7907023 | verify | 2 min 15 s | 6.9 min | 1.4 GiB | **478 checks, 0 failures**; 14 arrays bit for bit over 1,620,006 obs; every file `v3.0.1` and `GOSAT2` |

- **Cost:** ~0.2 core-hours reserved for both jobs.
- **Listing:** 2019-02-05 to 2021-12-31, the 51 declared missing days and no
  others.
- **Finalized 2026-10-22** with the user's sign-off on each step: `--attrs
  --apply`, `--tag v3.0.1-verified-20261022 --apply`; `--gc` dry run found
  nothing unreachable, so no `--apply`. `--status`: all 12 stores "remaining
  nothing, finalized". 163 MB on disk.

### TROPOMI model-comparison stores: production (2026-10-19 to 10-22)

The six 2-D stores (both column kernels, both a priori partial columns,
`dry_air_partial_column`, `pressure`), each in a process of its own, sharded,
blosc zstd 5 + shuffle, 10 granules per commit. The 19 finalized stores were
no-ops. All jobs develop.

| jobs | what | wall | result |
| --- | --- | --- | --- |
| 7877706-7877712, 7882022 (B1-B8) | build, 8 cores, 128 GB | B1-B7 6 h each (walltime, -29, as planned), B8 3 h 27 min (exit 0) | each store 38,645 granules, 32,657,526,234 obs, index identical to geolocation; no errors |
| 7882023, 7882024 (B9, B10) | build | ~1 min each, exit 0 | no-ops |
| 7901062 (V1) | verify the two kernels and `pressure`, 64 cores, 200 GB | 3 h 17 min | **184 checks, 0 failures** |
| 7901063 (V2) | verify the two priors and dry air (limit raised to 6 h, approved) | 3 h 44 min | **184 checks, 0 failures** |
| 7901064 (S) | `--phases structure,index`, all 25 stores | 1 min | **775 checks, 0 failures** |

- **Cost: ~815 core-hours** (build ~365, verify ~450), against 575
  estimated; the user approved the extra. The build ran ~32% slower per
  orbit than the bench month (~680-1,000 orbits/h per store), and verify
  used ~2x the bench's CPU per granule and store (64 processes on one node).
- **A parallel verify submission was cancelled** (7901053-7901055) within a
  minute, before any verdict: two verifies of one config share the evidence
  log, so they must run in sequence (now in CLAUDE.md).
- Memory: store processes peaked at 15.6-18.8 GiB; PBS counted up to the
  128 GB limit once (B5), with file cache, but every store committed to the
  end of that job.
- **Finalized 2026-10-22** with the user's sign-off on each step: `--attrs`
  (history names build revisions `4945839`, `157d4af`, `53c063b`, identical
  code), `--tag v8.1-verified-20261022`, `--expire` (3,865 build snapshots
  per store), `--gc` (**4.87 TiB freed**: superseded shards, old index
  chunks and manifests). `--status`: all 25 TROPOMI stores "remaining
  nothing, finalized". A post-gc `--phases structure,repository` over the six:
  225 checks, 0 failures.
- **Size: 19.6 TiB** live for the six (kernels 3.21 and 2.66 TiB, priors 3.66
  each, dry air 3.23, `pressure` 3.21). Each store holds ~7,795 chunk files, 8
  manifests and 2 snapshots, plus ~3,870 transaction logs and ~3,870
  `overwritten` entries that `--gc` keeps.
