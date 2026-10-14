# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Status (2026-10-14)

- Task 1 done: `tropomi/CLAUDE.md` created.
- Task 2 done: git repo initialised at `data_engineering_wiso-sat/`, `.gitignore`
  carried over from the sibling repos, remote `origin` set (SSH), `main` pushed.
- Exploratory notebooks (`testing*.ipynb`) are gitignored by decision.
- Task 3 in progress, `l2-standards-draft.md`. Decided 2026-10-14: keep every
  observation; `inst` + `native_swath`; one store per variable for the whole
  record; L2 only; columns `mol m-2`; δD `1e-3`; raw `SCIAMACHY/` dir keeps
  its name (it holds MIPAS under H2O/ and HDO/). Leaning: shared geolocation
  store per product.
- Value check of all L2 products done: units confirmed except TES
  (`TotalColumnDensity` is molec cm-2 despite its label; `Species` stacks HDO
  and H2O profiles). Two `1`-unit variables are log-space (TROPESS
  `observation_error_h2o`, IASI `musica_wvp`) and must never be scaled.

## Next

Draft cross-checked against Sarkar et al. (2026), the WISO-SAT data descriptor
(the user supplied the PDF; it is not in the repo). Await the user's
decisions 6-11 in the draft: geolocation store, MIPAS scope (it is not in
WISO-SAT), mole-fraction unit, single dry-air basis, TES split (including the
kernel blocks), and coverage gaps (TES 2011-2015, AIRS 2020-04..2021-01).
Then rebuild the nomenclature table, move the rules into the style guide and
the rows into `nomenclature_data.md`, and delete the draft. Decision 5
(variable subset) is deferred.

## Open questions

- Which variables go into the production subset (config-driven, task 4).
