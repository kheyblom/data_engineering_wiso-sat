# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Status (2026-10-14)

- **Tasks 1-3 done.** Root `CLAUDE.md`; repo on GitHub (SSH remote, `main`).
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
- **Task 3 closed.**
  - The L2 rules are in the style guide (`style_guides` `7bc9f72`,
    `7137951`).
  - The 16 TROPOMI rows are in `nomenclature_data.md` (`style_guides`
    `fd94a93`, pushed).
  - The subset, the naming rule and the source-to-canonical map are in
    `docs/products/tropomi.md` ("Production subset").
- **Elsewhere:** GLEAM and MSWEP carry a deferred task 2 (add `cdm_data_type:
  Grid`; `standard_name` from the source only). Both are pushed.

## Next: task 4 (do not start until the user asks)

1. Write `nomenclature-key_tropomi.md` from the map in
   `docs/products/tropomi.md`. It is machine read; model it on
   `data_engineering_mswep/nomenclature-key_mswep.md`.
2. Design the shared reader interface.

## Decisions carried into task 4 (2026-10-14)

- **Subset:** 16 one-dimensional stores, ~1.7 TB uncompressed:
  - the core 7;
  - the 9 inputs that reproduce the Schneider et al. (2022) Table 1 filters.
- **Model comparison deferred:** kernels, priors and the dry-air partial
  column (~26 TB), plus the geolocation pressure grid (~5.3 TB), which only
  the kernels need. Revisit after the bench measures compression. They have
  no nomenclature rows yet.
- **Filtering guidance for the metadata** is Table 1 in full, plus the inferred
  reduced chi-squared (chi2 / spectral points). Details are in
  `docs/products/tropomi.md`.
- **Naming rule:** quantity first, then qualifiers general to specific
  (e.g. `albedo_surface_2365nm`, like `soil_moisture_surface`). Established
  terms stay whole (`solar_zenith_angle`). Unitless quantities use
  `unitless`.

## Open questions

- **Coordinate naming in the geolocation store.** The gridded stores keep
  `time`/`lat`/`lon` without nomenclature rows. `pressure` follows that
  convention unless the user says otherwise; it only matters once the
  model-comparison set is produced.
