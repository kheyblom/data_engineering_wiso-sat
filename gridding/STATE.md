# STATE.md (gridding/): working state / handoff

Read this first in a new session. Update it whenever work lands.

## Start here: AIRS v1 production (approved 2026-11-14, nothing submitted yet)

Everything up to production is done and committed; the engine, fixture and
bench all pass. The user asked for this handoff so a new session runs
production. **Two tasks are already approved by the user (2026-11-14):
do them without asking again, exactly as written.** Everything after them
needs the user's sign-off as usual.

**Before anything:** from `gridding/`, `git status --short` shows nothing,
`bash -lc 'qstat -u $USER'` shows no job, and
`/glade/derecho/scratch/$USER/data/wisosat/zarr/airs/` holds only `l2/`
(no `l3/` yet). If any of that is not so, stop and tell the user.

**Approved task 1: delete the AIRS bench root.** It is throwaway (128
stores, 1.1 GiB); its results are in TESTING.md ("AIRS bench") and its logs
stay in `logs/`. Look, then delete only this directory:

```bash
ls /glade/derecho/scratch/$USER/data/wisosat/bench/zarr/airs/l3
rm -rf /glade/derecho/scratch/$USER/data/wisosat/bench/zarr/airs
```

**Approved task 2: submit the eight production jobs.** Four builds
(develop, 8 cores, 32 GB; walltime 3 h for the RS sets, 2 h for the FS
sets), each followed `afterany` by its spatial verify (develop, 1 core, 32
GB, 1 h). The four sets write different stores, so the builds may run side
by side. The build refuses a dirty `gridding/` tree at submit and again at
start: keep the tree clean until every build has started.

```bash
bash -lc 'cd /glade/work/$USER/data_engineering/data_engineering_wiso-sat/gridding &&
for spec in "airs_rs/config_grid.yaml 03:00:00" "airs_rs/config_grid_daytime.yaml 03:00:00" \
            "airs_fs/config_grid.yaml 02:00:00" "airs_fs/config_grid_daytime.yaml 02:00:00"; do
  set -- $spec; C=config/$1
  b=$(CONFIG=$C QUEUE=develop NCPUS=8 MEM=32GB WALLTIME=$2 ./submit_grid_wisosat.sh) && echo "$C build $b" &&
  v=$(CONFIG=$C VERIFY=1 LAYOUT=spatial AFTER=$b QUEUE=develop NCPUS=1 MEM=32GB WALLTIME=01:00:00 ./submit_grid_wisosat.sh) &&
  echo "$C verify $v"
done'
```

- **What was approved:** these eight jobs, the stores under
  `/glade/derecho/scratch/$USER/data/wisosat/zarr/airs/l3/spatial`, and
  the cost: expected ~35 core-hours (bench: RS ~1.5 h, RS daytime ~1.2 h,
  FS sets ~0.7 h each on 8 cores), at most ~84 if every job hit its
  walltime; ~95 GiB of spatial stores. If a job will cost more than that,
  or develop will not take four builds at once, say so before changing
  anything. A build stopped by walltime resumes: resubmit it `AFTER` the
  stopped one, and tell the user.
- **Attribute texts:** the build writes each store's title, summary and
  per-variable comments from `config/airs_{rs,fs}/config_grid{,_daytime}.yaml`
  (`attrs`, `variable_attrs`). The user was offered a read of them before
  production and chose to go ahead.
- **Expected in the logs** (`logs/grid_airs_<set>.log`,
  `logs/verify_grid_airs_<set>.log`): 6,425 days for RS, 1,946 for FS;
  "missing an input" 0 or 1 a day (the masked first profile of a Standard
  file, R22); each verify ending `N checks, 0 failures` and `stores
  verified`. Selected rows over the record should come to RS 11,065,071
  (daytime 5,066,094) and FS 19,126,176 (daytime 18,423,705), less the R22
  rows (`tropess.md`, "Gridding inputs, AIRS v1").
- **A build may stop on purpose** on something the bench months did not
  hold: a level slot above a surface holding another pressure
  (`utils/profiles.py`), or an AIRS day with no sound orbit-phase fit
  within 30 days (`utils/airs_fov.py`). Neither is to be worked around:
  measure what the data holds and put it to the user.
