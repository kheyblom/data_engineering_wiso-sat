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

## Tier 2: bench (not yet run)

To plan with the user: one month (31 days) of the production config on a
compute node, to measure per-day cost per grid, worker scaling, memory, and
commit time per (grid, frequency), and to size `num_workers`,
`periods_per_commit` and the job chain. Then a temporal rechunk of the bench
month to measure the region path.

## Tier 3: production (not yet run)

The production grids and frequencies are placeholders in
`config/tropomi/config_grid.yaml` until the user chooses them.
