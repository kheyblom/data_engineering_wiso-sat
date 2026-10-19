# Model-comparison naming pass (TASKS.md task 7, step 1)

**Status: proposal, 2026-10-19, for user review.** Review in place with
`#@CLAUDE` comments. Nothing here is in `nomenclature_data.md` yet.

Scope: every product's column averaging kernels, a priori profiles, dry-air
partial columns and pressure grid, named once across all products. Evidence:
header reads of one file per product on 2026-10-19 (plus the 2026-10-14
survey), and the checks under Findings.

## 1. Decisions to make

| # | decision | recommendation | alternative |
| --- | --- | --- | --- |
| N1 | **Name grammar** | `<quantity>[_<vertical form>][_<species or form>][_<basis>][_<role>]`; roles are suffixes, as `_standard_error` already is (section 2) | — |
| N2 | **No `profile` token.** The dims say the shape (`level` or `layer`); the name says the quantity | a retrieved H2O profile is `water_vapor_mole_fraction_dry_air`, the same name a gridded 3-D field would take | a `_profile` token, which splits one quantity across two names |
| N3 | **Pressure** | a coordinate named `pressure` in the geolocation store, in the key's coordinate table, with no nomenclature row (as `time`, `lat`, `lon`). This settles the open question in STATE.md | a nomenclature row `pressure` |
| N4 | **Pressure units** | **`Pa`**: SI, like the lake's other units, and native in TROPOMI, SCIAMACHY and IASI (~99% of the volume). GOSAT, TES and TROPESS convert x 100 | `hPa` (native in GOSAT, TES, TROPESS) |
| N5 | **Vertical dims** | `level` and `layer` in every product. A layer lies between levels i and i+1. **This departs from the guide's "source name without a leading n"** (IASI `atmospheric_levels`, TES `Grid_Pressure_Composite`), so needs approval | keep source names: no common join name across products |
| N6 | **Matrix axes** | rows on `level`, columns on `level_2`. An attribute states that rows are the retrieved state and columns the true state, as the TES file says | `level_i` / `level_j` |
| N7 | **Vertical order** | **keep each source's order**, and record it in a `vertical_order` attribute (`surface_first` or `top_first`). No cross-product code can be layout-agnostic anyway (column kernels, log matrices, SVD), and the per-obs pressure grid is always needed | reverse three products to one order: exact, but a restructuring |
| N8 | **Log-space kernels** | `_log` after `averaging_kernel` (TES, TROPESS), because a linear kernel of the same parent is a different quantity (survey finding 3) | — |
| N9 | **Block splits** (TES) | `_cross_<species>` names the true-state species of an off-diagonal block. The diagonal blocks carry no suffix | — |
| N10 | **IASI SVD** | split per proxy state, as the guide's stacked-array rule requires: left and right vectors per proxy, shared singular values and rank. Pad `rank` to the record's maximum (13) with NaN; the rank store gives the valid count | store `musica_species_id` as a dim: breaks the stacked-array rule |
| N11 | **GOSAT `dry_column`** | **hold.** It is ~1/4 of the hydrostatic expectation (finding F2). It is not needed to apply the XH2O kernel; `pressure_weight` is | store it, units unresolved: not allowed by the guide |
| N12 | **Out of this pass** | error covariances (TES `ObservationErrorCovariance`, `*ErrorCovariance`; TROPESS `observation_error`, `observation_error_h2o`) and the IASI temperature cross-kernel (`musica_wvp_xavkat_*`). The grammar extends to them (`..._observation_error_covariance_log[_cross_<species>]`) when asked | name them now |

## 2. The grammar, applied

- **Quantity**: `water_vapor` (as in the 2026-10-14 rows), `dry_air`, `pressure_weight`.
- **Vertical form**: `column` (total or column-averaged), `partial_column` (per
  layer), or none (a value at a level or a layer mean).
- **Species or form**: `h2o` is implicit for mole fractions, as in the existing
  `water_vapor_column_mole_fraction_dry_air`. Otherwise `h2o`, `hdo`,
  `delta_d`, `hdo_h2o_ratio`, `proxy_humidity`, `proxy_delta_d`.
- **Basis**: `mole_fraction_dry_air`.
- **Role**: `apriori`, `averaging_kernel[_log][_cross_<species>]`,
  `averaging_kernel_svd_{left_vectors,right_vectors,singular_values,rank}`,
  `standard_error`.

The retrieved quantities the grammar implies are listed below. They get rows
when their readers are built, not now. They show that the pattern holds for the
profile products:

| implied name | products (source) |
| --- | --- |
| `water_vapor_mole_fraction_dry_air` | TES (`Species` H2O half), TROPESS (`x_h2o`), IASI (`musica_h2o`) |
| `water_vapor_hdo_mole_fraction_dry_air` | TES (`Species` HDO half) |
| `water_vapor_hdo_h2o_ratio` | TROPESS (`x`) |
| `water_vapor_delta_d` | IASI (`musica_deltad`) |
| `water_vapor_proxy_humidity`, `water_vapor_proxy_delta_d` | IASI (`musica_wvp`, split) |

## 3. Proposed rows for `nomenclature_data.md` (24)

| canonical_name | canonical_units | long_name |
| --- | --- | --- |
| `water_vapor_column_h2o_averaging_kernel` | unitless | column averaging kernel of the total column of water vapor (H2O), with respect to layer partial columns |
| `water_vapor_column_hdo_averaging_kernel` | unitless | column averaging kernel of the total column of HDO water vapor, with respect to layer partial columns |
| `water_vapor_column_mole_fraction_dry_air_averaging_kernel` | unitless | normalized column averaging kernel of the column-averaged dry-air mole fraction of water vapor, with respect to the layer dry-air mole fraction |
| `water_vapor_partial_column_h2o_apriori` | mol m-2 | a priori layer partial column of water vapor (H2O) |
| `water_vapor_partial_column_hdo_apriori` | mol m-2 | a priori layer partial column of HDO water vapor |
| `water_vapor_mole_fraction_dry_air_apriori` | 1e-6 | a priori dry-air mole fraction of water vapor (H2O) |
| `water_vapor_hdo_mole_fraction_dry_air_apriori` | 1e-6 | a priori dry-air mole fraction of HDO water vapor |
| `water_vapor_hdo_h2o_ratio_apriori` | unitless | a priori HDO/H2O mole ratio of water vapor |
| `water_vapor_delta_d_apriori` | 1e-3 | a priori delta D of water vapor |
| `water_vapor_proxy_humidity_apriori` | unitless | a priori humidity proxy state of water vapor, 0.5 (ln H2O + ln HDO) |
| `water_vapor_proxy_delta_d_apriori` | unitless | a priori delta D proxy state of water vapor, ln HDO - ln H2O |
| `water_vapor_hdo_h2o_ratio_averaging_kernel_log` | unitless | averaging kernel of the ln HDO/H2O mole ratio of water vapor, with respect to the true ln ratio |
| `water_vapor_mole_fraction_dry_air_averaging_kernel_log` | unitless | averaging kernel of the ln dry-air mole fraction of water vapor (H2O), with respect to the true ln H2O mole fraction |
| `water_vapor_mole_fraction_dry_air_averaging_kernel_log_cross_hdo` | unitless | averaging kernel of the ln dry-air mole fraction of water vapor (H2O), with respect to the true ln HDO mole fraction |
| `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log` | unitless | averaging kernel of the ln dry-air mole fraction of HDO water vapor, with respect to the true ln HDO mole fraction |
| `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log_cross_h2o` | unitless | averaging kernel of the ln dry-air mole fraction of HDO water vapor, with respect to the true ln H2O mole fraction |
| `water_vapor_proxy_humidity_averaging_kernel_svd_left_vectors` | unitless | left singular vectors of the water vapor proxy-state averaging kernel, humidity proxy rows |
| `water_vapor_proxy_delta_d_averaging_kernel_svd_left_vectors` | unitless | left singular vectors of the water vapor proxy-state averaging kernel, delta D proxy rows |
| `water_vapor_proxy_humidity_averaging_kernel_svd_right_vectors` | unitless | right singular vectors of the water vapor proxy-state averaging kernel, humidity proxy columns |
| `water_vapor_proxy_delta_d_averaging_kernel_svd_right_vectors` | unitless | right singular vectors of the water vapor proxy-state averaging kernel, delta D proxy columns |
| `water_vapor_proxy_averaging_kernel_svd_singular_values` | unitless | singular values of the water vapor proxy-state averaging kernel |
| `water_vapor_proxy_averaging_kernel_svd_rank` | unitless | rank of the truncated singular value decomposition of the water vapor proxy-state averaging kernel |
| `dry_air_partial_column` | mol m-2 | layer partial column of dry air |
| `pressure_weight_column_average` | unitless | layer pressure weight that forms a column average from a layer profile |

## 4. Per product and source

Units are after conversion. `(obs, level, level_2)` is a matrix (N6).

### TROPOMI (SRON, processor 8.1) and SCIAMACHY (SRON SICOR, same format)

