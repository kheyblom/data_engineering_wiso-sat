# Level 2 standards — draft proposal (task 3)

**Status: proposal, awaiting approval.** Once agreed, the rules go into
`style-guide_data_engineering.md` under "Level 2 satellite retrieval data", the
variables into `nomenclature_data.md`, and this file is deleted.

Each rule names the gridded precedent it follows. The aim is that a Level 2
store differs from a gridded one only where the data's shape forces it.

## Evidence (measured 2026-10-13, header reads + one orbit's flags/time)

- One file per orbit, `hdo/YYYY/MM/DD/<orbit>/s5p_l2_hdo_0003_<orbit>.nc`,
  ~1.1 GB, 5-14 orbits per day. Processor version `8.1` (root attr),
  product version `0003` (filename).
- Every variable is indexed by `nobs` = the full L1B swath flattened
  (scanline x 215 ground pixels, e.g. 4173 x 215 = 897,195), in scanline then
  pixel order. Secondary dims: `nlayer` 50, `nlevel` 51, `ncorner` 4, `nwin` 1,
  `ntime` 7 (a broken-down timestamp, ms resolution).
- No `_FillValue` anywhere; missing = netCDF default float fill `9.96921e36`.
  In orbit 16820: 71% of `nobs` have an `hdo_column`, 65% have
  `processing_quality_flags == 0`, and 54k flagged obs still carry values
  (e.g. `deltad = -7593`, i.e. unphysical).
- `quality_flag` and `convergence` are "Not implemented";
  `processing_quality_flags` is the real flag (CF `flag_masks`/`flag_values`).
- Upstream `standard_name`s are mostly not CF standard names (`delta_d`,
  `water_column`, `heavy_water_column`). Several `units` are byte strings
  (`b'1'`). Columns are in `molec. cm-2`, which udunits cannot parse.
- In the sampled pair, orbits did not straddle UTC midnight (2021-01-10 last
  orbit ends 23:40, 2021-01-11 first starts 00:23). Not yet checked for the
  whole record.

## Proposed rules

**L2-1. Store unit: one store per variable per UTC day.**
Follows the general one-store-per-variable rule; the day is the partition.
Replaces, for L2 only, the gridded rule requiring separate spatial and temporal
stores: an observation list has no lat/lon axes to chunk against, so there is
one layout (L2-8).

**L2-2. A day is the UTC date of the observation time**, not the raw directory.
The build checks every observation falls on the store's day; an orbit that
straddles midnight is split by observation time. Observations keep source order
(orbit, scanline, ground pixel), which is also time order.
*Precedent: the gridded time axis is derived from the data, never assumed.*

**L2-3. No observation selection and no quality filtering.** Every observation
in the raw files is kept, failed retrievals included (they read back NaN). The
quality flag is its own variable store and is **mandatory in every production
run**; filtering is the consumer's job, and upstream filtering guidance goes in
metadata. *Precedent: "exactly represents the original data"; MSWEP's
"declared, not detected". It also makes verification a 1:1 index mapping, and
NaN runs compress to almost nothing.*

**L2-4. Sibling stores of one day share an identical observation axis.** The
same `obs` length and identical coordinates in every variable's store for that
day, so `xr.merge(..., join='exact')` always works. Build and verifier both
check it. *Precedent: GLEAM's `check_time_axis` pinning a variable family.*

**L2-5. Dimensions and coordinates.**
- Observation dimension `obs` (from `nobs`).
- Coordinates in every store: `time`, `lat`, `lon` (pixel centre), plus
  traceability coordinates `orbit`, `scanline` and `ground_pixel`, which map
  every observation back to its raw file and index. They compress to little.
- Secondary dims renamed, dropping the `n` prefix: `layer`, `level`, `corner`.
  Length-1 dims (`nwin`) are squeezed. `ntime` becomes the `time` coordinate.
  Each change is recorded in metadata.
- Pixel corners are not coordinates; they are their own variable stores, if
  selected.
*Precedent: gridded stores use `time`/`lat`/`lon`; the same names let one
reader serve both.*

**L2-6. Time encoding: int64 `milliseconds since 1900-01-01`,
`proleptic_gregorian`.** Same epoch and calendar as the gridded
`days since 1900-01-01`; milliseconds because the source resolves them.

**L2-7. Fill values.** Undeclared source fill is declared in config
(`source_fill_values: [9.96921e36]`), checked to occur before masking, masked
to NaN, and recorded in a `source_fill_values_masked` attribute. Floats store
NaN as fill. Integer variables keep their dtype (never cast to float for NaN)
and carry an explicit `_FillValue`. *Precedent: MSWEP `source_fill_values`,
`check_source_fill`, and the dtype rules.*

**L2-8. Chunking: one layout, chunked only along `obs`.**
- Target ~16-32 MiB uncompressed per chunk, matching the gridded 24.7 MiB.
  Starting points for the task 4 bench: 4,194,304 obs for 1-D float32
  (16 MiB, ~3-4 chunks/day), 131,072 obs for `(obs, 50)` float32 (25 MiB).
- Secondary dims (`layer`, `level`, `corner`) are never split.
- Coordinates are chunked like the data: unlike gridded index coordinates they
  are as long as the data.
