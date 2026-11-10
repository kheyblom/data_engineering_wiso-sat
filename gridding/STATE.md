# STATE.md (gridding/): working state / handoff

Read this first in a new session. Update it whenever work lands.

## Where we are (2026-11-10)

- **No pipeline code yet.** `gridding/` was created on 2026-11-10 when the
  repo was split into `l2/` and `gridding/`.
- **TROPOMI daily method: decided** (user, 2026-11-09; no open decisions as
  of 2026-11-10). The record is `../notebooks/drafting/gridding-notes.md`
  ("Decisions", "The decided method"), with working code in
  `../notebooks/drafting/tropomi_tools.py` and `tropomi_gridding.py`. In
  short: footprint-polygon overlap at every resolution, area weight, UTC day,
  H2O-weighted δD, `clear_or_low_cloud`, H2O column at most 5,551 mol m-2
  (T23), every pass of the day averaged, standard error from independent
  errors, effective n, resolution and grid type (lat/lon or EASE-Grid 2.0)
  set in config.
- **Next:** the pipeline design questions in `CLAUDE.md` ("To decide before
  the first pipeline code"), laid out for the user.
- **Environment:** `gridding/pyproject.toml` and `uv.lock`; see the root
  CLAUDE.md, "How the halves connect".
