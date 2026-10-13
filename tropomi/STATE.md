# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Status (2026-10-13)

- Task 1 done: `tropomi/CLAUDE.md` created.
- Task 2 done: git repo initialised at `data_engineering_wiso-sat/`, `.gitignore`
  carried over from the sibling repos, remote `origin` set (SSH), `main` pushed.
- Exploratory notebooks (`testing*.ipynb`) are gitignored by decision.

## Next

Task 3 in progress: proposal written to `l2-standards-draft.md` (rules L2-1..12,
draft nomenclature rows, five decisions). Awaiting the user's decisions; then
move the rules into the style guide, the rows into `nomenclature_data.md`, and
delete the draft.

## Open questions

- Which variables go into the production subset (config-driven, task 4).
- Whether stores include quality-filtered observations only, or all with
  `quality_flag` carried alongside.
