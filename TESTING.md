# Validating the WISO-SAT L2 build

How the pipeline is tested before anything runs at production scale, what has
been found, and how to reproduce it. It is tiered like `data_engineering_mswep`
and `_gleam`, for the same reason: a bug found on a fixture costs seconds, and
the same bug found on the full TROPOMI record (30,800 orbits) costs
core-hours against a finite allocation.

| Tier | What it is | Cost | Status |
|------|-----------|------|--------|
| 0 | Guards that refuse a bad config or raw tree before anything is written | seconds | **passed** (2026-10-14, in the Tier 1 test) |
| 1 | Per-product fixtures, end to end: build, verify, resume, tamper, finalize | ~75 s, login node | **passed** (2026-10-14): 35 cases, TROPOMI and GOSAT |
| 2 | One real month of TROPOMI, production settings, throwaway stores | develop-queue job | **not run**: commands below, awaiting approval |
| 3 | Production builds and verification, one product at a time | batch chain | **blocked** for TROPOMI by the download gaps; GOSAT waits on the kernel naming pass |

Nothing below is a statement about production cost until Tier 2 has run.

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

### 5. The TROPOMI download is incomplete

Found while staging the bench. 692 orbit directories are empty, and 70 days
have no directory. Checked one by one against the upstream server:
- 353 empty orbits and 58 days are real upstream gaps, and are now declared;
- **339 orbits and 12 days exist upstream but are missing here.**

The production build refuses to run until they are downloaded. The lists are
in `docs/products/tropomi-download-gaps.md`. The record has 30,800 orbit
files, not 31,492.

### 6. A source `calendar` attribute blocks the time write

FOCAL's time carries `calendar: standard`, and xarray refuses to write a time
whose attributes already hold an encoding key. It is now kept as
`original_calendar`; the store's calendar is `proleptic_gregorian`.

## Tier 2: the TROPOMI bench (awaiting approval)

**What it is:** one real month, 2020-07: 395 orbits, ~1.25% of the record, no
missing days and five empty orbits, all real upstream gaps. It runs with the
production config's variables, chunks and settings
(`config/tropomi/config_zarr_bench.yaml`), into throwaway stores under
`/glade/derecho/scratch/$USER/data/wisosat_bench/`. The raw tree is 31
symlinks, made by `validation/stage_bench_tropomi.py`.

**What it measures,** and what each figure decides:

| measure | from | decides |
|---|---|---|
| wall time per orbit, build and verify | job logs (batch lines) | walltime and job chain length for 30,800 orbits |
| peak memory, main process and largest worker | `peak memory:` log line | `MEM`, and whether 8 workers fit a shared node |
| compressed bytes per store and per chunk | `du` of each bench store (17 small directories) | whether `chunks.obs` (16 MiB uncompressed) stays inside 5-40 MiB usefully once compressed, and the production footprint |
| read scaling | a second build at `num_workers: 16`, only if the first is I/O-bound | `num_workers` |

**Commands.** These are shown for approval and have **not been submitted**.
The build and its verification are chained `afterany`, so they never overlap.

```bash
# build: develop queue (shared node, charged per core), 8 cores, 1 hour
bash -lc 'cd ~/work/data_engineering/data_engineering_wiso-sat && \
  CONFIG=config/tropomi/config_zarr_bench.yaml QUEUE=develop NCPUS=8 MEM=32GB \
  WALLTIME=01:00:00 ./submit_wisosat_zarr.sh'
# verify, after the build: same shape
bash -lc 'cd ~/work/data_engineering/data_engineering_wiso-sat && \
  CONFIG=config/tropomi/config_zarr_bench.yaml VERIFY=1 QUEUE=develop NCPUS=8 \
  MEM=32GB WALLTIME=01:00:00 AFTER=<build job id> ./submit_wisosat_zarr.sh'
```

**Ceiling:** 2 jobs x 8 cores x 1 hour = 16 core-hours. The one-orbit read
measured on the login node (19 variables in 2.6 s, cold) suggests ~20 min per
job if reads scale across 8 processes. They may not, since the reads are
Lustre-bound; finding out is what the bench is for.

## Tier 3: production (not yet planned in detail)

The Tier 2 figures set the job size and chain length. Then, per product:
1. The build, chained `afterany` if it needs more than one walltime.
2. The verifier, over every observation, chained after the build.
3. `finalize_wisosat_zarr.py`: `--status`, then `--attrs`, `--tag`, and `--gc`
   (dry run first).

Blockers:
- **TROPOMI:** the 339 orbits and 12 days missing from the download (finding
  5).
- **GOSAT:** the whole record is ~9,000 small files, so a single develop job
  covers build and verification. It waits on the cross-product naming pass,
  so that its kernel and a priori stores are built with the rest.
  - Building them later is possible: a new store resumes from zero on the same
    obs axis while the others are no-ops.
