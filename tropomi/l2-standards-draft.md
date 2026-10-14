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

## Evidence for TROPOMI (measured 2026-10-13)

- **Files:** one per orbit, `hdo/YYYY/MM/DD/<orbit>/s5p_l2_hdo_0003_<orbit>.nc`,
  ~1.1 GB, 5-14 orbits per day, 2017-11-08 .. 2024-05-30.
  - Processor version `8.1` (root attribute); product version `0003` (filename).
- **Observation layout:** `nobs` is the full L1B swath flattened in scanline
  then pixel order (e.g. 4173 x 215 = 897,195). So scanline = i // 215 and
  ground pixel = i % 215 within an orbit; this needs checking for every orbit.
  - Secondary dims: `nlayer` 50, `nlevel` 51, `ncorner` 4, `nwin` 1, and
    `ntime` 7 (a broken-down timestamp, ms resolution).
- **Size:** the whole record is roughly 3e10 observations (an estimate from
  sampled days). That is ~120 GB uncompressed per 1-D float32 variable and
  ~6 TB per `(obs, 50)` variable.
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
- Coordinates on `obs` in every store: `time`, `lat`, `lon` (pixel centre).
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

## Units across the L2 sensors (decisions 2 and 3)

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
| IASI (KIT MUSICA L2) | `musica_deltad` profile: **`1e-3`** | ln-ratio proxy state: `1` | `musica_h2o` profile: **`ppmv`** |
| MIPAS (ESA L2, in `SCIAMACHY/`) | none | separate HDO VMR profile: `1E-6` | H2O VMR profile, "in air": **`1E-6`** |
| TES (L2 HDO Nadir Lite v006) | none | `HDO_H2O` ratio profile: `VMR` | `TotalColumnDensity`: **`molecules/m2`** (probably HDO, to confirm); `Species` dry-air VMR profile |

The differences are mostly **different quantities**, not different units for
one quantity. Unit conversion can only unify within a quantity, so the
recommendation is one canonical unit per quantity family. A different
quantity gets its own canonical name, never a conversion.

### Recommendation

**δD → `1e-3` (per mil).**
- It is already used by 5 of the 6 products that publish δD, it is the
  community convention, and udunits parses it.
- Only TROPOMI converts (x 1000, exact in float32 up to rounding).
- Products publishing a ratio or separate HDO/H2O are **not** converted into
  δD: that is a derivation needing a standard ratio, not a unit change. Note
  SRON uses 3.1153e-4 and TROPESS 3.1152e-4.
- Alternative `1`: TROPOMI unchanged, but five products divide by 1000.

**Column amount (number per area) → `mol m-2`.**
- It is SI, udunits-parseable, the CF canonical unit for
  `atmosphere_mole_content_of_water_vapor`, and the ESA TROPOMI operational
  convention. The HDO/H2O column ratio stays a plain mole ratio.
- Conversions use the exact N_A = 6.02214076e23:
  - TROPOMI and SCIAMACHY: x 1e4 / N_A (= 1.66053907e-20);
  - TES: x 1 / N_A.
- Alternative `kg m-2` (precipitable water): comparable with reanalysis TCWV,
  but it needs molar masses (H2O 18.01528, HDO 19.02134 g/mol). The HDO/H2O
  mass ratio then no longer equals the mole ratio δD is defined on, which is
  a trap.
- Alternative `molec cm-2`: no change for TROPOMI and SCIAMACHY, but udunits
  cannot parse it and TES would still need x 1e-4.

**Mole fraction, profiles and column averages → `1e-6` (ppm).**
- Already used by GOSAT, GOSAT-2, TROPESS `x_h2o_col_p` and MIPAS (respelled
  from `1E-6`), and by IASI (respelled from `ppmv`).
- TROPESS `x_h2o` profiles and TES `Species` convert x 1e6.
- Alternative `1` (mol mol-1): six products divide by 1e6.
- Dry-air and moist-air mole fractions are different quantities and need
  separate canonical names:
  - dry air: GOSAT, TROPESS RS, TES;
  - "in air": MIPAS;
  - unstated: IASI and TROPESS FS, so their documentation needs checking.

**HDO/H2O ratio (not normalised) → `1`.**
- TROPESS is unchanged; TES respells `VMR` to `1`.

All conversions are a single multiplication applied once in float32. The
verifier compares against `raw x factor` computed the same way, so the
expected mismatch is zero, with a 1-ulp tolerance stated if it is not.

## Open decisions

2. Column unit: `mol m-2` (recommended), `kg m-2`, or `molec cm-2`.
3. δD unit: `1e-3` (recommended) or `1`.
6. Coordinates in every store (L2-5): `time` + `lat` + `lon` cost ~16 bytes
   per observation, about 4x a 1-D float32 variable, repeated in each store.
   - Recommended: keep them in every store, so each store is
     self-describing like a gridded one.
   - Alternative: a single geolocation store joined on `obs`.
7. MIPAS sits under `SCIAMACHY/` in the raw tree. Should it be moved or
   relabelled before an AIRS/MIPAS project reads it?
5. *(deferred)* The production variable subset.
