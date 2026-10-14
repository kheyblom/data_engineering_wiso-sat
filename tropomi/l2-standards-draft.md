# Level 2 standards — draft proposal (task 3)

**Status: proposal, partly decided.** Once agreed, the rules go into
`style-guide_data-engineering_raw-to-datalake.md` under "Level 2 satellite retrieval data", the
variables into `nomenclature_data.md`, and this file is deleted.

Each rule names the gridded precedent it follows. The aim is that a Level 2
store differs from a gridded one only where the data's shape forces it.

## Decided (2026-10-14)

- Keep every observation; no selection, no quality filtering (L2-3).
- Temporal frequency `inst`, grid name `native_swath` (L2-9).
- **One store per variable covering the whole record**, not one per day
  (L2-1). Supersedes the per-day design and TASKS.md's "zarr stores for each
  day".
- Scope is Level 2 only; L3 gridded files in the raw tree are ignored.
- Column amounts in `mol m-2`; δD in `1e-3` (per mil). Decided 2026-10-14,
  after the value check below confirmed every declared unit except TES's.
- The raw `SCIAMACHY/` directory keeps its name although `H2O/` and `HDO/`
  hold MIPAS files (see open decision on the store's `data_source`).
- *Leaning, not final:* one shared geolocation store per product, joined on
  `obs` (see the estimate below).

## Evidence for TROPOMI (measured 2026-10-13)

- **Files:** one per orbit, `hdo/YYYY/MM/DD/<orbit>/s5p_l2_hdo_0003_<orbit>.nc`,
  ~1.1 GB, 5-14 orbits per day, 2017-11-08 .. 2024-05-30.
  - Processor version `8.1` (root attribute); product version `0003` (filename).
- **Observation layout:** `nobs` is the full L1B swath flattened in scanline
  then pixel order (e.g. 4173 x 215 = 897,195). So scanline = i // 215 and
  ground pixel = i % 215 within an orbit; this needs checking for every orbit.
  - Secondary dims: `nlayer` 50, `nlevel` 51, `ncorner` 4, `nwin` 1, and
    `ntime` 7 (a broken-down timestamp, ms resolution).
- **Size:** 31,492 orbit files. `nobs` per orbit is ~697,800 in 2018-2019 and
  exactly 896,980 in every orbit sampled from 2020 on (the along-track
  resolution change of Aug 2019). The whole record is ~2.6e10 observations:
  ~105 GB uncompressed per 1-D float32 variable, ~5.2 TB per `(obs, 50)`.
- **Fill:** there is no `_FillValue`; missing values are `9.96921e36`.
  - In orbit 16820, 71% of `nobs` have an `hdo_column` and 65% have
    `processing_quality_flags == 0`.
  - Flagged observations still carry unphysical values, e.g.
    `deltad = -7593`.
- **Flags:** `quality_flag` is "Not implemented"; `processing_quality_flags` is
  the real flag.
- **Upstream metadata:** most `standard_name`s are not CF standard names, and
  some units are byte strings.
- **Day boundary:** in the sampled pair, orbits did not straddle UTC midnight.

## Proposed rules

**L2-1. One store per variable, covering the whole record.**
- Follows the general one-store-per-variable rule.
- Replaces, for L2 only, the gridded rule requiring separate spatial and
  temporal stores: an observation list has no lat/lon axes to chunk against,
  so there is one layout (L2-8).

**L2-2. Observations are appended in orbit order and keep source order within
an orbit.** Orbit order is time order. The build checks that `time` never
decreases across the whole store.
*Precedent: gridded time axes are derived from the data and checked, not
assumed.*

**L2-3. No observation selection and no quality filtering.** *(decided)*
- Every observation in the raw files is kept, failed retrievals included (they
  read back NaN).
- The quality flag is its own variable store and is mandatory in every
  production run.
- Upstream filtering guidance goes in metadata.

**L2-4. Sibling stores share an identical observation axis and orbit index.**
- Every variable store from one product has the same `obs` length, the same
  coordinates and the same orbit index, so `xr.merge(..., join='exact')` works.
- The build and the verifier both check this.

*Precedent: GLEAM's `check_time_axis` pinning a variable family.*

**L2-5. Dimensions, coordinates and the orbit index.**
- Observation dimension `obs` (from `nobs`).
- Coordinates `time`, `lat`, `lon` (pixel centre): either on `obs` in every
  store, or once in a shared geolocation store (leaning; see the estimate
  below). The orbit index stays in every store either way, so day and orbit
  subsetting never needs the geolocation store.
- **Orbit index:** a small `orbit` dimension (~25k entries, one chunk) holding:
  - `orbit_number`, `orbit_obs_start`, `orbit_obs_count`
  - `orbit_time_start`, `orbit_time_end`
  - `source_file`

  It does three jobs:
  - It replaces a search through ~3e10 timestamps: finding a day or an orbit is
    one tiny read.
  - It maps every observation back to its raw file and index (scanline and
    ground pixel follow from the index, see Evidence), so no per-observation
    traceability coordinates are needed.
  - It is the build's resume state (L2-11).

  *Precedent: gridded 1-D index coordinates are kept as one small chunk for
  exactly this reason.*
- **Secondary dims:**
  - Renamed without the `n` prefix: `layer`, `level`, `corner`.
  - Length-1 dims (`nwin`) are squeezed.
  - `ntime` becomes the `time` coordinate.
  - Each change is recorded in metadata.
- Pixel corners are their own variable stores, if selected.

**L2-6. Time encoding: int64 `milliseconds since 1900-01-01`,
`proleptic_gregorian`.** Same epoch and calendar as the gridded
`days since 1900-01-01`; milliseconds because the source resolves them.

**L2-7. Fill values.**
- Undeclared source fill is declared in config
  (`source_fill_values: [9.96921e36]`) and checked to occur before masking.
- It is masked to NaN and recorded in a `source_fill_values_masked` attribute.
- Floats store NaN as their fill value. Integer variables keep their dtype and
  carry an explicit `_FillValue`.

*Precedent: MSWEP `source_fill_values` / `check_source_fill`; dtype rules.*

**L2-8. Chunking: one layout, chunked only along `obs`.**
- Target ~16-32 MiB uncompressed per chunk, matching the gridded 24.7 MiB.
- Starting points for the task 4 bench:
  - 4,194,304 obs for a 1-D float32 variable (16 MiB, ~7k chunks over the
    record);
  - 131,072 obs for an `(obs, 50)` float32 variable (25 MiB, ~230k chunks,
    about the GLEAM spatial store's count).
- Secondary dims are never split.
- Time-ordered chunks make a day or an orbit a contiguous read. A regional
  time series is a full scan; that is inherent to L2, and L3 products exist to
  serve it.
- Default zarr v3 zstd compression, as in the gridded stores. `time` may add a
  delta filter, to be measured in the bench.

**L2-9. Naming.** *(`inst`, `native_swath` decided)*
```
<data_source>.<version>.<product>.<temporal_frequency>.<grid_name>.<variable>.zarr
tropomi.v_0003.hdo.inst.native_swath.<variable>.zarr
```
- This is the guide's existing convention with its product slot (`v_3_5.nrt`).
  There is no date component and no deviation.
- No layout or year directories are needed: there are only a handful of stores.
- New nomenclature rows:
  - temporal frequency `inst`: instantaneous observation, no temporal
    aggregation;
  - grid name `native_swath`: the instrument's own pixels, not regridded.

**L2-10. Metadata.** The required `history`, `verification` and
`date_created`, plus:
- `Conventions: CF-1.11, ACDD-1.3` and `featureType: point`. This is a CF
  discrete-sampling-geometry point collection.
- ACDD coverage read off the data: `time_coverage_*` and `geospatial_*`.
- `product_version` and `processor_version`; per-file provenance lives in the
  orbit index.
- Upstream attributes are kept as `original_*`. An upstream `standard_name` is
  kept only if it is a real CF standard name, else moved to
  `original_standard_name`. Byte-string attributes are decoded.
- `ancillary_variables` names the sibling stores needed to interpret this one,
  e.g. an averaging kernel needs the pressure levels.
- `quality_filtering: none applied`, plus upstream filtering guidance.

**L2-11. Incremental build and missing data.**
- **Append and resume:** the store is appended a batch of orbits at a time,
  each batch one icechunk commit. Resume starts after the last orbit in the
  committed orbit index, which is written in the same commit as its data so
  the two cannot disagree.
  - Batches do not land on chunk boundaries, because orbit sizes vary. Each
    append therefore rewrites the trailing partial chunk; that is safe only
    because there is exactly one writer at a time. How the build handles this
    is a task 4 detail.
- **Missing days:** listed in config as `expected_missing_days`. The build
  fails on any gap that is not listed. Missing days simply do not appear on
  the axis; there is no regular axis to fill.

*Precedent: GLEAM append/resume; MSWEP `expected_missing_times`.*

**L2-12. Verification covers every observation, not a sample.** Raw variables
are uncompressed and one HDF5 chunk each, so the comparison costs about what
the build cost. It checks:
- the obs count against the orbit index and raw `nobs`;
- values against raw after masking and unit conversion;
- coordinates against raw;
- that `time` never decreases;
- the shared axis across sibling stores.

## Units across the L2 sensors

Header reads of one file per product, 2026-10-14. The AIRS and CrIS FS units
were checked to be the same across processor versions (R1p11..R1p19); only
their `long_name` wording drifts. Excluded as L3: the `AIRS_TROPESS_gridded_*`
files, the IASI data bag (`L3pp`), `TROPOMI_averaged_files`, and the GOSAT-2
`monthly_1deg`/`.mat` files. **`SCIAMACHY/H2O` and `SCIAMACHY/HDO` actually hold
ESA MIPAS files** (a different instrument on the same Envisat platform).

### What each product publishes

| sensor (product) | δD | other isotope form | water amount |
| --- | --- | --- | --- |
| TROPOMI (SRON L2 0003) | `deltad`, column: **`1`** | — | `h2o_column`, `hdo_column`: **`molec. cm-2`** |
| SCIAMACHY (SRON SICOR L2) | none | — | `h2o_column`, `hdo_column`: **`molec. cm-2`** |
| AIRS (TROPESS Summary, RS) | `dd_col_p` (850-250 hPa), `dd_004`: **`1e-3`** | HDO/H2O ratio profile `x`: `1` | `x_h2o` dry-air VMR profile: **`1`**; `x_h2o_col_p` (850-250 hPa): **`1e-6`** |
| CrIS-SNPP (TROPESS Summary, RS) | same as AIRS RS: **`1e-3`** | same: `1` | same: **`1`** / **`1e-6`** |
| AIRS (TROPESS Standard, FS) | none | `x`: `1` | `x_h2o` VMR profile: **`1`** |
| CrIS-JPSS1 (TROPESS Standard, FS) | none | `x`: `1` | `x_h2o` VMR profile: **`1`** |
| GOSAT, GOSAT-2 (IUP FOCAL v3.0.1) | `xded`, column-averaged: **`1e-3`** | — | `xh2o` column-avg dry-air mole fraction: **`1e-6`** |
| IASI (KIT MUSICA L2) | `musica_deltad` profile: **`1e-3`** | ln-space proxy state `musica_wvp`: `1` | `musica_h2o` profile: **`ppmv`** |
| MIPAS (ESA L2, in `SCIAMACHY/`) | none | separate HDO VMR profile: `1E-6` | H2O VMR profile, "in air": **`1E-6`** |
| TES (L2 HDO Nadir Lite v006) | none | — | `Species` = stacked HDO + H2O dry-air VMR profiles: **`VMR`**; `TotalColumnDensity` (HDO): labelled **`molecules/m2`**, actually molec cm-2 |

The differences are mostly **different quantities**, not different units for
one quantity, so there is one canonical unit per quantity family. A different
quantity gets its own canonical name, never a conversion.

### Value check (2026-10-14)

Read one file per product (one orbit for TROPOMI), applied each variable's
declared fill, and compared percentiles with physical expectations. Single
files, so this confirms units, not the distribution of the record.

| product | variable (declared unit) | p1 / p50 / p99 | verdict |
| --- | --- | --- | --- |
| TROPOMI | `deltad` (`1`), flag == 0 | -0.99 / -0.25 / 13.3 | **fraction confirmed** (p50 = -250 per mil) |
| TROPOMI | `h2o_column`, `hdo_column` (`molec. cm-2`) | p50 5.5e22, 1.3e19 | confirmed (~16 mm precipitable water; HDO/H2O ~2.3e-4) |
| TROPOMI | column averaging kernels (`1`) | p50 1.02 / 2.01 | unitless confirmed |
| SCIAMACHY | columns, kernel (`molec. cm-2`, `1`) | p50 1.1e22, 4.3e18; 0.27 | confirmed |
| TROPESS RS/FS | `x` HDO/H2O ratio (`1`) | 1.1e-4 / 2.3e-4 / 3.0e-4 | **mole ratio confirmed** (p50 = -260 per mil vs VSMOW) |
| TROPESS RS/FS | `x_h2o`, `x_h2o_raw` (`1`) | 2.5e-6 / 6e-4 / 3e-2 | **mol mol-1 confirmed** |
| TROPESS FS | `observation_error_h2o` (`1`) | 0.017 / 0.088 / 0.37 | **relative (ln-space) error, not a mole fraction** — must not be x 1e6 |
| TROPESS RS | `dd_col_p`, `dd_004` (`1e-3`); `x_h2o_col_p` (`1e-6`) | -327 / -247 / -153; 965 / 4077 / 9828 | confirmed |
| GOSAT, GOSAT-2 | `xded` (`1e-3`); `xh2o` (`1e-6`); kernel (`1`) | -220 / -136 / -46; 131 / 2417 / 5951; ~1.0 | confirmed |
| IASI | `musica_deltad` (`1e-3`); `musica_h2o` (`ppmv`) | -598 / -341 / 2; 2.7 / 168 / 28,450 | confirmed |
| IASI | `musica_wvp` (`1`) | -0.88 / 0.12 / 10.0 | **ln-space state** (ln of ppmv, ln of ratio), not a mole fraction |
| MIPAS | H2O `profile` (`1E-6`) | 0.9 / 6.0 / 452 | confirmed (stratospheric ppm) |
| MIPAS | HDO `profile` (`1E-6`) | ~0 / 9.5e-4 / 0.039 | confirmed (HDO ~1e-3 ppm in the stratosphere) |
| TES | `Species` / `Retrieval/HDO_H2O` (`VMR`) | HDO 4.7e-8, H2O 2.2e-4 (p50) | **mol mol-1 confirmed, but the array stacks two profiles** |
| TES | `TotalColumnDensity` (`molecules/m2`) | p50 7.9e18 | **mislabelled: values are HDO in molec cm-2** |

Findings that change the plan:

1. **TES `TotalColumnDensity` is in molec cm-2, not molecules/m2.**
   Integrating the TES HDO profile over pressure gives a median 7.83e22
   molecules/m2, and the file's value is exactly 1.000e-4 of that, per target.
   It is the HDO column. Conversion to `mol m-2` is therefore x 1e4 / N_A, the
   same as TROPOMI, not the 1 / N_A the label implies. The build must declare
   the corrected source unit and record it in metadata.
2. **TES `Species` (and `Retrieval/HDO_H2O`, an identical array) stacks two
   profiles.** Levels 0-16 are HDO and 17-33 are H2O, on the same 17 pressures
   repeated. `HDO_H2O` is a name, not a ratio. The two halves become two
   variables, which is a restructuring the style guide would have to allow;
   the ratio they imply is physical (p50 2.2e-4; δD from -82 per mil at the
   surface to -650 aloft).
3. **Two `1`-unit variables are log-space and must never be scaled with their
   neighbours:** TROPESS `observation_error_h2o` and IASI `musica_wvp`. The
   nomenclature key must map them to their own canonical names, with units `1`.
4. Not unit problems, but worth recording:
   - TROPOMI `processing_quality_flags == 0` still passes δD from -0.99 to
     +13 (p1/p99) and `h2o_column` up to 1.7e26; SRON's own filtering
     guidance needs to go in the metadata.
   - TROPOMI column kernels reach p99 ~700 in some layers.
   - TROPESS `x_h2o` reaches 0.44 mol mol-1 (unphysical).
   - The GOSAT and GOSAT-2 files contain only flag-0 soundings, so they arrive
     pre-filtered.

### Canonical units (decided except mole fraction)

**δD → `1e-3`** *(decided)*.
- TROPOMI converts x 1000.
- AIRS/CrIS RS, GOSAT, GOSAT-2 and IASI are unchanged.
- Products publishing a ratio or separate HDO/H2O are not converted into δD:
  that would be a derivation, not a unit change.

**Column amount → `mol m-2`** *(decided)*.
- TROPOMI, SCIAMACHY and TES (corrected label) all convert x 1e4 / N_A
  (= 1.66053907e-20), with N_A = 6.02214076e23 exact.

**Mole fraction → `1e-6` (recommended).** Where it applies:

| product | variables | conversion |
| --- | --- | --- |
| GOSAT, GOSAT-2 | `xh2o`, `xh2o_uncertainty`, `h2o_profile_apriori` | none |
| AIRS, CrIS-SNPP (RS) | `x_h2o_col_p`, `x_h2o_col_p_error` | none |
| AIRS, CrIS-SNPP (RS); AIRS, CrIS-JPSS1 (FS) | `x_h2o`, `x_h2o_raw` profiles | x 1e6 |
| IASI | `musica_h2o`, `_apriori`, `_error` | none (respell `ppmv`) |
| MIPAS | H2O and HDO `profile`, `profile_error`, `extended_profile`, `a_priori_profile` | none (respell `1E-6`) |
| TES | HDO and H2O halves of `Species`; `ConstraintVector`, `Retrieval/Initial` | x 1e6 (`ConstraintVector` declares `mole/mole`) |
| TROPOMI, SCIAMACHY | none — they publish columns | — |

- MIPAS covariances are `1E-12`, i.e. (1e-6)^2, and stay consistent.
- HDO in ppm is small (MIPAS ~1e-3, TES p50 0.05). That costs no precision in
  float32, whose relative precision does not depend on magnitude.
- Not mole fractions, so they stay `1`: the HDO/H2O ratios (TROPESS `x`,
  `xa`, `x_raw`), the log-space variables (finding 3), averaging kernels, and
  flags.

All conversions are a single multiplication applied once in float32. The
verifier compares against `raw x factor` computed the same way, so the
expected mismatch is zero, with a 1-ulp tolerance stated if it is not.

## Dry-air vs total-air mole fraction (for discussion)

1. **The two quantities.**
   - Dry-air mole fraction: x_dry = n_w / n_dry.
   - Total (moist) air mole fraction: x_tot = n_w / (n_dry + n_w).
   - So x_tot = x_dry / (1 + x_dry), and x_dry = x_tot / (1 - x_tot).
   - Both are mol mol-1, so **no unit conversion can tell them apart or
     reconcile them**. Specific humidity (a mass fraction) is a third,
     different quantity.
2. **How much it matters.** The relative difference is about x itself:

   | regime | typical x | dry vs total |
   | --- | --- | --- |
   | tropical surface | 30,000 ppm | ~3% (30,000 dry is 29,126 total) |
   | mid-latitude surface | 5,000 ppm | 0.5% |
   | upper troposphere | 100 ppm | 0.01% |
   | stratosphere (MIPAS) | 5 ppm | negligible |

   The tropical figure is larger than GOSAT's own `xh2o` uncertainty (p50
   15.5 ppm on 2,417, ~0.6%), so the difference is not noise.
3. **What it does not affect.**
   - δD and HDO/H2O ratios: the basis cancels if both species share it.
   - Columns in `mol m-2`, which are absolute amounts.
   - Column-averaged "X" quantities (GOSAT `xh2o`, TROPESS `x_h2o_col_p`),
     which are dry-air by convention (column / dry-air column).
4. **What each product declares.**
   - Dry, explicitly:
     - GOSAT and GOSAT-2 `xh2o` (CF-style standard name
       `dry_atmosphere_mole_fraction_of_water_vapor`) and their a priori;
     - TROPESS RS `x_h2o` ("dry_air_volume_mixing_ratio") and `x_h2o_col_p`;
     - TES `Species` ("relative to dry air").
   - Total air: MIPAS, via the CF standard name
     `mole_fraction_of_water_vapor_in_air`. In CF "in_air" includes the water
     vapour; whether ESA meant that exactly is worth confirming, though it is
     negligible at MIPAS altitudes.
   - Unstated:
     - TROPESS FS `x_h2o`. It is the same MUSES algorithm as RS, so probably
       dry, but needs confirming.
     - IASI MUSICA `musica_h2o` (`ppmv`): the product documentation needs
       checking.
5. **Options.**
   - **A (recommended):** separate canonical names that carry the basis
     (e.g. `..._mole_fraction_dry_air` / `..._mole_fraction_in_air`). Each is
     stored as published, with a `mole_fraction_basis` attribute.
   - B: convert everything to one basis. H2O can convert itself exactly, but
     HDO needs the matching H2O value. That is a derivation, which the guide's
     "exactly represents the original data" rules out without approval.
   - C: ignore the difference. Not acceptable, given point 2.
6. **Before naming:** confirm the basis for TROPESS FS and IASI MUSICA from
   their product documentation.

## Shared geolocation store: volume estimate

Per product, from file counts and per-file `obs` sizes sampled across each
record (4-6 files; TES and MIPAS vary most). Coordinates as they would be
stored:
- `time` as int64 and `lat`/`lon` as float32 (every source publishes float32
  centres): **16 B per observation**.
- A per-observation pressure grid on top for profile products: 4 B x levels.

All figures are uncompressed. `time` compresses very well and `lat`/`lon`
little, so the stored savings will be somewhat smaller.

| product | files | ~obs | lat/lon/time per store | pressure grid per profile store |
| --- | --- | --- | --- | --- |
| TROPOMI | 31,492 orbits | 2.6e10 | **419 GB** | 5.3 TB (51 levels) |
| IASI (MUSICA) | 4,568 | 1.6e9 | **25 GB** | 182 GB (29) |
| SCIAMACHY (SICOR) | 41,616 | 7.8e7 | 1.25 GB | 19 GB (61) |
| AIRS FS | 1,424 | 4.1e7 | 0.66 GB | 2.8 GB (17) |
| CrIS-JPSS1 FS | 1,208 | 3.0e7 | 0.48 GB | 2.0 GB (17) |
| AIRS RS | 6,361 | 1.1e7 | 0.18 GB | 0.76 GB (17) |
| GOSAT H2O / DED | 4,498 / 4,498 | 7.2e6 / 2.5e6 | 0.12 / 0.04 GB | 0.17 / 0.06 GB (6) |
| TES | 75 | 2.9e6 | 0.05 GB | 0.20 GB (17) |
| CrIS-SNPP RS | 1,865 | 2.8e6 | 0.05 GB | 0.19 GB (17) |
| MIPAS H2O / HDO | 35,124 / 30,213 orbits | 2.3e6 / 1.9e6 | 0.04 / 0.03 GB | 0.25 / 0.21 GB (27) |
| GOSAT-2 H2O / DED | 1,010 / 1,010 | 1.4e6 / 6.1e5 | 0.02 / 0.01 GB | 0.03 / 0.01 GB (6) |

How to read it:
- **Saving = (N - 1) x the per-store figure**, for N variable stores of one
  product.
  - At TROPOMI N = 6, a shared store saves **~2.1 TB** of lat/lon/time.
  - If profile variables carried their own pressure grid, each extra profile
    store would add 5.3 TB more.
- **Relative to the data, for 1-D float32 variables:** coordinates in every
  store cost 20 N B/obs against 4 N + 16 B/obs shared. That is 64% less at
  N = 5 and 72% less at N = 10, the same for every sensor because the dtypes
  are the same.
- **TROPOMI is ~94% of the total**, and IASI most of the rest. For the TROPESS,
  GOSAT, MIPAS and TES products the saving is under 1 GB per store.

What a shared store costs:
- A variable store alone no longer says where its values are.
- The join on `obs` relies on L2-4 (identical observation axes), which the
  verifier already checks.
- The guide must allow a geolocation store holding several coordinate arrays,
  as an exception to one variable per store.
- Recommended form, if chosen: one `<...>.geolocation.zarr` per product with
  `time`, `lat`, `lon` and, for profile products, the per-observation pressure
  grid. Every variable store keeps the orbit index, so subsetting by day or
  orbit still works without it.

## Open decisions

6. **Geolocation:** confirm one shared geolocation store per product (leaning
   yes), and whether it also carries the per-observation pressure grid
   (recommended).
7. **MIPAS `data_source` in store names:** keeping the raw directory as
   `SCIAMACHY/` is fine. But the files declare `sensor: MIPAS`, and SICOR
   SCIAMACHY water stores would sit beside them, so the stores should use
   `mipas` as `data_source`. Recommended: `mipas` in store names, raw
   directory unchanged. Needs confirmation.
8. **Mole fraction unit:** `1e-6` (recommended) or `1`.
9. **Dry vs total air:** option A (separate canonical names), pending the
   TROPESS FS and IASI documentation check.
10. **TES:** allow splitting the stacked `Species` array into HDO and H2O
    stores, and declare the corrected column unit.
5. *(deferred)* The production variable subset.
