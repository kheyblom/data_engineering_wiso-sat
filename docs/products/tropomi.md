# TROPOMI (SRON HDO L2, product version 0003)

Product notes for the TROPOMI reader, configs and key. Rules that apply to every
product are in the root `CLAUDE.md` and the style guide; cross-product evidence
is in `docs/l2-survey.md`.

## Raw data (measured 2026-10-13/14)

```
/glade/derecho/scratch/kheyblom/data/wiso-sat/raw/TROPOMI/tropomi.grid.surfsara.nl/
  hdo/<YYYY>/<MM>/<DD>/<orbit>/s5p_l2_hdo_<product_version>_<orbit:05d>.nc
  hdo/2017/11/08/373/s5p_l2_hdo_0003_00373.nc     (~1.1 GB each)
```

- **Files:** 31,492 orbits from 2017-11-08 to 2024-05-30. Orbits per day
  vary (5-14 seen); not every orbit has a file. Product version `0003` (from
  the filename); processor version `8.1` (root `version` attribute).
- **Groups:** there are no root variables, so open each group with `group=`.
  - `target_product`: deltad, h2o/hdo columns, precisions, averaging kernels,
    a priori profiles.
  - `instrument`: lat/lon centre and corners, time, geometry, pixel ids.
  - `diagnostics`: the flags.
  - `meteo` and `side_product`.
- **Observation layout:** everything is indexed by `nobs`, the full L1B swath
  flattened in scanline-then-pixel order (e.g. 4173 x 215 = 897,195).
  - Scanline = i // 215 and ground pixel = i % 215 within an orbit. The
    verifier must confirm this for every orbit.
  - `nobs` is ~697,800 per orbit in 2018-2019 and exactly 896,980 in every
    orbit sampled from 2020 on (the Aug 2019 along-track resolution change).
  - The record totals ~2.6e10 observations: ~105 GB uncompressed per 1-D
    float32 variable, ~5.2 TB per `(obs, 50)`.
- **Secondary dims:**
  - `nlayer` 50, `nlevel` 51, `ncorner` 4;
  - `nwin` 1 (squeeze);
  - `ntime` 7: `instrument/time` is a broken-down timestamp
    (year .. millisecond) that becomes `time`.
- **Fill:** there is no `_FillValue`. Missing values are the netCDF default
  float fill `9.96921e36`, so declare it in config and mask it.
  - In orbit 16820, 71% of `nobs` have an `hdo_column` and 65% have
    `processing_quality_flags == 0`.
- **Flags:** `quality_flag`, `convergence` and `glintflag` are "Not
  implemented". `processing_quality_flags` is the real flag (CF
  `flag_masks`/`flag_values`).
- **Storage:** variables are uncompressed, one HDF5 chunk spanning the whole
  variable, so reading one variable of one orbit is ~5 MB.
- **Units:**
  - `deltad` is a fraction (`1`; median -0.25), so it converts x 1000 to per
    mil.
  - Columns are `molec. cm-2`. Some units are byte strings (`b'1'`); decode
    them.
- **`standard_name`s** are SRON's own (`delta_d`, `water_column`, ...). Keep
  them unchanged, per the guide.
- **Day boundary:** in the sampled pair, orbits did not straddle UTC midnight.
  The build checks `time` never decreases.
- **Value notes:**
  - `processing_quality_flags == 0` still passes δD from -0.99 to +13
    (p1/p99) and `h2o_column` up to 1.7e26, so more filtering is needed
    downstream.
  - The column kernels reach p99 ~700 in some layers; this is unexplained and
    not a unit issue.

## Build details (task 4)

- **Granule:** an orbit. The granule index has ~31.5k entries and is stored as
  one chunk. Resume starts after the last committed orbit, whose index entry
  is written in the same commit as its data.
- **Appends:** orbit sizes vary, so appends do not land on chunk boundaries.
  Each append rewrites the trailing partial chunk, which is safe only with a
  single writer.
