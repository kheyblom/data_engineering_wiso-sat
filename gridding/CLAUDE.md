# CLAUDE.md (gridding/)

Guidance for Claude Code when working in `gridding/`, the half of
`data_engineering_wiso-sat` that grids the finalized L2 stores. The root
[CLAUDE.md](../CLAUDE.md) holds the products in scope and the rules both
halves share; this file holds what is particular to gridding.

- Read [STATE.md](STATE.md) first in a new session: it is the gridding
  handoff, so keep it current. Testing tiers and findings:
  [TESTING.md](TESTING.md).
- **Run everything from `gridding/`.** It has its own environment
  (`pyproject.toml`, `uv.lock`, `.venv`), separate from `l2/`'s: a
  dependency change here never calls for the L2 fixture test.
- **The method** is [`../docs/technical/gridding-method.md`](../docs/technical/gridding-method.md)
  (user-facing, sensor-general). How it was decided, with the numbers, is
  `../notebooks/drafting/gridding-notes.md` ("Decisions"); its drafting code
  (`tropomi_tools.py`) is now in `utils/` and is no longer the reference.

## Layout (built 2026-11-10)

```
grid_wisosat.py              # build: one pass over the UTC days writes every grid x frequency (spatial stores)
rechunk_wisosat.py           # spatial (at temporal.source_tag) -> temporal stores, region writes
verify_grid_wisosat.py       # read-only; --layout spatial|temporal; sampled (see below)
finalize_grid_wisosat.py     # --layout ...; --status, then --attrs, --tag, --gc (dry run without --apply);
                             # --relocate after a move rewrites the path attributes
submit_grid_wisosat.sh       # CONFIG=... [VERIFY=1 LAYOUT=...|RECHUNK=1] ./submit_grid_wisosat.sh; show the user first
nomenclature-key_grid.md     # machine read: quantity -> canonical name, units, kind, dtype; input units; frequencies
products/<source>.py         # per product: quality levels (selection_stores, select), FOOTPRINT_MODELS
utils/                       # config, nomenclature, periods, grids, footprints, sums, l2 (reader), stores
config/<product>/config_grid*.yaml
validation/stage_fixture.py, validation/test_pipeline.py
tools/survey/                # one-off evidence scripts behind decisions (each docstring: what, and how to run)
```

The order for a product: build -> verify spatial -> finalize spatial
(`--attrs`, `--tag`, `--gc`) -> set `temporal.source_tag` to that tag ->
rechunk -> verify temporal -> finalize temporal. Finalize is one action per
invocation from a login node; **Claude runs the steps, the user signs off on
each `--apply`** (as l2/, user decision 2026-10-19).

## Inputs: the L2 stores only

- Gridding reads **finalized, tagged** L2 stores and nothing else from L2
  (user decision 2026-11-10): their `obs` axis, granule index and
  attributes, at the config's `l2.tag`. It never imports `l2/` code and
  never writes an L2 store. Each gridded store records the snapshot the tag
  names in every L2 store read (`source_l2_snapshots`); a resume and the
  verifier refuse if that changes.
- A day is selected by observation time, never by granule (TROPESS granules
  are not UTC days, `tropess.md` R27): the granule index's earliest/latest
  times give the obs span, then rows are kept by time.
- The L2 stores and their tags are listed in `../l2/STATE.md`; what each
  variable means, and every known data issue, is in
  `../docs/products/<product>.md`.
- Quality filtering and thresholds belong here, not in L2: the L2 stores
  keep every observation as published (style guide). A config's
  `selection` names the product's quality level (`products/<source>.py`)
  and any thresholds (TROPOMI T23: H2O column at most 5,551 mol m-2).

## Decisions (user, 2026-11-10)

- **Common engine, per-product inputs.** One codebase for every sensor:
  the config names the L2 variable behind each input (`delta_d`,
  `delta_d_uncertainty`, `weight`) and the footprint model; the product
  module holds its quality levels. Only TROPOMI has all five inputs today
  (corners, column δD, noise σ, H2O column); every other sensor needs its
  gridding inputs decided first (STATE.md lists what each lacks). Only the
  `corners` footprint model exists: add another when a sensor needs it.
- **Configurable** grid type (`latlon` resolution Δ dividing 180, or an
  NSIDC EASE-Grid 2.0 global grid by name), resolution, and frequency
  (`day`, `<n>day`, `month`, `<n>month`). Each grid is made from L2, never
  from another grid; one pass reads each day once for every grid.
- **Periods** are blocks counted from 1900-01-01 (n-day exactly n days,
  same boundaries for every sensor and year); n-month blocks start in
  January, n divides 12. A period's sums are its days' sums.
- **Names:** `<layout>/wisosat.<product>.<version>.<frequency>.<grid_name>.<variable>.zarr`
  under `directories.zarr` = `.../data/wisosat/zarr/<product>/l3/`, beside
  the product's L2 stores in `l2/` (user decision 2026-11-11; the root
  CLAUDE.md, "Store layout"),
  grid tokens `latlon_0p25x0p25` and `ease2_m25km` (NSIDC's name, lower
  case), layout `spatial/` or `temporal/` (GLEAM/MSWEP's exception,
  approved for the WISO-SAT grids). The version is the L2 version token.
- **Stores:** the 8 statistics (float32; `observation_count` int32) and
  all 9 per-cell sums (float64), 17 stores per (grid, frequency, layout).
  The weight is w = overlap area × H2O column in **mol**. Rows in
  `nomenclature_data.md` added 2026-11-10 (style_guides `8144058`).
