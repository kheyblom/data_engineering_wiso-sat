# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Status (2026-10-13)

- Task 1 done: `tropomi/CLAUDE.md` created.
- Task 2 done: git repo initialised at `data_engineering_wiso-sat/`, `.gitignore`
  carried over from the sibling repos, remote `origin` set (SSH), `main` pushed.
- Exploratory notebooks (`testing*.ipynb`) are gitignored by decision.

## Next

Task 3: agree Level 2 standards for the style guide with the user (store unit
per day, dimension/coordinate naming for `nobs`-indexed data, chunking, fill
handling, quality-flag handling), and add the TROPOMI variables to
`nomenclature_data.md`. Nothing is decided yet.

## Open questions

- Which variables go into the production subset (config-driven, task 4).
- Whether stores include quality-filtered observations only, or all with
  `quality_flag` carried alongside.
