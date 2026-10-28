# TES (Aura L2 HDO Nadir, Lite v006)

Started 2026-10-28: decisions laid out for the user (T1-T12, below). Measured
2026-10-14 from header reads, sampled values and an integration test, and
re-probed 2026-10-28. This is the most irregular product, so the strongest
test of the shared reader interface (design condition 1).

## Raw data

```
raw/TES/TL2HDOLN_6-20241006_030112/TES-Aura_L2-HDO-Nadir_<YYYY-MM>_v006_Litev01.00.nc   (5 MB .. 1.7 GB)
```

- **Files:** 75 monthly files, 2004-09 .. 2010-12; **2005-06 is absent**, so
  the granule is a month. 71.5 GB in all (corrected 2026-10-28: not ~40 MB
  each). Netcdf4, uncompressed and contiguous, so reads are cheap.
  - **2,825,124 rows** in all (header count, 2026-10-28): 191 (2010-02) to
    68,558 (2008-07). Under 10,000 rows: 2004-09, 2004-10, 2005-04, 2010-01,
    2010-02, 2010-03, 2010-10.
  - The folder also holds an empty `.ipynb_checkpoints/`; the TES root a
    `.DS_Store`. The listing must ignore both.
- **Coverage gap:** Sarkar et al. (2026) use TES through 2015. 2011-2015 is
  absent from disk (flagged, not chased). It is not in v006 upstream either
  as far as can be checked: see T1.

## Upstream versions (CMR, 2026-10-28)

- **v006 is no longer listed in CMR** (no `TL2HDOLN` collection at version 6
  or 006). The on-disk files say `VERSIONID 6`, `LOCALVERSIONID
  L2_Products_Lite_Main:R01.00.00`, DOI `10.5067/AURA/TES/TESHDOLN_L2.006`,
  produced 2015-05-21.
- **V007 is the listed collection** (`C3215610255-LARC_CLOUD`, DOI
  `10.5067/AURA/TES/TL2HDOLN.007`, files `..._v007_Lite-v02.00.nc`): **73
  granules, 2004-08 .. 2015-12**, but **none from 2005-01 to 2008-11**, nor
  2010-04, 05, 08; 2011-2015 has 46 months, mostly 5-80 MB (reduced TES
  operations). It names a V8 successor whose DOI does not resolve.
- **V007 vs V006 for HDO** (V007 Data Quality Description): "essentially a
  zero-mean difference between the versions and the uncertainty calculation
  between versions are consistent"; the change is the GMAO a priori (GEOS
  5.12.4 for 5.9.1).
- Sizes of overlapping months agree (2004-09: 37.2 MB V007, 37.4 MB v006;
  2008-12: 794 MB, 0.80 GB), so V007 Lite is likely the same layout. Not
  checked: no V007 file is on disk.

## Probes, 2026-10-28 (2004-09, 2008-07, 2010-12; login node)

The audit over every file must confirm these.
- **Time is TAI93** (E4, settled): `Time` - (`YYYYMMDD` + `UT_Hour` as UTC
  since 1993) is exactly the leap seconds since 1993 (5 in 2004, 6 in
  2008), to 3 ms (`UT_Hour` is float32). `Time` is exact to 1 µs on every
  row (fractional seconds on every row).
- **Rows:** no fill in time, lat or lon; rows in time order; no repeated
  (time, lat, lon) or (`Run`, `Sequence`, `Scan`) in a file; every row's
  `YYYYMMDD` is in the file's month. `Grid_Targets` is 0..n-1.
- **Rows with no retrieval** (E8): 151 in 2008-07 have every profile and
  matrix at fill, `SpeciesRetrievalQuality` 0 and DOF 0.0 (not fill); cloud,
  surface temperature and flags are written. They are observations under
  the project rule (time, lat, lon written), so they are kept.
- **Stacked state** (E1 confirmed): `Species` equals `Retrieval/HDO_H2O`
  bitwise; `Pressure`, `Altitude` and `Retrieval/AirDensity` hold equal
  halves (fill included).
