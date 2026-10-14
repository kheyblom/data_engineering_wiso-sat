# STATE.md — working state / handoff

Read this first in a new session. Update it whenever work lands.

## Status (2026-10-14)

- **Tasks 1-3 done.** Root `CLAUDE.md`; repo on GitHub (SSH remote, `main`).
- **Task 4: the pipeline, the TROPOMI reader and the second reader (GOSAT, at
  fixture level) are built. `validation/test_pipeline.py` passes 34 cases over
  both products** (~75 s on a login node). Layout and usage are in `CLAUDE.md`.
  - Fixtures are staged under `/glade/derecho/scratch/kheyblom/data/wisosat_fixture/`.
  - Neither production config has been run.
- **Task 4 closed 2026-10-14.**
  - The four GOSAT rows are committed in style_guides (`3966e69`).
  - Both citations are checked against their DOI records: Schneider et al.
    2022, and Sarkar et al. 2026 (Scientific Data,
    doi:10.1038/s41597-026-08218-8; no volume or article number yet).
- **Decided 2026-10-14 (user), all reflected in the code and docs:**
  - **Store names:**
    - `wisosat.<product>.<version>.inst.native_swath.<variable>.zarr`;
    - the version comes from the file attributes, with no product token.
  - **One pass, many stores.**
  - **GOSAT DED and H2O merged into one product:**
    - a constructed obs axis, the union of each day's soundings in time
      order;
    - `xded` reuses the TROPOMI δD rows;
    - see `docs/products/gosat.md`.
- **Elsewhere:** GLEAM and MSWEP carry a deferred task 2 (add `cdm_data_type:
  Grid`; `standard_name` from the source only). Both are pushed.

## Next

1. **Task 5 (in progress):** `TESTING.md`, the testing plan from fixture to
   bench to production. Show the user any batch job before submitting it.
2. **The cross-product naming pass** for kernels, priors and dry-air columns,
   planned for the second-reader step and still open. GOSAT's kernel, a
   priori, dry column and pressure grid wait on it. It does not block
   TROPOMI, whose production subset excludes them.
3. **GOSAT-2:** a config pair using `product: gosat2`. It needs a small shared
   change so the reader and key can be named apart from the product.

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