`nlayer` 50 / 60, `nlevel` 51 / 61. Order **top_first** (level 0 is 0 Pa).

| source | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- |
| `target_product/h2o_column_averaging_kernel` | `water_vapor_column_h2o_averaging_kernel` | unitless | (obs, layer) | none |
| `target_product/hdo_column_averaging_kernel` | `water_vapor_column_hdo_averaging_kernel` | unitless | (obs, layer) | none |
| `target_product/h2o_profile_apriori` | `water_vapor_partial_column_h2o_apriori` | mol m-2 | (obs, layer) | x 1e4 / N_A from `molec. cm-2` |
| `target_product/hdo_profile_apriori` | `water_vapor_partial_column_hdo_apriori` | mol m-2 | (obs, layer) | x 1e4 / N_A |
| `meteo/dry_air_subcolumns` | `dry_air_partial_column` | mol m-2 | (obs, layer) | x 1e4 / N_A |
| `meteo/pressure_levels` | geolocation `pressure` | Pa | (obs, level) | none; layer interfaces |

TROPOMI: 5 new variable stores, and `pressure` added to the existing
geolocation store (as the corners were), on the same obs axis. ~29 TiB
estimated; compression is measured before any 2-D store (step 3).

### GOSAT and GOSAT-2 (IUP FOCAL v3.0.1)

`layer_dim` 5, `level_dim` 6. Order **surface_first** (file comment). All from
the H2O file; DED has no kernel or prior. The vertical fields are shared and
identical where both files hold a sounding (`docs/products/gosat.md`).

| source | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- |
| `xh2o_averaging_kernel` | `water_vapor_column_mole_fraction_dry_air_averaging_kernel` | unitless | (obs, layer) | none |
| `h2o_profile_apriori` | `water_vapor_mole_fraction_dry_air_apriori` | 1e-6 | (obs, layer) | none; layer means |
| `pressure_weight` | `pressure_weight_column_average` | unitless | (obs, layer) | none |
| `pressure_levels` | geolocation `pressure` | Pa | (obs, level) | x 100 from `hPa`; layer interfaces |
| `dry_column` | held (N11) | — | (obs, layer) | — |

`pressure_weight` is within 0.0026 of dp / p_surface but not equal, so it is
stored as published, not derived.

### TES (Aura L2 HDO Nadir Lite v006)

