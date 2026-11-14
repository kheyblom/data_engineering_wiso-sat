# STATE.md (gridding/): working state / handoff

Read this first in a new session. Update it whenever work lands.

## Where we are (2026-11-13)

- **AIRS v1: the engine grids it end to end on a fixture; no production
  store yet** (2026-11-13, with the user). Decisions D1-D9 and their
  evidence: [`../airs-gridding-decisions.md`](../airs-gridding-decisions.md);
  the result for users: `../docs/products/tropess.md` ("Gridding inputs,
  AIRS v1", "Gridded stores", "Footprint model") and the method doc
  (profile sensors: Sections 2, 5, 6, 10). Done the same day:
  - the footprint model prototyped and validated against AIRS L1B (D1;
    height from the orbit phase, a revision the user approved);
  - L2: four footprint stores per stream built, verified, finalized
    (`../l2/TESTING.md`), tag `v1-verified-20261113` on those only;
  - the engine's second method, `profile` (`CLAUDE.md`, "Two methods"):
    column operator, level and surface groups, `airs_fov`, a key per
    config, store sets, L2 tags per store, the verifier's own profile
    method; TROPOMI unchanged;
  - an AIRS fixture and five test cases (`TESTING.md`): 14 cases pass.
  The 25 new store names (D9, 9.3) were approved by the user on 2026-11-14
  (style_guides `540b122`). **Bench submitted 2026-11-14** (RS June 2010,
  FS June 2022; `config/airs_*/config_grid_bench.yaml`; results go in
  TESTING.md Tier 2).

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

## AIRS v1 decisions (user, 2026-11-13; engine built, production not)

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
  (`water_vapor_column_delta_d_850_250hpa`, a new row); q and HDO (R·q) linear in ln p,
  exact cuts at 850, 250 hPa and the surface; δD with 3.11e-4.
- **Stores (D9):** 32 per set, grid, frequency and layout: 14 column, 12
  level (the four sums beyond 2.7 added), 6 surface statistics.
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
     2. ~~`l2/`: the four geometry stores for RS and FS v1.~~ Done
        2026-11-13: `granule_number_level_1b`, `scanline_index`,
        `ground_pixel_index`, `sensor_view_angle`, built, verified and
        finalized (`../l2/TESTING.md`). **Their tag is
        `v1-verified-20261113`; the other 19 stores of each stream keep
        `v1-verified-20261023` (user decision): the engine must read L2 at
        a tag per store** (`l2.tag` plus per-store overrides; today
        `utils/l2.py` takes one tag).
     3. ~~D9, the method doc, the engine changes, the AIRS fixture.~~ Done
        2026-11-13 (see "Where we are").
     4. **Next, in order:**
        - ~~production configs for the four store sets~~ (written
          2026-11-13: `config/airs_{rs,fs}/config_grid{,_daytime}.yaml`;
          their attribute texts are user-facing and worth the user's read
          before production). One config per set: the two sets of a stream
          read the same L2 days, so they could share a pass only with an
          engine change (not planned);
        - a one-month bench each for RS and FS (job shown to the user
          first). It settles the chunks: at 1° a 2-D period is 0.26 MB
          (float32), so TROPOMI's 4 periods per chunk would make ~1,600
          files per RS store; to try: spatial `{time: 8, level: -1}`
          (~800 files, 66 MB raw per float64 level chunk) and temporal
          `{time: -1, level: 1, rows: 36, cols: 36}` (800 chunks per level
          store). `block_rows` must follow the temporal tile (36) and the
          memory of a level buffer (RS: 6,372 x 16 x rows x 360 x 8 B);
        - production, verify, finalize (`--attrs`, `--tag`, `--gc`),
          rechunk and the temporal finalize, each `--apply` signed off.
        **To watch in the bench and production logs:** days counted as
        "missing an input" beyond the one R22 row a day; a build stopping
        on a level slot that holds another pressure (`utils/profiles.py`)
        or on an AIRS day with no sound orbit-phase fit within 30 days
        (`utils/airs_fov.py`); and D5's check by date that the DOF-only
        rows (RS 1,939, FS 54,510) are the Standard-only days. Each worker
        fits the orbit phase of the AIRS days it touches (~0.3 s a day).
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
