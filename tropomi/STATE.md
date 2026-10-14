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

- **Decided 2026-10-14:**
  - one geolocation store per product, holding the pressure grid;
  - MIPAS excluded;
  - mole fractions in ppm on one dry-air basis;
  - TES split, with the column-unit correction;
  - coverage gaps flagged but not chased.
- **L2 rules written into the style guide:** `style_guides` commit
  `7bc9f72` (plus the `inst` row), **committed locally, not pushed**.
- **Waiting on the user's decision 5:** the TROPOMI variable subset
  (candidates in `l2-standards-draft.md`), and approval to push `7bc9f72`.
- **Then:**
  - add the variable rows to `nomenclature_data.md`;
  - write `nomenclature-key_tropomi.md`;
  - fold the TROPOMI facts into `CLAUDE.md`;
  - delete the draft;
  - mark task 3 done.

## Open questions

- Which variables go into the production subset (config-driven, task 4).