`Grid_Pressure_Composite` 34 = HDO levels 0-16 then H2O 17-33, on the same 17
pressures. Order **surface_first**. Each 34 x 34 matrix splits into four
17 x 17 blocks; rows are the retrieved state, columns the true state (the
file's own `AveragingKernel` description: "sensitivity of retrieved ln(vmr) to
the true ln(vmr)").

| source | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- |
| `ConstraintVector[0:17]` | `water_vapor_hdo_mole_fraction_dry_air_apriori` | 1e-6 | (obs, level) | x 1e6 from `mole/mole` |
| `ConstraintVector[17:34]` | `water_vapor_mole_fraction_dry_air_apriori` | 1e-6 | (obs, level) | x 1e6 |
| `AveragingKernel[0:17, 0:17]` | `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log` | unitless | (obs, level, level_2) | none |
| `AveragingKernel[0:17, 17:34]` | `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log_cross_h2o` | unitless | (obs, level, level_2) | none |
| `AveragingKernel[17:34, 0:17]` | `water_vapor_mole_fraction_dry_air_averaging_kernel_log_cross_hdo` | unitless | (obs, level, level_2) | none |
| `AveragingKernel[17:34, 17:34]` | `water_vapor_mole_fraction_dry_air_averaging_kernel_log` | unitless | (obs, level, level_2) | none |
| `Pressure[0:17]` | geolocation `pressure` | Pa | (obs, level) | x 100 from `hPa`; the build checks that both halves are equal on every obs |

No dry-air partial column is published (`AirDensity` is a number density on
levels; left out).

### AIRS and CrIS (TROPESS / MUSES)

`level` 17. Order **surface_first**. FS (Standard) only has the kernel and
prior; RS (Summary) has neither.

| source | streams | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- | --- |
| `observation_ops/xa` | FS | `water_vapor_hdo_h2o_ratio_apriori` | unitless | (obs, level) | none |
| `observation_ops/averaging_kernel` | FS | `water_vapor_hdo_h2o_ratio_averaging_kernel_log` | unitless | (obs, level, level_2) | none; "logarithmic_averaging_kernel_hdo_to_h2o_ratio" |
| `pressure` | FS, RS | geolocation `pressure` | Pa | (obs, level) | x 100 from `hPa` |

Confirm the row/column convention against the TROPESS user guide when the
reader is built.

### IASI (KIT MUSICA L2pp)

`atmospheric_levels` 29. Order **top_first**. The kernel is published as a
truncated SVD over the 2 x 29 proxy state (`musica_species_id`: humidity proxy
0.5 (ln H2O + ln HDO), then δD proxy ln HDO - ln H2O). Block (k, l) of the
kernel is `L_k diag(s) R_l^T`, so the split per proxy loses nothing.

| source | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- |
| `musica_h2o_apriori` | `water_vapor_mole_fraction_dry_air_apriori` | 1e-6 | (obs, level) | none (respell `ppmv`) |
| `musica_deltad_apriori` | `water_vapor_delta_d_apriori` | 1e-3 | (obs, level) | none |
| `musica_wvp_apriori[:, 0]` | `water_vapor_proxy_humidity_apriori` | unitless | (obs, level) | none; ln space, never scaled |
| `musica_wvp_apriori[:, 1]` | `water_vapor_proxy_delta_d_apriori` | unitless | (obs, level) | none; ln space |
| `musica_wvp_avk_lvec[:, 0]` | `water_vapor_proxy_humidity_averaging_kernel_svd_left_vectors` | unitless | (obs, rank, level) | none; rank padded (N10) |
| `musica_wvp_avk_lvec[:, 1]` | `water_vapor_proxy_delta_d_averaging_kernel_svd_left_vectors` | unitless | (obs, rank, level) | none |
| `musica_wvp_avk_rvec[:, 0]` | `water_vapor_proxy_humidity_averaging_kernel_svd_right_vectors` | unitless | (obs, rank, level) | none |
| `musica_wvp_avk_rvec[:, 1]` | `water_vapor_proxy_delta_d_averaging_kernel_svd_right_vectors` | unitless | (obs, rank, level) | none |
| `musica_wvp_avk_val` | `water_vapor_proxy_averaging_kernel_svd_singular_values` | unitless | (obs, rank) | none |
| `musica_wvp_avk_rank` | `water_vapor_proxy_averaging_kernel_svd_rank` | unitless | (obs) | none (int8) |
| `musica_pressure_levels` | geolocation `pressure` | Pa | (obs, level) | none; trailing NaN beyond `musica_nol` |

- The proxy priors are what the kernel applies to. The H2O and δD priors are
  the physical ones; the proxies follow from them only through ln and a
  reference ratio, so not exactly in float32. Both pairs are proposed; the
  physical pair could be dropped.
- **Size:** each SVD vector store is ~2.4 TB uncompressed (1.6e9 obs x 13 x
  29 x 4 B), ~9.7 TB for the four.

## 5. Findings from this pass (2026-10-19)

| # | finding | where recorded |
| --- | --- | --- |
| F1 | **Vertical order differs by product**: top first in TROPOMI, SCIAMACHY and IASI (level 0 at 0 Pa or 46 Pa); surface first in GOSAT, TES and TROPESS. | N7 |
| F2 | **GOSAT `dry_column` is ~1/4 of the hydrostatic dry column.** In molec cm-2, dp / (g M_dry) x N_A over each layer divided by `dry_column` gives p1 / p50 / p99 = 3.97 / 3.99-4.00 / 4.04 on 2011-01-15 and 2015-06-01 (2,984 soundings). The units say `no. of molecules`. | gosat.md G7 |
| F3 | **IASI `wv_avk_rank` varies by file**, 12 or 13 in seven files sampled 2014-2020. | iasi.md I6 |
| F4 | **IASI changes processor version and platforms in 2019**: `IASIAB_MUSICA_030201` through 2019, `IASIAB_MUSICA_030300` and `IASIABC_MUSICA_030300` from 2019 (MetOp-C joins). The store name carries one version. | iasi.md I7 |
| F5 | **TROPESS FS `pressure` level 0 is -999** on the targets sampled (one 2023 file). RS level 0 holds the surface pressure. | tropess.md R10 |
| F6 | **The TES kernel is in ln(vmr) space**, rows retrieved and columns true, per its own attribute. | N8, tes.md |

## 6. After agreement

1. Add the agreed rows to `nomenclature_data.md` (user review before commit).
2. Map them in each product's key as its reader is built. GOSAT first, then
   TROPOMI's model-comparison stores on the existing obs axis.
3. Before any 2-D store, measure kernel compression with a scratch script
   (login node). The chunk rule sizes 2-D arrays: 50 layers take 131,072 obs.
