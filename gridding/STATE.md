# STATE.md (gridding/): working state / handoff

Read this first in a new session. Update it whenever work lands.

## Where we are (2026-11-13)

- **AIRS v1: every gridding decision made, nothing built** (2026-11-13,
  with the user). The decisions, evidence and order of work are in
  [`../airs-gridding-decisions.md`](../airs-gridding-decisions.md) (D1-D8,
  all completed); the result is in `../docs/products/tropess.md`, "Gridding
  inputs, AIRS v1" (and R47); summary in "AIRS v1 decisions" below. The
  method doc gained "Sensors without a standard error" (Section 7), and
  `CLAUDE.md` the two rules from this work that hold for every sensor
  (derived inputs computed here; no valid σ, no standard error). The
  scripts behind the numbers are in `tools/survey/` (`airs_*.py`,
  `tropess_column_air.py`). That file replaced a Claude Docs doc
  ("AIRS gridding: decisions"), which is superseded.

- **TROPOMI 0.25° daily finalized** (2026-11-11; TESTING.md Tier 3): 2,945
  days (2017-11-08 to 2025-11-30), 17 spatial and 17 temporal stores, 134
  GiB each layout, under `/glade/derecho/scratch/kheyblom/data/wisosat/zarr/tropomi/l3/`
  (`spatial/`, `temporal/`; `l2/` beside `l3/`; moved from
  `wisosat/grid/tropomi/` to `zarr/tropomi/` on 2026-11-11, then into
  `l3/` the same day; user decision, root CLAUDE.md "Store layout");
  tag **`v8.1-verified-20261111`** on all 34. After each move,
  `finalize_grid_wisosat.py --relocate --apply` (signed off by the user)
  rewrote the path attributes (`related_store`, `source_l2_stores`,
  `rechunked_from`) on all 34 and appended the move to `history`: two
  commits after the tag. The tag stays on the snapshot before the moves,
  with the old paths; the values are the same. No new tag (user decision
  2026-11-11). Verify spatial 629 checks,
  temporal 1,513, 0 failures; `--gc` found nothing to collect. Rechunk
  float64 stores ran at the 64 GB memory request (TESTING.md): halve
  `block_rows` or ask for more memory for a longer record or finer grid.
  fixes: the verifier compares thresholds at the stored precision, and
  TROPOMI's cloudy row is optical thickness >= 0.3 (user decision, T24).
- **Pipeline** (2026-11-10): build, verify, finalize, rechunk, submit
  wrapper and the fixture test; layout and decisions in `CLAUDE.md`.
- **Design decisions** (user, 2026-11-10; recorded in `CLAUDE.md`,
  "Decisions"): common engine with per-product inputs, TROPOMI first;
  grid type, resolution and frequency (`day`, `<n>day`, `month`,
  `<n>month`) in config; periods counted from 1900-01-01; grid tokens
  `latlon_0p25x0p25` / `ease2_m25km`; `spatial/` + `temporal/`
  directories; 8 statistics + 9 sums per (grid, frequency); temporal =
  rechunk of the tagged spatial store; sampled verification. New
  nomenclature rows (14 variables: 5 statistics, 9 sums; `month`, `3day`) added in style_guides
  `8144058`.
- **TROPOMI method:** as decided 2026-11-09 (`../docs/technical/gridding-method.md`).
  The pipeline reproduces the drafting code on a full production day to
  1e-9 (TESTING.md).
- **The method doc** has its store table (Section 10) and the weight in mol.

## AIRS v1 decisions (user, 2026-11-13; not built yet)

Kept here while AIRS is in progress; once built, what users need goes
into the docs (`tropess.md`, the method doc) and this section is cut.

D1-D8 in [`../airs-gridding-decisions.md`](../airs-gridding-decisions.md)
(evidence, options, order of work); the result is in `../docs/products/tropess.md`,
"Gridding inputs, AIRS v1". They extend the engine; none applies to another
sensor without the user's approval.

