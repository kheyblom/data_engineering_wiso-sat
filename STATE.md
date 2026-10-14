# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Status (2026-10-14)

- **Tasks 1-2 done.** Root `CLAUDE.md`; repo on GitHub (SSH remote, `main`).
- **One codebase for all WISO-SAT L2 products** (user decision, 2026-10-14).
  The docs are restructured; **nothing is built yet**.
  - Root `CLAUDE.md`: scope, product table, governing rules, design
    conditions.
  - `docs/products/*.md`: per-product reader facts, measured from header
    reads and sampled values.
  - `docs/l2-survey.md`: cross-product units, value checks, dry-air basis,
    geolocation estimate, and the Sarkar et al. (2026) cross-check.
  - `tools/survey/`: the scripts behind that evidence.
  - `notebooks/`: gitignored exploration.
- **Task 3 nearly done.** The L2 rules are in the style guide, pushed
  (`style_guides` `7bc9f72`, `7137951`). All unit, basis, scope and naming
  decisions are recorded in the root `CLAUDE.md`. Remaining: the TROPOMI
  variable rows.
- **Elsewhere:** GLEAM and MSWEP carry a deferred task 2 (add `cdm_data_type:
  Grid`; `standard_name` from the source only). Both are pushed.

## Next: TROPOMI variable subset (to be done in a new session)

1. Choose the subset with the user. The candidates (core / model comparison
   / optional filter inputs, each with a proposed canonical name, unit and
   conversion) are in `docs/products/tropomi.md`.
2. Settle the open questions that bear on it (see Open questions).
3. Add the chosen rows to `nomenclature_data.md` in
   `/glade/u/home/kheyblom/work/style_guides`, matching that table's format.
   - The user reviews the style_guides change before it is committed and
     pushed.
   - Canonical names are permanent identifiers, so get them right first.
4. Mark task 3 done in `TASKS.md`. Then task 4: write
   `nomenclature-key_tropomi.md` (machine read; model it on
   `data_engineering_mswep/nomenclature-key_mswep.md`) and design the shared
   reader interface.

## Open questions

- **The variable subset.** Size matters: each 50-layer variable is ~5.2 TB
  uncompressed.
- **Clear-sky inputs:** which inputs Schneider et al. (2022) Table 1 uses for
  its clear-sky criteria, and whether the WISO-SAT "cloud optical thickness"
  is SRON's `aerosol_optical_thickness` (scattering layer). Both need the
  paper or SRON product documentation.
- **Coordinate naming in the geolocation store.** The gridded stores keep
  `time`/`lat`/`lon` without nomenclature rows. `pressure` follows that
  convention unless the user says otherwise.