- **Levels:** 17 per species, the surface first (pressure falls with the
  index). Levels below the surface are fill at the front of each half (the
  Lite guide: "fill is put in at the front of each species"), identically in
  `Species`, `Pressure`, `Altitude`, `ConstraintVector`, `AirDensity`; the
  matrices are fill on the outer product of those levels. 2008-07: 45,561
  rows have 17 levels, the rest 10-16 (or none, E8). Level 0 is the surface
  pressure (p50 1013.7 hPa); `Grid_Pressure` gives 1040 there.
- **`Species` is bias-corrected HDO** (E10): `Original_Species` / `Species`
  is 1.0065 at p50 (0.996 .. 1.115) for HDO and exactly 1 for H2O. The Lite
  guide's correction, ln HDO_c = ln HDO - A_DD b with b = 0.00019 p - 0.067
  from the surface to 316.227 hPa and 0 above, is reproduced from the file
  (next point).
- **Kernel orientation, settled (E6): rows retrieved, columns true, as
  stored** (numpy `[obs, row, col]`). Fitting ln(`Original_Species`) -
  ln(`Species`) = A_DD (c1 + c2 p) on the HDO levels leaves a 5e-4 relative
  residual (p50) with the kernel as stored, and recovers the guide's
  coefficients on all three files (c1 -0.068, c2 0.000191); with the kernel
  transposed the residual is 0.30 and the coefficients scatter. (An
  `A S_m` symmetry test leaned the same way, 0.3 vs 1.1, but did not
  calibrate on TROPESS v2, so it is not evidence.) The Lite guide names the
  blocks in IDL order: `[1,0]` `HDO_H2OAVERAGINGKERNEL` is numpy
  `[0:17, 17:34]`.
- **`DegreesOfFreedomForSignal` is the trace of the HDO block** (to 6e-7),
  not of the 34x34 kernel, the H2O block or a ratio kernel.
- **`Retrieval/Initial` equals `ConstraintVector`** on every row.
- **Covariances** (sampled 500 targets per file): symmetric to 1e-7, no
  negative variance in any of the three.
- **Flags:** `SpeciesRetrievalQuality` 0/1 (79% good in 2008-07);
  `GlobalSurveyFlag` 0/1 (38% special observations); `DayNightFlag` 0/1;
  `SurfaceTypeFootprint` 1 freshwater, 2 saltwater, 3 land, 4 mixed (not a
  land flag).

## Decisions for the user (2026-10-28)

Proposed answers in **bold**; the user decides each.

- **T1. Which collection.** v006 is on disk (2004-09 .. 2010-12, 75 months,
  2.8 M rows) and retired from CMR; V007 is current but lacks 2005-01 ..
  2008-11 upstream (the bulk of TES), and adds 2011-2015 (46 small months).
  The two must not share a store (a version per store). Options: (a) v006
  only; (b) V007 only, downloaded by the data-access session; (c) both, as
  separate products (`v_6`, `v_7`), as TROPESS v1 and v2. **Proposed: build
  v006 now; ask the data-access session to fetch V007 and to check whether
  its 2005-2008 exists outside CMR; decide V007 once it is on disk.** The
  decisions below are written so they carry to V007 if its layout matches.
- **T2. Name and version.** **`wisosat.tes.v_6.inst.native_swath.<variable>.zarr`**,
  from `VERSIONID 6` (as TROPESS `VersionID` 1 gave `v_1`). Checked on
  every file: `SHORTNAME` `TL2HDOLN`, `VERSIONID` 6, `LOCALVERSIONID`
  `L2_Products_Lite_Main:R01.00.00`, platform `Aura`, instrument `TES` (all
  in `coremetadata`), and the file name's `v006_Litev01.00`.
- **T3. Granules.** **One monthly file per granule, monthly coverage
  (`expected_missing_months: [2005-06]`, as SCIAMACHY).** 2005-06 cannot be
  checked against a v006 listing (retired); V007 has no 2005 at all. Stated
  in `known_data_gaps` with that evidence.
