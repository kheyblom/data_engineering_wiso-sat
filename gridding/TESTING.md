# TESTING.md (gridding/)

Testing tiers and findings for the gridding pipeline. Tiny fixture, then
bench, then production (root CLAUDE.md: the allocation is finite).

## Tier 1: fixture (login node, no allocation)

- **Data:** `validation/stage_fixture.py` copies TROPOMI orbits 14067-14069
  (2020-06-30 21:51 to 2020-07-01 ~03:00 UTC, 2,503,245 rows; orbit 14068
  crosses midnight, so a day edge and a month edge) out of the finalized L2
  stores at `v8.1-verified-20261018` into 14 small L2 stores tagged
  `fixture-20261110`, under
  `/glade/derecho/scratch/kheyblom/data/wisosat/fixture/gridding/l2/tropomi`.
  12 s.
- **Config:** `config/tropomi/config_grid_fixture.yaml`: 1° and EASE 25 km,
  day / 3day / month (6 targets, 102 stores per layout), one period per
  commit so two days make two append commits, 60-row rechunk blocks.
- **Test:** `validation/test_pipeline.py`, 8 cases (see its docstring).
  The verifier is watched failing: the same stores checked under a stricter
  H2O threshold must fail.

### Results

- **2026-11-10: 8 cases passed, 5.0 min** (login node). Build 26 s; spatial
  verify 1.8 min (2,822 checks: 10 sampled periods, every cell); rechunk
  1.1 min; temporal verify 5 s (4,012 checks).
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
  `/glade/derecho/scratch/kheyblom/data/wisosat/bench/grid/tropomi`,
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
