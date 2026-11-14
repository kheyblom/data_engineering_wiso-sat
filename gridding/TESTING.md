# TESTING.md (gridding/)

Testing tiers and findings for the gridding pipeline. Tiny fixture, then
bench, then production (root CLAUDE.md: the allocation is finite).

## Tier 1: fixture (login node, no allocation)

- **Data:** `validation/stage_fixture.py` copies TROPOMI orbits 14067-14069
  (2020-06-30 21:51 to 2020-07-01 ~03:00 UTC, 2,503,245 rows; orbit 14068
  crosses midnight, so a day edge and a month edge) out of the finalized L2
  stores at `v8.1-verified-20261018` into 14 small L2 stores tagged
  `fixture-20261110`, under
  `/glade/derecho/scratch/kheyblom/data/wisosat/fixture/gridding/l2/tropomi`
  (since 2026-11-11 `.../fixture/gridding/zarr/tropomi/l2`, beside the
  fixture's `l3/spatial/` and `l3/temporal/`).
  12 s.
- **Config:** `config/tropomi/config_grid_fixture.yaml`: 1° and EASE 25 km,
  day / 3day / month (6 targets, 102 stores per layout), one period per
  commit so two days make two append commits, 60-row rechunk blocks.
- **Test:** `validation/test_pipeline.py`, 9 cases (see its docstring).
  The verifier is watched failing: the same stores checked under a stricter
  H2O threshold must fail.

### Results

- **2026-11-10: 8 cases passed, 5.0 min** (login node). Build 26 s; spatial
  verify 1.8 min (2,822 checks: 10 sampled periods, every cell); rechunk
  1.1 min; temporal verify 5 s (4,012 checks).
- **2026-11-11: 9 cases passed** (login node), with case 9 `--relocate`
  added for the move to `zarr/<product>/{l2,spatial,temporal}/`. The fixture
  was moved by `mv` to that layout first. Case 9 moves both layouts to
  another root: `--status` reports stale paths; `--relocate` rewrites them;
  a second run does nothing; the tag keeps the old paths; values are
  unchanged; verify structure passes at the new root; then the layouts are
  moved back and relocated.
- **2026-11-10, method carried over intact:** the pipeline's 1° grid of the
  full UTC day 2020-07-01 from the production L2 stores, against the
  decided drafting code (`notebooks/drafting/tropomi_tools.py`
  `daily_overlaps` / `daily_statistics`, which the user reviewed): the same
  39,907 occupied cells and counts; δD, standard error, n_eff, H2O,
  coverage and footprint area within 1e-9 relative; spread within 8e-6 ‰
  absolute (float rounding in one-footprint cells, where it is 0). Day:
  11,963,030 rows, 3,360,002 pass `clear_or_low_cloud`, 22 over the H2O
  threshold, 4 polar, 3,359,976 gridded (the notes' 3,359,980 counts the 4
  polar ones). Grid of one day at 1° on a login node: 42 s including the
  read.

- **2026-11-13: 14 cases passed** (login node, ~7 min), with the AIRS
  fixture and cases 10-14 added (below). The nine TROPOMI cases passed
  unchanged after each engine change of the day (three runs).

### AIRS fixture (the profile method, 2026-11-13)

- **Data:** the same script stages AIRS v1 RS 2014-04-04 .. 04-08 (5,605
  rows) out of the finalized L2 stores into 13 small stores under
  `.../fixture/gridding/zarr/airs/l2`: tagged `fixture-20261113`, the four
  footprint stores `fixture-20261113-footprint` (a tag per store, as in
  production). 04-05 and 04-06 hold 12 and 13 retrievals: too few for the
  footprint model's orbit-phase fit.
- **Config:** `config/airs_rs/config_grid_fixture.yaml`: 1°, day / 3day (2
  targets, 64 stores per layout), key `nomenclature-key_grid_tropess.md`.
- **Cases 10-14:** units (column operator against a 200,000-step
  integral, the Summary boundary at DOF exactly 1.1, store-set names, tags
  per store); build (level dimension, counts by level, 3-day sums equal to
  their days', the carried phases); verify, and the daytime selection made
  to fail it; finalize, rechunk, temporal verify; the daytime store set
  built beside the full one and verified.
- **Results:** build 13 s (7 days, 32 + 32 stores); spatial verify 15 s
  (1,848 checks: every cell of 4 day and 3 three-day periods); temporal
  verify 3,928 checks.

### Findings (2026-11-13)

1. **Both orbit-phase fits must reach the least-squares minimum itself**
   (found on the fixture 2026-11-13, fixed after the bench 2026-11-14). The
   footprints depend on a fitted orbit phase, which the build fits by
   Gauss-Newton on spherical trigonometry and the verifier by scipy on unit
   vectors. The misfit is not zero at the minimum (~0.1°), so a fit with
   one-sided differences settles off it, and scipy with a badly scaled
   phase rate stopped early: the two phases differed by 1e-7° on RS and up
   to 6e-5° on an FS day. Sums then agreed only to 1e-8, and on the FS
   bench 7 of 972 checks failed (coverage of sliver overlaps on every
   sampled day, a kernel-diagonal mean near zero; absolute differences
   ~2e-8). With central differences run until the steps vanish, and the
   phase rate scaled by the scans' half-span in the verifier, the phases
   agree to ~1e-9° and the sums pass at 1e-10 (fail at 1e-11): the default
   `SUM_RTOL` of 1e-9 holds, and no AIRS config sets `verify.sum_rtol`. A
   profile-method statistic is also allowed an absolute difference of
   `SUM_RTOL` times its largest value, for means of signed values near 0.
2. **A day's own phase fit can be badly wrong where it has few targets**
   (`../docs/products/tropess.md`, "Footprint model"): RS 2014-12-13 (10
   retrievals within 134 scans) fits a phase rate 0.5% off, which is 25 km
   in orbit height. The rule (sound fit, or the nearest sound day's
   carried over) came from this; case 11 pins it on the fixture's two tiny
   days.
3. **The approved wording of the column interpolation did not match its
   evidence** (D2, 2.1): "q and R linear in ln p" against a script that
   interpolated q and R·q. They differ by a median 2 ‰. Put to the user;
   q and HDO it is (`../airs-gridding-decisions.md`).
4. **The nominal 705.3 km height did not hold** (D1, 1.4): L1B shows
   692-720 km over the record. Put to the user; the height now comes from
   the orbit phase.

## Tier 2: bench (planned 2026-11-10)

The first TROPOMI build is **0.25° at day** (user decision 2026-11-10).

- **Measured first (login node, 2026-11-10):** one UTC day (2020-07-01) at
  0.25° in one worker: 35 s to read and grid (47 s with start-up), peak RSS
  2.1 GiB; 514,632 occupied cells (the drafting notes' number), 8,285,606
  (footprint, cell) pairs. The verifier's full-day recompute could not be
  measured there: the login node's per-user cap (~10 GiB) was already 7.1
  GiB used by VS Code extensions, and the recompute needs more than the
  rest. It is measured in the bench instead (reads are now chunk-wise with
  the selection applied while reading, and the clipping is in blocks of
  `verify.max_pairs`).
- **Config:** `config/tropomi/config_grid_bench.yaml`: production limited to
  July 2020 (31 days), bench root
  `/glade/derecho/scratch/kheyblom/data/wisosat/bench/grid/tropomi`
  (`.../bench/zarr/tropomi/l3` in the config since 2026-11-11),
  `num_workers: 16`, 5 verify sample days.
- **Jobs** (develop queue, shared node, billed per cpu):
  1. build: `NCPUS=18 MEM=64GB WALLTIME=01:00:00`;
  2. verify spatial, `AFTER` the build: `NCPUS=2 MEM=32GB WALLTIME=01:00:00`;
  3. on a login node, with the user's sign-off: finalize spatial
     (`--attrs`, `--tag bench-spatial`);
  4. rechunk: `RECHUNK=1 NCPUS=2 MEM=32GB WALLTIME=00:30:00`, then verify
     temporal.
- **To measure:** per-day cost and throughput at 16 workers, worker and
  main-process memory, commit time per 10 periods x 17 stores, store size
  per day, the verifier's cost per sampled day, and the rechunk's cost per
  store. These size production (`num_workers`, `periods_per_commit`, queue,
  walltime and the job chain over 2,945 days).

### Bench results (2026-11-10)

- **Build** (job 8142727, develop, 18 cpus, 64 GB, `a7a3402`): 31 days in
  2.9 min (walltime 3 min 18 s), 44.6 cpu-min (~86 cpu-s per day at 16
  workers, against 35 s alone on a login node), 43.8 GB peak (~2.7 GB per
  worker). Commits of 10 periods to 17 stores: 9.6 s for the first (store
  creation), then 1.5-2.1 s. 1.0-3.8 M footprints gridded a day into
  179-551 k cells; 24-173 a day over the H2O limit (T23).
- **Size:** 1,377 MiB for 31 days and 17 stores, ~44 MiB a day (float64
  sums ~3.7 MiB a day each, float32 statistics ~1.7, count ~0.5). Each
  store holds one chunk file per day: ~2,950 files per store over the
  record, at the edge of the ~2,000-3,000 per directory guidance.
- **Production estimate** (2,945 days, if throughput holds): ~4.6 h at 16
  workers on develop (two jobs chained afterany; develop caps at 6 h), ~90
  core-hours; ~130 GiB spatial plus as much temporal.
- **Verify** (job 8142728) failed at once: the submit wrapper checked the
  build's `num_workers` (16) against the verify job's 2 cpus. Fixed
  (`ba519f0`: the guard is for builds only).
- **Verify** (job 8142763, develop, 2 cpus, 32 GB): 10 min 14 s, 7.3 GB, 5
  days recomputed (~2 min each). 4 days matched in every cell; 2020-07-31
  failed in one cell: one footprint with optical thickness exactly 0.3
  (float32), which the build excludes (neither Table 1 row) and the
  verifier, casting to float64 (0.300000012), counted as low cloud. **The
  verifier was wrong** (TROPOMI T24): it now keeps float sources at their
  stored precision. The build, like the drafting code, was right. To rerun.

- **Rerun after T24** (low cloud at optical thickness >= 0.3, `fcb90c5`;
  bench root deleted first): build job 8143184, 2.8 min, 42.9 cpu-min, 45
  GB; spatial verify job 8143185, **510 checks, 0 failures**, 10.5 min, 7.8
  GB (~2 min per recomputed day). Finalize `--attrs` and `--tag
  bench-spatial` on all 17 stores.
- **Rechunk** (job 8143565, develop, 2 cpus): 17 stores x 4 blocks of 200
  rows in 3 min 16 s, 0.7 GB; ~3 s per block for 31 days. Temporal size
  1,450 MiB (spatial 1,377). **Temporal verify** (job 8143568): **1,457
  checks, 0 failures**, 38 s.
- **For production** (2,945 days, ~95 x the bench): the build ~4.6 h at 16
  workers; the rechunk reads the whole spatial store once per block of
  rows, ~5 min per block, ~5.7 h serially for 68 blocks, ~6.8 GB float64
  per 200-row block. Files per store directory: ~2,950 data chunks plus
  ~300 for each time coordinate in the spatial layout (over the ~2,000-3,000
  guidance); 36 x 72 = 2,592 tiles in the temporal layout.

## Tier 3: production

0.25° at day (user decision 2026-11-10), 4-day spatial chunks.

- **Build** (job 8144353, develop, 18 cpus, 64 GB, `0ebec61`): 2,945 days
  (2017-11-08 to 2025-11-30) in 281.9 min (walltime 4 h 42 min), 94.3
  cpu-hours, 43 GB peak, exit 0: ~85 core-hours billed, as the bench
  predicted. The safety job (8144354) found every store complete and did
  nothing (25 s). 134 GiB for the 17 spatial stores; per store 736 chunk
  files, 743 manifests, 247 snapshots and 247 transactions.
- **Verify spatial** (job 8144355, develop, 2 cpus): **629 checks, 0
  failures**, 28 min, 13.3 GB; 12 days recomputed in every cell (2017-11-08,
  2018-05-19, 2018-12-31, 2019-08-24, 2022-01-29, 2022-02-22, 2022-11-20,
  2022-12-27, 2023-07-24, 2024-01-20, 2024-06-24, 2025-11-30), ~2.5-3 min
  each.
- **The first sample was empty:** 2017-11-08 has no griddable observation
  (TROPOMI T25), so 11 days carried the check. The last day, 2025-11-30, is
  partial in L2 (557,280 rows; 21,378 cells).
- **Finalize spatial** (login node, user sign-off): `--attrs`, then `--tag
  v8.1-verified-20261111` on all 17 stores; `temporal.source_tag` set to it
  (`5a19e08`).
- **Rechunk** (job 8153237, develop, 2 cpus, 64 GB, `block_rows: 720`, so
  one block per store): 2 h 26 min, 4.1 cpu-hours, exit 0. The float32
  stores took ~150 s each (int32 count 74 s); the float64 sums 7-20 min
  each (420-1,188 s, erratic). Peak memory was reported at 64 GiB, the
  job's whole request: a float64 block is 24.4 GB (720 x 1,440 x 2,945 x 8
  B) before the read and encode buffers (not measured separately), so the
  sums ran at the limit, which likely explains their spread. Not a failure, but for a
  longer record or a finer grid, halve `block_rows` for the float64 stores or
  ask for more memory. Temporal stores: 134 GiB in all (as spatial), 11 GiB
  per float64 store, 2,599 chunk files each (36 x 72 = 2,592 tiles plus 7
  coordinate chunks), 3 snapshots.
- **Verify temporal** (job 8153238, afterany the rechunk, develop, 2 cpus):
  **1,513 checks, 0 failures**, 1 min 27 s, 2.1 GB; 8 tiles x 8 periods per
  store equal bit for bit to the tagged spatial store.
- **Finalize temporal** (login node, user sign-off): `--attrs`, then `--tag
  v8.1-verified-20261111` on all 17 stores; `--status` shows every store
  tagged with no attribute missing. `--gc` dry runs on both layouts: 0
  chunks, manifests or snapshots to collect, so no `--gc --apply`.
  **TROPOMI 0.25° daily is finalized.** The bench root was deleted
  2026-11-11 (user decision).
