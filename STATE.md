# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Status (2026-10-14)

- **Tasks 1-2 done.** `CLAUDE.md` created and the repo initialised, with
  remote `origin` (SSH) and `main` pushed. Exploratory notebooks
  (`testing*.ipynb`) are gitignored.
- **Codebase restructured** from TROPOMI-only to one codebase for all WISO-SAT
  L2 products (user decision, 2026-10-14).
  - Root `CLAUDE.md`, `TASKS.md` and `STATE.md`.
  - Per-product notes in `docs/products/`.
  - Cross-product evidence in `docs/l2-survey.md` (the former
    `tropomi/l2-standards-draft.md`).
  - Nothing is built yet.
- **Task 3 nearly done.** The L2 rules are in the style guide and pushed
  (`style_guides` `7bc9f72`, `7137951`). All unit, basis and scope decisions
  are recorded in the root `CLAUDE.md`.
- **Elsewhere:** GLEAM and MSWEP each carry a deferred task 2 to align their
  stores with the guide updates (`cdm_data_type: Grid`; `standard_name`
  retained from source only). Both are pushed.

## Next

1. **Decision 5:** the TROPOMI variable subset (candidates in
   `docs/products/tropomi.md`).
2. Add those variable rows to `nomenclature_data.md` (style_guides repo), then
   mark task 3 done.
3. **Task 4:** design the shared reader interface around TROPOMI, then write
   `nomenclature-key_tropomi.md` and the configs.

## Open questions

- The production variable subset for TROPOMI.
- The Schneider et al. (2022) Table 1 clear-sky inputs, and whether the
  paper's "cloud optical thickness" is SRON's `aerosol_optical_thickness`.
