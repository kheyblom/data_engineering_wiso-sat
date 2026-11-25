# STATE.md (gridding/): working state / handoff

Read this first in a new session. Update it whenever work lands.

## Where we are (2026-11-25)

- **In progress: requests W1-W3 from `isotopes_transpiration`**
  (`/glade/work/kheyblom/projects/isotopes_transpiration/docs/handoffs/data-engineering-requests.md`;
  GLEAM's G1 is built in `data_engineering_gleam` on the same 0.5° and 1°
  grids).
  - **W1, decided (user, 2026-11-25):** every WISO-SAT gridded name
    carries its set (`store_set` now required; gridding/CLAUDE.md
    "Names"); TROPOMI tokens `clear_or_low_cloud` and `clear`; the 34
    finalized 0.25° stores are renamed
    `wisosat.tropomi.v_8_1.day...` -> `...v_8_1.clear_or_low_cloud.day...`,
    title and summary name the set, then they are verified again and get a
    new tag (`v8.1-verified-<date>`).
  - **W1 done (2026-11-25):** the 34 stores renamed to
    `wisosat.tropomi.v_8_1.clear_or_low_cloud.day.latlon_0p25x0p25.<variable>.zarr`,
    values unchanged (evidence check 34/0), verified again (629 and 1,513
    checks, 0 failures), tag **`v8.1-verified-20261125`** on all 34 (they
    keep `v8.1-verified-20261111`); TESTING.md, "TROPOMI 0.25° renamed".
    `temporal.source_tag` stays `v8.1-verified-20261111`.
  - **W2, W3 builds running** (configs `e95abb0`: `config_grid_0p5_1p0.yaml`,
    `config_grid_clear.yaml`; chunks the same in cells as 0.25°, user
    decision): W2 job 8308418 (resume 8308419), W3 job 8308421 (resume
    8308422), develop, 18 cpus, 64 GB, 6 h. Then per config: verify
    spatial -> finalize -> `temporal.source_tag` -> rechunk -> verify ->
    finalize temporal. W3 also: `tools/verify_subset.py` (every cell-day,
    clear <= clear_or_low_cloud; tested on the fixture both ways), as a job.

- **AIRS v1 1° daily finalized** (2026-11-15; TESTING.md Tier 3, "AIRS
  production"): four store sets, `v_1.rs.all`, `v_1.rs.daytime`,
  `v_1.fs.all` and `v_1.fs.daytime` (the set token in the version slot is
  an approved exception for these stores only; `all` added 2026-11-14,
  user decision), 32 stores each per layout: 256 stores under
  `/glade/derecho/scratch/kheyblom/data/wisosat/zarr/airs/l3/` (`spatial/`
  65 GiB, `temporal/` 72 GiB), tag **`v1-verified-20261115`** on all.
  RS 6,425 days (2002-08-30 to 2020-04-01), FS 1,946 (2021-02-01 to
  2026-05-31). Verify spatial 1,196 checks, temporal 2,860, per set, 0
  failures; `--gc` found nothing to collect. ~19 core-hours. The daytime
  summaries were corrected after the rename by `finalize --text` (added
  for it, `1edfd51`; recorded in each store's `history`). Decisions D1-D9
  and their evidence: [`../airs-gridding-decisions.md`](../airs-gridding-decisions.md);
  what users need: `../docs/products/tropess.md` ("Gridding inputs, AIRS
  v1", "Gridded stores", "Footprint model") and the method doc. Memory at
  the limit twice (fs.daytime build 32 GiB of 32; fs.all rechunk 44 of
  48), likely page cache: size a longer or finer AIRS run with headroom.

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
   - **AIRS v1:** finalized 2026-11-15 (above). Further grids or
     frequencies, and v2, on the user's request. One config per store set:
     the two sets of a stream read the same L2 days, so they could share a
     pass only with an engine change (not planned).
   - **CrIS (TROPESS): the next candidate.** As AIRS (the profile method),
     but its footprint model, selection and store sets need the user's
     decisions first, and SNPP RS and FS overlap 2021-02..05 (R26), so
     gridding both double counts.
   - **IASI, TES:** not built in L2 yet.
   Each needs: a footprint model (e.g. a centred circle of a stated
   diameter), the δ, σ and weight variables (or a decision to weight by
   area alone), its selection, and a "Gridding inputs" section in its
   product doc.
- **Environment:** `gridding/pyproject.toml` and `uv.lock` (shapely and
  pyproj named for the verifier); see the root CLAUDE.md, "How the halves
  connect".