- **T4. The store set** (each needs its key row; new nomenclature rows
  marked *new row*):

  | store | source | conversion |
  | --- | --- | --- |
  | geolocation | `Time`, `Latitude`, `Longitude` | T6 |
  | `water_vapor_hdo_mole_fraction_dry_air` *(new row)* | `Species[:, 0:17]` (bias-corrected) | x 1e6 |
  | `water_vapor_h2o_mole_fraction_dry_air` | `Species[:, 17:34]` | x 1e6 |
  | `water_vapor_hdo_mole_fraction_dry_air_apriori` | `ConstraintVector[:, 0:17]` | x 1e6 |
  | `water_vapor_h2o_mole_fraction_dry_air_apriori` | `ConstraintVector[:, 17:34]` | x 1e6 |
  | `water_vapor_hdo_and_h2o_mole_fraction_dry_air_averaging_kernel_log` | `AveragingKernel`, 4 blocks | none |
  | `..._observation_error_covariance_log` | `ObservationErrorCovariance`, 4 blocks | none; no `Units`, declared `ln(vmr)^2` |
  | `..._measurement_error_covariance_log` | `Characterization/MeasurementErrorCovariance`, 4 blocks | none |
  | `..._total_error_covariance_log` | `Characterization/TotalErrorCovariance`, 4 blocks | none |
  | `pressure` | `Pressure[:, 0:17]`; 17:34 must equal | x 100 |
  | `altitude` | `Altitude[:, 0:17]`; 17:34 must equal | none (m) |
  | `quality_flags_retrieval` | `SpeciesRetrievalQuality` | int32; 1 good |
  | `water_vapor_hdo_mole_fraction_dry_air_degrees_of_freedom_for_signal` *(new row)* | `DegreesOfFreedomForSignal` | trace of the HDO block |
  | `cloud_effective_optical_depth` | `AverageCloudEffOpticalDepth` | none |
  | `cloud_top_pressure` | `CloudTopPressure` | x 100 |
  | `temperature_surface` | `SurfaceTemperature` | none (K) |
  | `day_night_flag` | `DayNightFlag` | int32 |

  17 stores. The kernel and covariance blocks map as in the naming pass
  (Model-comparison variables, below). Every array the paper grids is here.
- **T5. Optional stores, for the user** (proposals in bold):
  - **`GlobalSurveyFlag`: in**, as a new row (e.g. `global_survey_flag`, 1
    global survey, 0 special observation). 38% of rows are special
    observations, a different sampling; the Lite guide points users to it.
  - **`SurfaceTypeFootprint`: in**, as a new row (e.g. `surface_type`, 1-4
    as published). It is not `land_flag` (4 classes; deriving one would be
    a derivation). Or leave out.
  - **`Retrieval/AirDensity` as `air_molar_density`** (row exists since
    TROPESS v2), / N_A, halves equal: **in**, for parity with TROPESS v2. TES
    has no `standard_name`s, so no exception is needed.
  - **`Characterization/TotalColumnDensity` (E2) and its error: out.** HDO
    only, with a mislabelled unit, and nothing pairs it; the paper does not
    use it.
  - **Footprint corners (`Geolocation/{Latitude,Longitude}_Footprint_1..4`)
    in the geolocation store: in**, as TROPOMI's.
- **T6. Time.** **TAI93 less the leap seconds (5, 6 from 2006-01-01, 7 from
  2009-01-01), checked against `YYYYMMDD` + `UT_Hour` on every row (3 ms
  tolerance), stored in µs**: the coarsest unit that holds the source
  exactly (TROPOMI ms, GOSAT ns).
- **T7. Rows.** **Every row kept** (E8's no-retrieval rows hold NaN
  profiles); time order checked, as the probes found it (no `time_order:
  source` needed unless the audit says otherwise); the repeat check across
  month seams in the audit.
- **T8. Fill (E3).** **Declared per source in the key**: -999.0, -999 or -99,
  some given as the string `'-999.00'`; `Geolocation/Run` has none.
- **T9. Levels.** **17 per species, `vertical_order: surface_first`**; slices
  `[:, 0:17]` and `[:, 17:34]`, matrices as four blocks; `source_remainders`
  `equal` for `Pressure`, `Altitude` and `AirDensity`. Below-surface fill
  stays NaN.
