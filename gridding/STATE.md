# STATE.md (gridding/): working state / handoff

Read this first in a new session. Update it whenever work lands.

## Where we are (2026-11-10)

- **Pipeline built and passing its fixture** (2026-11-10): build, verify,
  finalize, rechunk, submit wrapper and the fixture test; layout and
  decisions in `CLAUDE.md`, results in `TESTING.md`. Nothing has run on
  the production record or a compute node yet.
- **Design decisions** (user, 2026-11-10; recorded in `CLAUDE.md`,
  "Decisions"): common engine with per-product inputs, TROPOMI first;
  grid type, resolution and frequency (`day`, `<n>day`, `month`,
  `<n>month`) in config; periods counted from 1900-01-01; grid tokens
  `latlon_0p25x0p25` / `ease2_m25km`; `spatial/` + `temporal/`
  directories; 8 statistics + 9 sums per (grid, frequency); temporal =
  rechunk of the tagged spatial store; sampled verification. New
  nomenclature rows (15 variables, `month`, `3day`) added in style_guides
  `8144058`.
- **TROPOMI method:** as decided 2026-11-09 (`../docs/technical/gridding-method.md`).
  The pipeline reproduces the drafting code on a full production day to
  1e-9 (TESTING.md).
- **The method doc** has its store table (Section 10) and the weight in mol.

## Next

1. **Choose TROPOMI's production grids and frequencies** (the config's are
   placeholders: 1°, 0.25°, EASE 25 km; day and month) and the
   verification sample sizes (`verify.samples`).
2. **Bench** (TESTING.md Tier 2): one month on a compute node; show the
   user the job first.
3. Production, verify, finalize, rechunk, verify, finalize.
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
   - **AIRS, CrIS (TROPESS):** centres only; δD is an 850-250 hPa level
     mean, not a column (Q2b), so the H2O-weighted mean is not the δD of
     summed columns; its σ is not noise-only and is missing on ~70% of v1
     rows (R17); no H2O column; CrIS SNPP RS and FS overlap 2021-02..05
     (R26), so gridding both double counts.
   - **IASI, TES:** not built in L2 yet.
   Each needs: a footprint model (e.g. a centred circle of a stated
   diameter), the δ, σ and weight variables (or a decision to weight by
   area alone), its selection, and a "Gridding inputs" section in its
   product doc.
- **Environment:** `gridding/pyproject.toml` and `uv.lock` (shapely and
  pyproj named for the verifier); see the root CLAUDE.md, "How the halves
  connect".
