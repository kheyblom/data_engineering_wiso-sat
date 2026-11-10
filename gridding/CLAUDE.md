# CLAUDE.md (gridding/)

Guidance for Claude Code when working in `gridding/`, the half of
`data_engineering_wiso-sat` that grids the finalized L2 stores. The root
[CLAUDE.md](../CLAUDE.md) holds the products in scope and the rules both
halves share; this file holds what is particular to gridding.

- Read [STATE.md](STATE.md) first in a new session: it is the gridding
  handoff, so keep it current.
- **Run everything from `gridding/`.** It has its own environment
  (`pyproject.toml`, `uv.lock`, `.venv`), separate from `l2/`'s: a
  dependency change here never calls for the L2 fixture test.
- **The design record so far** is `../notebooks/drafting/gridding-notes.md`
  (TROPOMI, daily): the method decided 2026-11-09, its "Decisions" and its
  numbers. Its working code is `tropomi_tools.py` and `tropomi_gridding.py`
  beside it. Those files are gitignored drafts; the method moves into this
  folder as it becomes pipeline code.

## Inputs: the L2 stores only

- Gridding reads **finalized, tagged** L2 stores and nothing else from L2
  (user decision 2026-11-10): their `obs` axis, granule index and
  attributes. It never imports `l2/` code and never writes an L2 store.
- The L2 stores and their tags are listed in `../l2/STATE.md`; what each
  variable means, and every known data issue, is in
  `../docs/products/<product>.md`.
- Quality filtering and thresholds belong here, not in L2: the L2 stores
  keep every observation as published (style guide). TROPOMI T23 (unphysical
  H2O columns under `clear_or_low_cloud`) is the first such case: stored as
  published, dropped by the daily grid above 5,551 mol m-2, a config value.

## Rules particular to gridding

- **The style guide's "Gridded data" section governs** (with its General
  rules), not its Level 2 section: zarr, and separate stores optimized for
  spatial and for temporal retrieval.
- **WISO-SAT is not the reference** (user decision 2026-11-04). Agreement
  with Sarkar et al. (2026) is never a criterion for a gridding choice.
- **Surveys of L3 practice use online sources only**: not WISO-SAT, and not
  the upstream L3 files on disk (`TROPOMI_averaged_files` and the others the
  root CLAUDE.md lists as out of scope).
- From GLEAM / MSWEP, beyond the shared principles in the root CLAUDE.md:
  the spatial/temporal store pair and the `append`/`region` write
  strategies, which L2 left out because it has no grid, apply here. Read
  those repos before designing the stores.

## To decide before the first pipeline code

Store naming (frequency and grid-name tokens), the store layout and chunking
for the spatial and temporal pair, the config schema, the verification
scheme (what "every observation, not a sample" means for a grid), the
fixture test, and how a grid records the L2 tag it was built from. Lay
these out for the user; none is decided yet.
