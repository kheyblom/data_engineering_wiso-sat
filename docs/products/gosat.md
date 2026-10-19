# GOSAT and GOSAT-2 (IUP FOCAL v3.0.1)

**GOSAT reader built at fixture level, 2026-10-14** (design condition 1, the
second reader): `products/gosat.py`, `nomenclature-key_gosat.md`,
`config/gosat/`, `validation/stage_gosat.py`. The fixture passes the
end-to-end test. GOSAT-2 is not configured yet; it has the same format, and the
reader's patterns already accept it.

## Raw data: four products

The DED and H2O files hold **partly overlapping sets of soundings**.

**Decided 2026-10-14 (user): merge them into one product per satellite.** The
obs axis is one obs per distinct sounding, the union of each day's two files
in time order. This approves a constructed obs axis. Measured over 13 sampled
days per satellite:

| | DED | H2O | in both | distinct |
| --- | --- | --- | --- | --- |
| GOSAT | 8,625 | 21,888 | 3,765 | 26,748 |
| GOSAT-2 | 7,230 | 16,394 | 3,343 | 20,281 |

- **Matching:** time, latitude and longitude, bit for bit. This finds exactly
  the pairs that FOCAL's pass/scene/sounding numbers find.
- **Shared fields:** all 16 the files share are identical on every matched
  sounding.
- **No duplicates** within a file, and both files are time ordered.
- **Absent values:** a variable is absent where its file lacks the sounding.
  Floats are NaN there; the integer flags hold the config's
  `absent_fill_values`, -2147483647, which FOCAL never writes.
- **Two flag stores:** each flag gets its own canonical name,
  `quality_flags_retrieval_delta_d` and `quality_flags_retrieval_h2o`.
- **Granule:** a day, holding both files. Its index entry names both.
- **Naming:** `wisosat.gosat.v_3_0_1...` and later `wisosat.gosat2...`.

```
raw/GOSAT/IUP-GHG-L2-{DED,H2O}-GOSAT-FOCAL-<YYYY>-v3.0.1/v3.0.1/<YYYY>/IUP-GHG-L2-{DED,H2O}-GOSAT-FOCAL-<YYYYMMDD>-v3.0.1.nc
raw/GOSAT-2/IUP-GHG-L2-{DED,H2O}-GOSAT-FOCAL-<YYYY>-v3.0.1/v3.0.1/<YYYY>/IUP-GHG-L2-{DED,H2O}-GOSAT2-FOCAL-<YYYYMMDD>-v3.0.1.nc
```

| product | years | files | obs/file (sampled) | ~obs |
| --- | --- | --- | --- | --- |
| GOSAT DED | 2009-2021 | 4,498 | ~545 | 2.5e6 |
| GOSAT H2O | 2009-2021 | 4,498 | ~1,607 | 7.2e6 |
| GOSAT-2 DED | 2019-2021 | 1,010 | ~602 | 6.1e5 |
| GOSAT-2 H2O | 2019-2021 | 1,010 | ~1,432 | 1.4e6 |

- **File names:** GOSAT-2 files say `GOSAT2` while their folders say `GOSAT`.
- **Files to skip:** the GOSAT-2 2019 folder also holds L3 files
  (`GOSAT2_monthly_1deg.nc`, `HDO_5x5_monthly.mat`), so glob
  `IUP-GHG-L2-*-FOCAL-*.nc`.
- **Granule:** a daily file, ~0.1-0.2 MB each.

## Format

- **Layout:** flat (no groups), `conventions: CF-1.6`.
- **Dims:** observation dim `sounding_dim`; `level_dim` 6, `layer_dim` 5.
- **Time:** `time` is float64 `seconds since 1970-01-01 00:00:00`, calendar
  `standard`.
- **Geolocation:** `latitude`, `longitude` (float32), `pressure_levels`
  (level_dim), `pressure_weight` (layer_dim).
- **Fill:** no fill attributes were seen in the sampled files, and they hold
  only quality-flag-0 soundings. The product arrives pre-filtered (FOCAL
  multi-stage QC, per Sarkar et al. 2026).

