# GOSAT and GOSAT-2 (IUP FOCAL v3.0.1)

Not started. Measured 2026-10-14 from header reads and one file's values per
product. A good candidate for the second reader under design condition 1:
flat, small and simple, so it is a cheap test of the shared interface.

## Raw data: four products

The DED and H2O files hold **different soundings**: on one day DED had 777
and H2O had 1,666. So each is its own product, with its own `obs` axis and
its own geolocation store.

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