- **T10. Filtering guidance in the metadata.** `SpeciesRetrievalQuality ==
  1` (Lite guide, V007 quality summary), then DOF; Sarkar et al. (2026)
  strict (COD <= 0.5, DOF >= 1) and relaxed (COD <= 3.6, DOF >= 0.5);
  the HDO bias correction already applied (E10); `GlobalSurveyFlag`.
- **T11. Left out.** `Retrieval/HDO_H2O` (= `Species`), `Retrieval/Initial`
  (= `ConstraintVector`), `Retrieval/Original_Species` (uncorrected; the
  recommended correction is applied), the 67-level grid (`Pressure_FM`,
  `Altitude_FM`, `Map`), `AveragingKernelDiagonal`, the cloud spectra, the
  `*_QA` and residual diagnostics, surface-temperature retrieval fields,
  angles, `YearFloat`, `YYYYMMDD`, `UT_Hour`, `Run`/`Sequence`/`Scan`,
  `TropopausePressure`, `L1BOzoneBandFlux`.
- **T12. Size and cost.** 2.8 M obs: each 4-block matrix store ~13 GB
  uncompressed, ~52 GB for the four; blosc zstd + shuffle on them, as
  TROPESS v2. Raw is 71.5 GB. A build and a verify should each be a few
  core-hours at most. The audit of every file reads ~71 GB, so it runs as a
  batch job (shown first).

Then, as TROPESS v2: the audit of every file, the production subset
reviewed in place, the nomenclature rows (shown before commit), the reader
at fixture level, the full fixture test, a bench, production, finalize.

## Format: non-CF, handle explicitly

- **Groups:** root, `Characterization`, `Geolocation`, `Retrieval`.
- **Dims:** observation dim `Grid_Targets`; `Grid_Pressure_Composite` 34;
  `Grid_Pressure` 17; `Grid_Pressure_FM` 67; `Grid_Cloud` 25.
- **Capitalised attributes:** `Units`, `FillValue` and `MissingValue`, not
  `units` / `_FillValue`, so **xarray will not mask fill**.
  - Fills seen: -999, -999.0 and -99 (integer flags). Declare them per
    variable.
- **Time:** `Time` is float64 "seconds since some reference (1993-01-01
  00:00:00)", calendar `julian`.
  - Likely TAI93, which counts leap seconds. Check it against `YYYYMMDD` and
    `UT_Hour` before trusting it.
- **Geolocation:**
  - `Latitude`, `Longitude` (float32);
  - footprint corners `Geolocation/{Latitude,Longitude}_Footprint_1..4`
    (float64);
  - `Pressure` (hPa) on the 34-level composite grid.

## Two upstream defects (found 2026-10-14)

1. **`Species` stacks two profiles.** Levels 0-16 are the HDO dry-air VMR and
   17-33 the H2O dry-air VMR, on the same 17 pressures repeated (verified
   equal).
   - `Retrieval/HDO_H2O` is **an identical array**; despite its name it is
     not a ratio. Store it once.
   - `AveragingKernel` (34 x 34), `ObservationErrorCovariance` and the
     `Characterization/*ErrorCovariance` (ln(vmr)^2) are stacked the same
     way. Each splits into **four 17 x 17 blocks** (HDO-HDO, HDO-H2O,
     H2O-HDO, H2O-H2O), keeping the cross blocks (style guide rule).
   - The kernel is in ln(vmr) space, rows the retrieved state and columns
     the true state, per its own `LongName` (2026-10-19).
   - In the three covariances, `S_HD` is exactly `S_DH` transposed (3,000
     targets, 2008-07). `ObservationErrorCovariance` has no `Units`
     attribute; its siblings say `ln(vmr)^2` (2026-10-19).
   - Split HDO: p50 4.7e-8. Split H2O: p50 2.2e-4. HDO/H2O p50 2.2e-4. Implied
     δD runs from -82 per mil at the surface to -650 aloft, which is physical.