## Variables and units (all match the canonical units: no conversion)

- **DED:** `xded` and `xded_uncertainty` (`1e-3`, column-averaged δD; p50
  -136), plus `xded_quality_flag`.
- **H2O:**
  - `xh2o` and `xh2o_uncertainty` (`1e-6`, column-averaged dry-air mole
    fraction; p50 2,417);
  - `h2o_profile_apriori` (`1e-6`, layer);
  - `xh2o_averaging_kernel` (`1`, ~1.0);
  - `xh2o_quality_flag` (0 = good, 1 = bad).
- **`dry_column`:** on `layer_dim`, with units `no. of molecules` (no
  per-area unit). Value-check it before using it.
- **Basis:** XH2O is a dry-air mole fraction by definition (column / dry-air
  column).

## Build facts (measured 2026-10-14)

- **Files:** 4,498 days per kind, 2009-04-23 to 2021-12-31. 138 days have no
  files of either kind; the gap days are the same for DED and H2O. GOSAT-2 has
  1,010 days, 2019-02-05 to 2021-12-31, with 51 missing.
- **Version:** the root `product_version` attribute is `v3.0.1` in every file
  sampled; it names the stores.
- **Time** is float64 seconds since 1970 that sit on no decimal grid coarser
  than a nanosecond.
  - In an exact round trip of 38,003 sampled times, ms failed 99% and us 76%;
    ns held every one.
  - So GOSAT time is int64 nanoseconds since 1900. The time unit is per
    product, from the key's coordinate table.
- **The subset at fixture level:** δD and XH2O, their uncertainties, both
  flags, and SZA. The kernel, a priori, dry column and pressure grid wait for
  the cross-product naming pass.

## Known data issues

Status: **handled** (the pipeline deals with it), **open** (settle before this product is built), **record only** (users should know; kept as published).

| # | issue | status |
| --- | --- | --- |
| G1 | **DED and H2O are separate, separately filtered files** with only partly overlapping soundings. Over 13 sampled days, 44% of DED soundings were in the H2O file. Where both hold a sounding, all 16 shared fields are identical. | handled (user decision 2026-10-14): merged per day onto one axis of distinct soundings. A variable is absent where its file lacks the sounding. |
| G2 | **Pre-filtered upstream**: the files hold only soundings that passed IUP's quality control, and every flag sampled is 0. | record only: stated in `filtering_guidance` |
| G3 | **Time has no decimal grid coarser than a nanosecond.** It is float64 seconds since 1970. In an exact round trip of 38,003 sampled times, ms failed 99% and us 76%. | handled: stored as int64 ns since 1900 |
| G4 | **The time variable carries `calendar: standard`**, which blocks xarray's time encoding. | handled: kept as `original_calendar`; stored as proleptic_gregorian |
| G5 | **GOSAT: 138 days have no files, GOSAT-2: 51**, identical for DED and H2O. Not yet checked against upstream. | handled for GOSAT (`expected_missing_days`); GOSAT-2 not configured |
| G6 | **GOSAT-2 file names say `GOSAT2` while their folders say `GOSAT`.** The GOSAT-2 2019 folder also holds L3 files (`GOSAT2_monthly_1deg.nc`, `HDO_5x5_monthly.mat`). | handled: the reader accepts both names and matches L2 file names exactly |
| G7 | **`dry_column` has units `no. of molecules`**, with no per-area unit, and is **~1/4 of the hydrostatic dry column**. In molec cm-2, dp / (g M_dry) x N_A per layer over `dry_column` gives p1 / p50 / p99 3.97 / 3.99-4.00 / 4.04, on 2011-01-15 and 2015-06-01 (2,984 soundings; 2026-10-19). | open: held from the naming pass (`docs/model-comparison-naming.md` N11); not needed to apply the kernel |
| G8 | `xh2o` holds negative values (minimum -116.6 ppm in one sampled day). | record only |
