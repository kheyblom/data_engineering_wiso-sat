# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Status (2026-10-14)

- Task 1 done: `tropomi/CLAUDE.md` created.
- Task 2 done: git repo initialised at `data_engineering_wiso-sat/`, `.gitignore`
  carried over from the sibling repos, remote `origin` set (SSH), `main` pushed.
- Exploratory notebooks (`testing*.ipynb`) are gitignored by decision.
- Task 3 in progress, `l2-standards-draft.md`. Decided 2026-10-14: keep every
  observation; `inst` + `native_swath`; one store per variable for the whole
  record (not per day); Level 2 only, L3 files in the raw tree ignored.
  Rules L2-1..12 reworked for the whole-record store (orbit index added).
  Unit survey of all L2 sensors added with recommendations.

## Next

Await the user's decisions 2 (column unit), 3 (delta-D unit), 6 (coordinates
in every store), 7 (MIPAS files under `SCIAMACHY/`). Then rebuild the draft
nomenclature table, move the rules into the style guide and the rows into
`nomenclature_data.md`, and delete the draft. Decision 5 (variable subset) is
deliberately deferred until the rest is settled.

## Open questions

- Which variables go into the production subset (config-driven, task 4).
