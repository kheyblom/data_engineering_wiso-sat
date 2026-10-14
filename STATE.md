# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Status (2026-10-14)

- **Tasks 1-3 done.** Root `CLAUDE.md`; repo on GitHub (SSH remote, `main`).
- **Task 4 in progress: the shared pipeline and the TROPOMI reader are built,
  and the fixture passes.**
  - Layout and usage are in `CLAUDE.md` ("Layout").
  - `validation/test_pipeline.py` runs 17 cases on the TROPOMI fixture, all
    passing. They cover:
    - a clean build and full verification;
    - a no-op re-run, and resume from a simulated kill;
    - tamper detection;
    - four build guards;
    - the finalize sequence.
  - The fixture is already staged at
    `/glade/derecho/scratch/kheyblom/data/wisosat_fixture/` (5 orbits,
    38,055 obs).
  - `config/tropomi/config_zarr.yaml` is written but **not run**; its scale
    settings are bench starting points.
- **Decided 2026-10-14 during task 4 (user):**
  - Stores are named `wisosat.<product>.<version>.inst.native_swath.<variable>.zarr`.
    The version is taken from the file attributes (TROPOMI processor `8.1` ->
    `v_8_1`), and there is no product token.
  - One pass, many stores: each granule is read once and written to every
    store of the config.
  - The raw root moved to `data/wisosat/raw/`.
- **Elsewhere:** GLEAM and MSWEP carry a deferred task 2 (add `cdm_data_type:
  Grid`; `standard_name` from the source only). Both are pushed.

## Next (task 4, in order)

1. **Second reader at fixture level (design condition 1), before any TROPOMI
   production run.** GOSAT is the cheapest; TES is the strongest test.
   - Its variables need rows in `nomenclature_data.md` first, and the user
     reviews style_guides edits before they are committed.
   - This is also the step for the cross-product naming pass on kernels,
     priors and dry-air columns (see below).
   - Share only what the second reader actually needs; then run
     `test_pipeline.py` for both products.
2. **Check the citations** in `config/tropomi/config_zarr.yaml` `references`
   (DOI, pages) before production.
3. Then task 5 (`TESTING.md`: the bench plan) and task 6.

## Decisions carried into task 4 (2026-10-14, still binding)

- **Subset:** 16 one-dimensional stores, ~1.7 TB uncompressed:
  - the core 7;
  - the 9 inputs that reproduce the Schneider et al. (2022) Table 1 filters.
- **Model comparison deferred:** kernels, priors and the dry-air partial
  column (~26 TB), plus the geolocation pressure grid (~5.3 TB), which only
  the kernels need. They have no nomenclature rows yet (decided 2026-10-14).
  - Measure kernel compression with a standalone scratch script; that needs
    no rows.
  - At the second-reader step (GOSAT or TES), name the kernels, priors and
    dry-air columns in one design pass across all products. The layouts
    differ: column kernels, block matrices, log space, SVD components, and
    priors as partial columns or as mole fractions.
  - Add rows per product as each is built, and for TROPOMI only if the bench
    makes the set affordable.
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
