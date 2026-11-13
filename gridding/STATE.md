# STATE.md (gridding/): working state / handoff

Read this first in a new session. Update it whenever work lands.

## Where we are (2026-11-13)

- **AIRS v1: every gridding decision made, nothing built** (2026-11-13,
  with the user). The decisions, evidence and order of work are in
  [`../airs-gridding-decisions.md`](../airs-gridding-decisions.md) (D1-D8,
  all completed); the result is in `../docs/products/tropess.md`, "Gridding
  inputs, AIRS v1" (and R47), and in `CLAUDE.md`, "AIRS v1 decisions". The
  method doc gained "Sensors without a standard error" (Section 7). The
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
     1. **D1 prototype and L1B validation (1.2-1.6).** Write the polygon
        code (1.1° cone, WGS84, 705.3 km, 32 vertices) with both ways of
        finding the cross-track direction (per-granule fit; orbit model)
        and the side from `airs_xtrack`. Compare with polygons from L1B
        geometry (`satheight`, `sat_lat`/`sat_lon`, `satazi`, `scanang`)
        on a handful of granules, e.g. from RS 2010-06-15 and FS
        2022-06-01. The raw files give each target's granule, scan and
        cross-track indices (0-based; L1B's are 1-based: check), and v2
        names its `l1b_filename`. TROPESS used AIRS L1B `AIRIBRAD`
        (ATBD Table 2). **Show the user the download before running it**
        (Earthdata; the `access_tropess` codebase did the TROPESS
        downloads).
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