- Default zarr v3 zstd compression, as in the gridded stores.

**L2-9. Naming and directory layout.**
```
<variable>/<YYYY>/<data_source>.<version>.<product>.<temporal_frequency>.<grid_name>.<variable>.<YYYYMMDD>.zarr
water_vapor_column_delta_d/2021/tropomi.v_0003.hdo.inst.native_swath.water_vapor_column_delta_d.20210110.zarr
```
- The date is a sixth component, after the variable, as `YYYYMMDD`.
- `v_0003.hdo` follows the existing version/product rule (`v_3_5.nrt`).
- `inst` is a **new temporal frequency** ("instantaneous observation, no
  temporal aggregation"): `day` means "daily average" in the key and would be
  wrong.
- `native_swath` is a **new grid name** meaning "the instrument's own pixels,
  not regridded", parallel to `native_0p1x0p1`.
- Directories: variable, then year. This keeps every directory at 366 entries
  or fewer (~2,400 days in all; GLADE prefers < 2-3k per directory).
  *Precedent: MSWEP's approved layout directory and year-split raw tree.*

**L2-10. Metadata.** The required `history`, `verification` and `date_created`,
plus:
- `Conventions: CF-1.11, ACDD-1.3` and `featureType: point`; the layout above is
  a CF discrete-sampling-geometry point collection.
- ACDD coverage read off the data: `time_coverage_start`/`end` and
  `geospatial_*` bounds.
- `source_files` (orbit files used), `orbits`, `product_version`,
  `processor_version`.
- Upstream attributes are kept as `original_*`. An upstream `standard_name` is
  kept only if it is a real CF standard name, else moved to
  `original_standard_name`. Byte-string attributes are decoded.
- `ancillary_variables`: names the sibling stores needed to interpret this
  one, e.g. an averaging kernel needs the pressure levels.
- `quality_filtering: none applied`, plus upstream filtering guidance.

*Precedent: GLEAM/MSWEP `original_*`, MSWEP's `standard_name` reasoning,
`related_store`, ACDD-1.3, `derive_attrs`.*

**L2-11. Missing days are declared.** `expected_missing_days` in config; the
build fails on any undeclared gap. Unlike gridded, a missing day produces **no
store** rather than an all-NaN one: there is no regular axis to keep aligned.
*Precedent: MSWEP `expected_missing_times`.*

**L2-12. Verification covers every observation, not a sample.** Raw variables
are uncompressed and one chunk each, so reading one variable of one orbit is
~5 MB. A full comparison costs about what the build cost. It checks:
- obs count = sum of the orbits' `nobs`
- values equal raw after masking and unit conversion
- coordinates equal raw
- every time falls on the store's day
- the shared axis across sibling stores

*Precedent: read-only verifier and the "earned verification" attribute.*

## Draft nomenclature additions (for the likely subset)

Names run general to specific, as the existing key does.

| canonical_name | canonical_units | long_name | source | conversion |
| --- | --- | --- | --- | --- |
| `water_vapor_column` | mol m-2 | total column water vapor | `h2o_column` | x 1e4 / N_A |
| `water_vapor_column_standard_error` | mol m-2 | standard error of total column water vapor | `h2o_column_precision` | x 1e4 / N_A |
| `water_vapor_column_hdo` | mol m-2 | total column HDO vapor | `hdo_column` | x 1e4 / N_A |
| `water_vapor_column_hdo_standard_error` | mol m-2 | standard error of total column HDO vapor | `hdo_column_precision` | x 1e4 / N_A |
| `water_vapor_column_delta_d` | 1 | delta-D of total column water vapor | `deltad` | none |
| `water_vapor_column_delta_d_standard_error` | 1 | standard error of delta-D of total column water vapor | `deltad_precision` | none |
| `water_vapor_column_averaging_kernel` | 1 | column averaging kernel, water vapor | `h2o_column_averaging_kernel` | none |
| `water_vapor_column_hdo_averaging_kernel` | 1 | column averaging kernel, HDO vapor | `hdo_column_averaging_kernel` | none |
| `retrieval_quality_flags` | 1 | retrieval processing quality flags | `processing_quality_flags` | none |

Temporal frequency: `inst` — instantaneous observation (no temporal aggregation).

## Decisions needed

1. **Keep every observation (L2-3)**, or drop all-fill (failed) observations
   to save space? Dropping breaks the 1:1 raw index mapping and has to be
   applied identically to every variable.
2. **Column units**: `mol m-2` (SI, udunits-parseable, the ESA TROPOMI L2
   convention, keeps HDO/H2O ratios trivial) vs `kg m-2` (matches reanalysis and
   AIRS precipitable water, but the HDO/H2O ratio then needs molar-mass
   correction) vs respelling `molec cm-2` with no value change (not udunits).
3. **delta-D units**: `1` as published (no conversion) vs per mil (x 1000).
4. **Filename**: are `inst`, `native_swath`, `v_0003.hdo` and the trailing
   `YYYYMMDD` acceptable?
5. **Which variables** make up the production subset? It decides which
   nomenclature rows are needed now.