- **Missing days:** declared in config as `expected_missing_days`. The build
  fails on any gap that is not declared.
- **Chunking starting points for the bench** (the guide allows 5-40 MiB):
  - 4,194,304 obs for 1-D float32 (16 MiB);
  - 131,072 obs for `(obs, 50)` float32 (25 MiB).
- **Geolocation store:**
  - `time`;
  - `lat`, `lon` (pixel centre);
  - `pressure` on `level` (`meteo/pressure_levels`, 51 interfaces, Pa);
  - pixel corners, optional (`corner`, 32 B/obs).
- **Filtering guidance to record in metadata, not apply** (Sarkar et al. 2026):
  - iterations <= 10;
  - SZA <= 70°;
  - cloud optical thickness < 0.3;
  - surface albedo >= 0.02;
  - the clear-sky criteria of Schneider et al. (2022) Table 1.

## Variable candidates (decision pending: the production subset)

Proposed canonical names run general to specific, like the existing key.

**Core: the retrieval plus the mandatory flag.**

| source | proposed canonical_name | units | conversion |
| --- | --- | --- | --- |
| `target_product/deltad` | `water_vapor_column_delta_d` | 1e-3 | x 1000 |
| `target_product/deltad_precision` | `water_vapor_column_delta_d_standard_error` | 1e-3 | x 1000 |
| `target_product/h2o_column` | `water_vapor_column` | mol m-2 | x 1e4 / N_A |
| `target_product/h2o_column_precision` | `water_vapor_column_standard_error` | mol m-2 | x 1e4 / N_A |
| `target_product/hdo_column` | `water_vapor_column_hdo` | mol m-2 | x 1e4 / N_A |
| `target_product/hdo_column_precision` | `water_vapor_column_hdo_standard_error` | mol m-2 | x 1e4 / N_A |
| `diagnostics/processing_quality_flags` | `retrieval_quality_flags` | 1 | none (int32; mandatory) |

**Model comparison: kernels and priors** (50 layers each, ~5.2 TB uncompressed).

| source | proposed canonical_name | units | conversion |
| --- | --- | --- | --- |
| `target_product/h2o_column_averaging_kernel` | `water_vapor_column_averaging_kernel` | 1 | none |
| `target_product/hdo_column_averaging_kernel` | `water_vapor_column_hdo_averaging_kernel` | 1 | none |
| `target_product/h2o_profile_apriori` | `water_vapor_partial_column_apriori` | mol m-2 | x 1e4 / N_A |
| `target_product/hdo_profile_apriori` | `water_vapor_partial_column_hdo_apriori` | mol m-2 | x 1e4 / N_A |
| `meteo/dry_air_subcolumns` | `dry_air_partial_column` | mol m-2 | x 1e4 / N_A |

**Optional: inputs to the WISO-SAT filter**, so users can reproduce it
without the raw files.

| source | proposed canonical_name | units | conversion |
| --- | --- | --- | --- |
| `diagnostics/iterations` | `retrieval_iterations` | 1 | none (int32) |
| `instrument/solar_zenith_angle` | `solar_zenith_angle` | degree | none |
| `side_product/aerosol_optical_thickness` | `scattering_optical_thickness` | 1 | none (squeeze `nwin`) |
| `side_product/surface_albedo` | `surface_albedo` | 1 | none (squeeze `nwin`) |

- **Clear-sky criteria:** Schneider et al. (2022) Table 1 may need more inputs
  (likely CH4-based). Check it before closing the optional set.
- **"Cloud optical thickness" mapping:** mapping the paper's term to
  `aerosol_optical_thickness` (SRON's scattering layer) is an inference, to be
  confirmed.
- **Left out unless asked:**
  - the other `meteo/` fields;
  - the CH4/CO side products;
  - the other aerosol and albedo parameters;
  - the fit diagnostics.
