# TES (Aura L2 HDO Nadir, Lite v006)

Not started. Measured 2026-10-14 from header reads, sampled values and an
integration test. This is the most irregular product, so the strongest test
of the shared reader interface (design condition 1).

## Raw data

```
raw/TES/TL2HDOLN_6-20241006_030112/TES-Aura_L2-HDO-Nadir_<YYYY-MM>_v006_Litev01.00.nc   (~40 MB)
```

- **Files:** 75 monthly files, 2004-09 .. 2010-12 (2005 has 11 months), so
  the granule is a month.
  - Obs per file vary widely: 47,426 / 46,285 / 58,907 / 961 sampled;
    ~2.9e6 in all.
- **Coverage gap:** Sarkar et al. (2026) use TES through 2015. 2011-2015 is
  absent from disk (flagged, not chased).

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

## Known data issues

Status: **handled** (the pipeline deals with it), **open** (settle before this product is built), **record only** (users should know; kept as published).

(2026-10-14).

| # | issue | status |
| --- | --- | --- |
| E1 | **`Species` stacks two profiles**: levels 0-16 are HDO and 17-33 are H2O, on the same 17 pressures repeated. `Retrieval/HDO_H2O` is an identical array, not a ratio. `AveragingKernel`, `ObservationErrorCovariance` and the `Characterization/*ErrorCovariance` stack the same way into 2 x 2 blocks. | open: split into one store per quantity and the matrices into blocks, cross blocks kept (style guide) |
| E2 | **`TotalColumnDensity` is mislabelled `molecules/m2`; the values are the HDO column in molec cm-2.** Integrating the HDO profile gives exactly 1e4 times the stored value for every target. | open: declare the corrected source unit and its evidence in the key; convert x 1e4 / N_A |
| E3 | **Non-CF attributes**: `Units`, `FillValue`, `MissingValue` (capitalised), so xarray does not mask fill. Fill values seen: -999, -999.0 and -99. | open: declare per variable |
| E4 | **Time is "seconds since 1993-01-01"** with calendar `julian`; likely TAI93, which counts leap seconds. | open: check against `YYYYMMDD` and `UT_Hour` |
| E5 | **2011-2015 is absent from disk** (Sarkar et al. 2026 use TES through 2015). | record only: flagged, not chased |