2. **`Characterization/TotalColumnDensity` is mislabelled.** It says
   `molecules/m2`, but the values are the **HDO column in molec cm-2**.
   - Integrating the HDO profile over pressure gives a median 7.83e22
     molecules/m2. The file holds exactly 1.000e-4 of that, per target.
   - Declare the corrected source unit (with this evidence) in the key and
     the metadata. Convert x 1e4 / N_A to `mol m-2`, not 1 / N_A.

## Variables and units

- **Split `Species`:** HDO and H2O VMR (`VMR` → `1e-6`, x 1e6), dry-air basis
  ("relative to dry air").
- **`ConstraintVector` and `Retrieval/Initial`:** a priori and initial values
  (`mole/mole` / `VMR`), stacked the same way → split, x 1e6.
- **`TotalColumnDensity`:** see defect 2.
- **Quality and filters:** `SpeciesRetrievalQuality` (1 = good),
  `DegreesOfFreedomForSignal`, `AverageCloudEffOpticalDepth`.
- **Fit diagnostics:** many `*_QA` diagnostics.

## Filtering guidance to record, not apply (Sarkar et al. 2026)

- Strict: COD <= 0.5 and DOF >= 1.
- Relaxed: COD <= 3.6 and DOF >= 0.5.

## Model-comparison variables (named 2026-10-19)

Named in the cross-product naming pass. The grammar and decisions are in
`docs/model-comparison-naming.md`; the rows are in `nomenclature_data.md`
(style_guides `fee64ec`). Units are after conversion. Not built yet.

- **Dims:** `Grid_Pressure_Composite` (34) holds HDO levels 0-16, then H2O
  17-33, on the same 17 pressures. It splits into `level` (17), the grid the
  file's own `Grid_Pressure` (17) describes. A matrix's second axis is
  `level_2`.
- **Rows and columns:** rows are the retrieved state, columns the true state.
  The file's `AveragingKernel` description says: "sensitivity of retrieved
  ln(vmr) to the true ln(vmr)". Confirmed from the data 2026-10-28 (E6).
- **Vertical order:** `surface_first`.

| source | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- |
| `ConstraintVector[0:17]` | `water_vapor_hdo_mole_fraction_dry_air_apriori` | 1e-6 | (obs, level) | x 1e6 from `mole/mole` |
| `ConstraintVector[17:34]` | `water_vapor_h2o_mole_fraction_dry_air_apriori` | 1e-6 | (obs, level) | x 1e6 |
| `AveragingKernel[0:17, 0:17]` | `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log` | unitless | (obs, level, level_2) | none |
| `AveragingKernel[0:17, 17:34]` | `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log_cross_h2o` | unitless | (obs, level, level_2) | none |
| `AveragingKernel[17:34, 0:17]` | `water_vapor_h2o_mole_fraction_dry_air_averaging_kernel_log_cross_hdo` | unitless | (obs, level, level_2) | none |
| `AveragingKernel[17:34, 17:34]` | `water_vapor_h2o_mole_fraction_dry_air_averaging_kernel_log` | unitless | (obs, level, level_2) | none |
| `ObservationErrorCovariance`, 4 blocks | `water_vapor_{hdo,h2o}_mole_fraction_dry_air_observation_error_covariance_log[_cross_{h2o,hdo}]` | unitless | (obs, level, level_2) | none; no `Units` attribute, declared `ln(vmr)^2` |
| `Characterization/MeasurementErrorCovariance`, 4 blocks | `water_vapor_{hdo,h2o}_mole_fraction_dry_air_measurement_error_covariance_log[_cross_{h2o,hdo}]` | unitless | (obs, level, level_2) | none; `ln(vmr)^2` |
| `Characterization/TotalErrorCovariance`, 4 blocks | `water_vapor_{hdo,h2o}_mole_fraction_dry_air_total_error_covariance_log[_cross_{h2o,hdo}]` | unitless | (obs, level, level_2) | none; `ln(vmr)^2` |
| `Pressure[0:17]` | geolocation `pressure` | Pa | (obs, level) | x 100 from `hPa`; the build checks that both halves are equal on every obs |