- **A verify failure** is investigated, not tolerated: the bench's only
  failures came from the two orbit-phase fits stopping apart (TESTING.md
  finding 1, fixed). `verify.sum_rtol` exists but no config sets it.

**Then, each step with the user's sign-off** (CLAUDE.md, the order for a
product; one finalize action per invocation, dry run first):

1. Report the builds and verifies (wall, days, rows, checks) and add an
   "AIRS production" run log to TESTING.md Tier 3.
2. Finalize spatial for each of the four configs: `--status`, `--attrs`,
   `--tag v1-verified-<YYYYMMDD>`, `--gc` (dry run of each first; every
   `--apply` signed off).
3. Set `temporal.source_tag` to that tag in the four configs (it is `null`
   now), commit, and show the user the rechunk jobs: one per config, 1
   core, **48 GB** (a block of an RS level sum is a 10.7 GB buffer), then
   `VERIFY=1 LAYOUT=temporal` `AFTER` each. Bench: about a minute for a
   month; the RS record reads each spatial store five times.
4. Finalize temporal the same way.
5. Wrap up: cut "AIRS v1 decisions" below (the docs carry it), update
   `../TASKS.md` and the root CLAUDE.md if a line there names AIRS
   gridding, and ask the user about the L1B validation granules (458 MB,
   `/glade/derecho/scratch/$USER/data/wisosat_validation/airs_l1b/`).

## Where we are (2026-11-14)

- **AIRS v1: engine, fixture and bench done; production approved, not
  run** (above). Decisions D1-D9 and their evidence:
  [`../airs-gridding-decisions.md`](../airs-gridding-decisions.md); what
  users need: `../docs/products/tropess.md` ("Gridding inputs, AIRS v1",
  "Gridded stores", "Footprint model") and the method doc (profile
  sensors: Sections 2, 5, 6, 10). What was built on 2026-11-13/14:
  - the footprint model, validated against AIRS L1B (D1; the height from
    the orbit phase, a revision the user approved);
  - L2: four footprint stores per stream, built, verified, finalized
    (`../l2/TESTING.md`), tag `v1-verified-20261113` on those only, so
    gridding reads L2 at a tag per store (`l2.store_tags`);
  - the engine's second method, `profile` (`CLAUDE.md`, "Two methods"),
    with the verifier's own version of it; TROPOMI unchanged;
  - an AIRS fixture and five test cases: `validation/test_pipeline.py`
    passes 14 cases (~7 min);
  - the 25 store names, approved by the user (style_guides `540b122`);
  - the bench (TESTING.md, "AIRS bench"): RS June 2010 and FS June 2022
    build, verify, rechunk and verify again with 0 failures, once both
    orbit-phase fits were made to reach the least-squares minimum
    (finding 1). The chunks in the configs stand.

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

## AIRS v1 decisions (user, 2026-11-13/14; cut this section once production is finalized)

Kept here while AIRS is in progress; what users need is already in the
docs (`tropess.md`, the method doc).

D1-D9 in [`../airs-gridding-decisions.md`](../airs-gridding-decisions.md)
(evidence, options, order of work); the result is in `../docs/products/tropess.md`,
"Gridding inputs, AIRS v1". They extend the engine; none applies to another
sensor without the user's approval.

- **Scope:** v1 only (RS and FS as separate products); v2 later.
- **Footprint (D1):** the 1.1° FOV projected onto WGS84 as a 32-vertex
  polygon, built here (model `airs_fov`) from four published geometry
  fields added to L2 (`airs_granule`, `airs_atrack`, `airs_xtrack`,
  `airs_view_ang`). **Prototyped and validated against L1B 2026-11-13**
  (`tools/survey/airs_fov_polygon.py`, ported to `utils/airs_fov.py`;
  `airs_fov_l1b.py`; logs
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
   - **AIRS v1:** decided, built to the bench; production is the handoff
     at the top of this file. One config per store set: the two sets of a
     stream read the same L2 days, so they could share a pass only with an
     engine change (not planned).
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
