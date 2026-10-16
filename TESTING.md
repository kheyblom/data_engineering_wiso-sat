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
| 3 | Production builds and verification, one product at a time | batch chain | TROPOMI: scale settings to decide. GOSAT: waits on the kernel naming pass |

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

## Tier 3: production (not yet planned in detail)

The Tier 2 figures set the job size and chain length. Then, per product:
1. The build, chained `afterany` if it needs more than one walltime.
2. The verifier, over every observation, chained after the build.
3. `finalize_wisosat_zarr.py`: `--status`, then `--attrs`, `--tag`, and `--gc`
   (dry run first).

Blockers:
- **TROPOMI:** no data blockers remain after the re-download, the audit and
  the bench (findings 5, 7 and 8; Tier 2). The scale settings come first:
  workers, chunks, queue and walltime.
- **GOSAT:** the whole record is ~9,000 small files, so a single develop job
  covers build and verification. It waits on the cross-product naming pass,
  so that its kernel and a priori stores are built with the rest.
  - Building them later is possible: a new store resumes from zero on the same
    obs axis while the others are no-ops.