- **Chunks** (after the bench): spatial 4 periods x the whole grid
  (`periods_per_commit` a multiple of 4), time coordinates a year per
  chunk; temporal the whole record x 20 x 20 cells. Keeps each store under
  ~1,000 files.
- **Temporal store = rechunk of the tagged spatial store**, not a second
  gridding; an exception to "each store built from its source", approved.
- **Every value falls in a selection row** (2026-11-10, TROPOMI T24):
  TROPOMI's cloudy row is optical thickness >= 0.3, not Table 1's > 0.3,
  and every threshold is compared at the stored precision, in the build
  and the verifier alike. A new product's selection is checked for such
  gaps between its rows.
- **Verification is sampled** (approved exception to "every observation,
  not a sample", for gridding): structure of every store in full; values
  on sampled periods recomputed from L2 by independent code (shapely,
  pyproj, pandas); temporal stores compared with spatial on sampled tiles
  x periods. `verify.samples` / `verify.seed` in config.

## AIRS v1 decisions (user, 2026-11-13; not built yet)

D1-D8 in [`../airs-gridding-decisions.md`](../airs-gridding-decisions.md)
(evidence, options, order of work); the result is in `../docs/products/tropess.md`,
"Gridding inputs, AIRS v1". They extend the engine; none applies to another
sensor without the user's approval.

- **Scope:** v1 only (RS and FS as separate products); v2 later.
- **Footprint (D1):** the 1.1° FOV projected from 705.3 km onto WGS84 as a
  32-vertex polygon, built here (model `airs_fov`) from four published
  geometry fields added to L2 (`airs_granule`, `airs_atrack`,
  `airs_xtrack`, `airs_view_ang`); validated once against a few L1B
  granules (download shown to the user first). `MAX_VERTICES` follows the
  vertex count.
- **δD (D2):** computed here from the 17-level profiles, never TROPESS's
  `dd_col_p`: per level (a level dimension, the surface level its own field)
  and as the H2O-weighted 850-250 hPa partial column
  (`water_vapor_column_delta_d_850_250hpa`, a new row); q and R linear in ln p,
  exact cuts at 850, 250 hPa and the surface; δD with 3.11e-4.
- **No σ (D3):** no standard error and no σ sums (method Section 7).
- **Weight (D4):** overlap area × the layer's H2O partial column (mol),
  g = 9.80665 and dry-air M; companion H2O statistics.
- **Selection (D5):** `summary`: DOF > 1.1 (strict, float32), or DOF missing
  and `dd_col_p` written. No cloud limit.
- **Grid (D6):** 1° lat/lon (`latlon_1p0x1p0`), `day`; more on request.
- **Store sets (D7):** every overpass and daytime only (`day_night_flag ==
  1`, quality level `summary_daytime`), for RS and FS. **Approved exception,
  for the AIRS v1 gridded stores only:** the set goes in the version slot,
  `wisosat.airs.v_1.rs.daytime.day.latlon_1p0x1p0.<variable>.zarr`.

## Rules particular to gridding

- **The style guide's "Gridded data" section governs** (with its General
  rules), not its Level 2 section: zarr, and separate stores optimized for
  spatial and for temporal retrieval.
- **WISO-SAT is not the reference** (user decision 2026-11-04). Agreement
  with Sarkar et al. (2026) is never a criterion for a gridding choice.
- **Surveys of L3 practice use online sources only**: not WISO-SAT, and not
  the upstream L3 files on disk (`TROPOMI_averaged_files` and the others the
  root CLAUDE.md lists as out of scope).
- **Builds start only from a clean commit of `gridding/`** (as l2/): every
  commit is stamped `@ <revision>`; only fixture configs set
  `allow_dirty_tree` (the test checks). Uncommitted `l2/`, `docs/` or root
  work does not block a build.
- **Empty cells:** statistics NaN, sums 0, `observation_count` 0. A sum
  over no footprints is 0, and it must add over days.
- **Test after any change to `gridding/`'s code or lock**, from
  `gridding/`: `uv run python validation/stage_fixture.py` once (it refuses
  to restage over an existing fixture), then
  `TMPDIR=/glade/derecho/scratch/$USER/tmp uv run python validation/test_pipeline.py`
  (9 cases, ~5 min, login node).
- **A store's last period can be partial** (the record ends inside it;
  `time_coverage_end` says where). A build does not reopen a written
  period, so extending the L2 record later needs that period's stores
  rewound first.

## Carried over from GLEAM / MSWEP / l2

- Spatial stores append `periods_per_commit` periods per commit and resume
  from their own `time_bounds`; temporal stores are a skeleton plus one
  region commit per `temporal.block_rows` rows, resumed from the commit
  messages. Writes are numpy, so builds leave no fork snapshots.
- Delete a fixture store before re-running it: builds resume, so a complete
  store is a silent no-op.
- `finalize --attrs` merges root attributes only; it cannot drop variable
  attributes. It credits only a passing verify of the same layout
  (`logs/verify_<log_file>`): never run two verifies of one config at once.
- `logs/` is evidence (gitignored): never delete or move it.
- xarray drops a lazy variable's `coordinates` list when writing a
  skeleton: `rechunk_wisosat.py` carries the spatial store's over, or EASE
  stores lose `lat(y)`/`lon(x)` as coordinates (found 2026-11-10).
