# SCIAMACHY (SRON SICOR L2 H2O/HDO, file version 0110)

Not started. Measured 2026-10-14 from header reads and one file's values.

## Raw data

```
raw/SCIAMACHY/HDO_SICORv10/<YYYYMM>/sci_l2_h2o_hdo_0110_<orbit:05d>.nc   (~4 MB)
```

- 41,616 files, one per orbit, across 112 month folders (2003-01 .. 2012-04);
  ~1,876 obs per file, ~7.8e7 in all.
- **Same file format as TROPOMI** (same SRON Sicor processor, `version` 8.1):
  - groups `target_product`, `instrument`, `diagnostics`, `meteo`,
    `side_product`;
  - observation dim `nobs`, with `instrument/time` as a 7-integer broken-down
    timestamp;
  - no `_FillValue` attributes.

  Expect to reuse most of the TROPOMI reader. That is also why SCIAMACHY is a
  poor choice for the "deliberately different" second reader.
- **Dims:** `nlayer` 60, `nlevel` 61, `ncorner` 4, `nwin` 1, `ntime` 7;
  `side_product` adds `nbaseline` 4.
- **Fill:** no `9.96921e36` was seen in the sampled file, but check the fill
  convention against several files before declaring it. Some retrieved
  columns are negative (e.g. `hdo_column` -9.3e16), which is real retrieval
  output, not fill.
- **Not SCIAMACHY:** `raw/SCIAMACHY/H2O` and `raw/SCIAMACHY/HDO` hold ESA
  MIPAS files and are excluded.

## Variables and units

- `target_product/h2o_column` and `hdo_column`, their `_precision`s and
  `_apriori`s are in `molec. cm-2` and convert to `mol m-2` (x 1e4 / N_A).
  - Value check, one file: p50 1.1e22 and 4.3e18.
- Column averaging kernels on `nlayer` (`1`, p50 0.27) and a priori profiles
  on `nlayer`.
- **No δD is published.** WISO-SAT derives it; deriving it here would be a new
  quantity, not a conversion, and needs approval.
- Quality flag: `diagnostics/processing_quality_flags`.

## Filtering guidance to record, not apply (Sarkar et al. 2026)

- flag 0, iterations < 12, SZA < 70°;
- 0.7 <= H2O/H2O_apriori <= 1.3 and 0.9 <= CH4/CH4_apriori <= 1.1;
- -600 < δD < 0 per mil;
- log(RMS) within ±6σ of its median; log(uncertainty) for H2O and HDO within
  ±5σ, per file.

## Geolocation

- Granule: an orbit file.
- Geolocation store: ~1.25 GB (lat/lon/time) plus 19 GB for the pressure grid
  (61 levels), uncompressed.