- **Blocks:** every matrix maps as the kernel does.
  - `[0:17, 0:17]` is the HDO block; `[0:17, 17:34]` is HDO `_cross_h2o`.
  - `[17:34, 0:17]` is H2O `_cross_hdo`; `[17:34, 17:34]` is the H2O block.
  - Both cross blocks are kept, though in each covariance `S_HD` is exactly
    `S_DH` transposed.
- **The error budgets:**
  - `observation`: measurement + systematic + cross-state. The file says it
    is "for comparisons with other measurements and for assimilation".
  - `measurement`: propagated radiance noise.
  - `total`: smoothing + systematic + measurement.
- **Stores: 6.** A matrix published in pieces is one store (style guide,
  Level 2).
  - The two priors are one store each.
  - The kernel's 4 blocks are arrays in
    `water_vapor_hdo_and_h2o_mole_fraction_dry_air_averaging_kernel_log`.
  - Each covariance's 4 blocks are arrays in
    `water_vapor_hdo_and_h2o_mole_fraction_dry_air_{observation,measurement,total}_error_covariance_log`.
  - This needs multi-array variable stores in the shared code first.
- **Sizes:** ~40 GB uncompressed for the 12 covariance blocks, ~3.4 GB each.
- **Left out:**
  - `AirDensity`, a number density on levels; no dry-air partial column is
    published.
  - The 67-level forward-model grid (`Grid_Pressure_FM`: `Altitude_FM`,
    `Pressure_FM`, `Map`). If it is ever stored, it needs its own dim name
    (e.g. `level_fm`).

## Known data issues

Status: **handled** (the pipeline deals with it), **open** (settle before this product is built), **record only** (users should know; kept as published).

(2026-10-14).

| # | issue | status |
| --- | --- | --- |
| E1 | **`Species` stacks two profiles**: levels 0-16 are HDO and 17-33 are H2O, on the same 17 pressures repeated. `Retrieval/HDO_H2O` is an identical array, not a ratio. `AveragingKernel`, `ObservationErrorCovariance` and the `Characterization/*ErrorCovariance` stack the same way into 2 x 2 blocks. | open: split into one store per quantity and the matrices into blocks, cross blocks kept (style guide) |
| E2 | **`TotalColumnDensity` is mislabelled `molecules/m2`; the values are the HDO column in molec cm-2.** Integrating the HDO profile gives exactly 1e4 times the stored value for every target. | open: declare the corrected source unit and its evidence in the key; convert x 1e4 / N_A |
| E3 | **Non-CF attributes**: `Units`, `FillValue`, `MissingValue` (capitalised), so xarray does not mask fill. Fill values seen: -999, -999.0 and -99. | open: declare per variable |
| E4 | **Time is "seconds since 1993-01-01"** with calendar `julian`. It is TAI93: it leads `YYYYMMDD` + `UT_Hour` by exactly the leap seconds since 1993 (probes 2026-10-28). | open: subtract the leap seconds, check every row (T6) |
| E5 | **2011-2015 is absent from disk** (Sarkar et al. 2026 use TES through 2015). Upstream it is in V007 only; v006 is retired from CMR (T1). | record only: flagged, not chased |
| E6 | **Kernel orientation:** rows retrieved, columns true, as stored. Settled by reproducing the Lite HDO bias correction through the HDO block (5e-4 residual; transposed 0.30). | settled (2026-10-28) |
| E7 | **v006 is retired; V007 lacks 2005-01 .. 2008-11 upstream** (CMR, 2026-10-28). | open: T1 |
| E8 | **Rows with no retrieval:** every profile and matrix at fill, quality 0, DOF 0.0 (151 in 2008-07). | open: kept as observations (T7) |
| E9 | **2005-06 is absent** from v006 on disk; no v006 listing exists to check it against. | open: declare (T3) |
| E10 | **`Species` is the bias-corrected HDO** (Lite guide); `Original_Species` is uncorrected. H2O is uncorrected in both. | open: store `Species`, state the correction (T10, T11) |