- **Scope:** v1 only (RS and FS as separate products); v2 later.
- **Footprint (D1):** the 1.1° FOV projected onto WGS84 as a 32-vertex
  polygon, built here (model `airs_fov`) from four published geometry
  fields added to L2 (`airs_granule`, `airs_atrack`, `airs_xtrack`,
  `airs_view_ang`). `MAX_VERTICES` follows the vertex count. **Prototyped
  and validated against L1B 2026-11-13** (`tools/survey/airs_fov_polygon.py`
  is the model to port; `airs_fov_l1b.py`; logs
  `logs/airs_fov_*_20261113.log`; `tropess.md`, "Footprint model"): orbit
  model with one phase fit per file, scan plane perpendicular to the
  inertial heading, side from `airs_xtrack` (≤ 44 left), indices 0-based.
  **Height from the orbit phase, not 705.3 km (user decision 2026-11-13,
  revising 1.4):** the height runs 692-720 km over the record. Areas within
  about 1% of L1B's, common area ≥ 0.987. The eight L1B granules are in
  `/glade/derecho/scratch/kheyblom/data/wisosat_validation/airs_l1b/`
  (458 MB; delete only with the user's say).
- **δD (D2):** computed here from the 17-level profiles, never TROPESS's
  `dd_col_p`: per level (a level dimension, the surface level its own field)
  and as the H2O-weighted 850-250 hPa partial column
  (`water_vapor_column_delta_d_850_250hpa`, a new row); q and R linear in ln p,
  exact cuts at 850, 250 hPa and the surface; δD with 3.11e-4.
- **No σ (D3):** no standard error and no σ sums (`CLAUDE.md`; method
  Section 7).
- **Weight (D4):** overlap area × the layer's H2O partial column (mol),
  g = 9.80665 and dry-air M; companion H2O statistics.
- **Selection (D5):** `summary`: DOF > 1.1 (strict, float32), or DOF missing
  and `dd_col_p` written. No cloud limit.
- **Grid (D6):** 1° lat/lon (`latlon_1p0x1p0`), `day`; more on request.
- **Store sets (D7):** every overpass and daytime only (`day_night_flag ==
  1`, quality level `summary_daytime`), for RS and FS. **Approved exception,
  for the AIRS v1 gridded stores only:** the set goes in the version slot,
  `wisosat.airs.v_1.rs.daytime.day.latlon_1p0x1p0.<variable>.zarr`.

## Next

1. **TROPOMI first: 0.25° at day** (user decision 2026-11-10); the other
   sensors' decisions come after TROPOMI is built.
2. ~~Bench, production build, verify, finalize, rechunk, temporal finalize~~
   (done 2026-11-11).
3. Further TROPOMI grids or frequencies (EASE M25km, month, n-day) only on
   the user's request: each is a config entry and a build.
4. **Other sensors** need their gridding inputs decided by the user before
   any config (survey 2026-11-10, from the product docs). What each lacks
   against the method's five inputs (time, footprint polygon, column δD,
   noise-only σ, H2O column in mol m-2):
   - **SCIAMACHY:** corners (order unverified) and H2O column, but **no
     δD** is published and no exact σ can be derived (`sciamachy.md` P2,
     S4); WISO-SAT's selection needs per-file statistics.
   - **GOSAT, GOSAT-2:** centres only (~10 km circle, Sarkar et al.);
     column-averaged δD with a 1σ of undocumented kind; only XH2O (1e-6),
     absent on ~56% of δD soundings (G1) and sometimes negative (G8).
   - **AIRS v1: decided 2026-11-13; next is the order of work** at the end
     of `../airs-gridding-decisions.md`:
     1. ~~D1 prototype and L1B validation (1.2-1.6).~~ Done 2026-11-13
        (see "Footprint (D1)" above). For the engine port: the phase fit
        needs each row's AIRS day (the L2 granule = file, from the granule
        index), since a UTC day holds rows of two files; decide what a file
        with too few targets for a fit does.
     2. **`l2/`: the four geometry stores** for RS and FS v1 (nomenclature
        rows first, user review), verified, new tag. An `l2/` task: read
        `../l2/STATE.md` and `../l2/CLAUDE.md` first.
     3. Method doc (vertical product, column operator, per-level sums,
        `airs_fov` footprint), nomenclature rows, engine changes (the
        table in the decisions file), AIRS fixture, bench, production.
   - **CrIS (TROPESS):** as AIRS, once AIRS is built; SNPP RS and FS
     overlap 2021-02..05 (R26), so gridding both double counts.
   - **IASI, TES:** not built in L2 yet.
   Each needs: a footprint model (e.g. a centred circle of a stated
   diameter), the δ, σ and weight variables (or a decision to weight by
   area alone), its selection, and a "Gridding inputs" section in its
   product doc.
- **Environment:** `gridding/pyproject.toml` and `uv.lock` (shapely and
  pyproj named for the verifier); see the root CLAUDE.md, "How the halves
  connect".
