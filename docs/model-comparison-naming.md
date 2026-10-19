# Model-comparison naming pass (TASKS.md task 7, step 1)

**Status: proposal, revised 2026-10-19 after the first review.** Review in
place with `#@CLAUDE` comments. Nothing here is in `nomenclature_data.md` yet.

Scope: every product's column averaging kernels, a priori profiles, dry-air
partial columns and pressure grid, named once across all products. Evidence:
header reads of one file per product on 2026-10-19 (plus the 2026-10-14
survey), and the checks under Findings.

## 1. Decisions

| # | decision | recommendation | status |
| --- | --- | --- | --- |
| N1 | **Name grammar** | `<quantity>[_<vertical form>]_<species or form>[_<basis>][_<role>]`. Roles are suffixes, as `_standard_error` already is. The species is always explicit (N13) | approved, pending the answers in section 2 |
| N2 | **No `profile` token** | the dims say the shape (`level` or `layer`); the name says the quantity. It causes no conflict in any product (2.1) | open |
| N3 | **Pressure** | a coordinate named `pressure` in the geolocation store, in the key's coordinate table, with no nomenclature row | **approved** |
| N4 | **Pressure units** | `Pa`; GOSAT, TES and TROPESS convert x 100 from `hPa` | **approved** |
| N5 | **Vertical dims** | `level` and `layer` in every product, mapped per sensor in 2.2. Departs from the guide's "source name without a leading n" | open |
| N6 | **Matrix axes** | rows on `level`, columns on `level_2` (2.3) | open |
| N7 | **Vertical order** | keep each source's order; record it in a `vertical_order` attribute | **approved** |
| N8 | **Log-space kernels** | `_log` after `averaging_kernel` | **approved** |
| N9 | **TES block splits** | the row species leads the name; `_cross_<species>` names the true-state species of an off-diagonal block (2.4) | open |
| N10 | **IASI SVD** | split the singular vectors per proxy state; pad `rank` to the record maximum with NaN (2.5) | open |
| N11 | **GOSAT `dry_column`** | hold until its unit is resolved (2.6) | open |
| N12 | **Out of this pass** | error covariances and the IASI temperature cross-kernel (2.7) | open |
| N13 | **Rename two existing rows** (new, from your comment on implicit `h2o`) | `water_vapor_column_mole_fraction_dry_air` and its `_standard_error` become `water_vapor_column_h2o_mole_fraction_dry_air[_standard_error]`. No store in the lake uses them yet (2.9) | open; changes a permanent identifier, so it needs your approval |

## 2. Answers to the first review

### 2.1 N2: does dropping `profile` cause a conflict anywhere?

**No.** A conflict needs one product publishing the same quantity at two
shapes with nothing else in the name to tell them apart. Every case found is
already told apart by the vertical-form token:

| product | the two variables | names |
| --- | --- | --- |
| SCIAMACHY | `h2o_column_apriori` (obs) and `h2o_profile_apriori` (obs, layer), both `molec. cm-2`; the same for HDO | `water_vapor_column_h2o_apriori` and `water_vapor_partial_column_h2o_apriori` |
| TES | `TotalColumnDensity` (obs) and the HDO half of `Species` (obs, level) | `water_vapor_column_hdo` and `water_vapor_hdo_mole_fraction_dry_air` |
| TROPESS RS | `x_h2o_col_p` (obs, 850-250 hPa average) and `x_h2o` (obs, level) | the first needs a range qualifier when its reader is built; the second is `water_vapor_h2o_mole_fraction_dry_air` |
| TROPESS RS | `dd_col_p` (850-250 hPa mean) and `dd_004` (δD at 4 per mil) | both scalars; both need qualifiers when the reader is built. No δD profile is published there |
| IASI | profiles only: no column quantity is published (full variable list read) | — |
| TROPOMI, GOSAT | no quantity appears at two shapes | — |

- **Across products**, one name does cover two representations. GOSAT's a
  priori mole fraction is a layer mean (obs, layer); TES's and IASI's are
  values at levels (obs, level). It is the same quantity, and the dim name
  says which. The `long_name` attribute states it.
- **The rule that keeps this true:** a quantity at one level or over one
  range (surface, 850-250 hPa) always carries a qualifier.

### 2.2 N5: what becomes `level` and what becomes `layer`

- **`level`**: a point in the vertical. It is where pressure is given, and in
  three products it is where the profile values are given.
- **`layer`**: the slab between levels i and i+1. Values on it are layer
  integrals or layer means. A product has layers only if it has N + 1
  levels for N layers.

| sensor | source dim (size) | becomes | what is on it |
| --- | --- | --- | --- |
| TROPOMI | `nlevel` (51) | `level` | `pressure` (layer interfaces) |
| | `nlayer` (50) | `layer` | kernels, a priori partial columns, dry-air partial column |
| SCIAMACHY | `nlevel` (61) | `level` | `pressure` (interfaces) |
| | `nlayer` (60) | `layer` | kernels, a priori partial columns, dry-air partial column |
| GOSAT, GOSAT-2 | `level_dim` (6) | `level` | `pressure` (layer boundaries, per the file) |
| | `layer_dim` (5) | `layer` | kernel, a priori (layer means), pressure weight |
| TES | `Grid_Pressure_Composite` (34), split into 2 x 17 | `level` (17) | `pressure`, a priori, the four kernel blocks; values at levels |
| TROPESS (AIRS, CrIS) | `level` (17) | `level` | `pressure`, a priori, kernel; values at levels |
| IASI | `atmospheric_levels` (29) | `level` | `pressure`, a priori, SVD vectors; values at levels. Trailing levels beyond `musica_nol` (18-29 per obs) are NaN |

- After the split, TES's 17 levels are the grid that the file's own
  `Grid_Pressure` (17) dim describes. TES also has a 67-level forward-model
  grid (`Grid_Pressure_FM`: `Altitude_FM`, `Pressure_FM`, `Map`). It is not in
  scope. If it is ever stored it needs its own dim name (e.g. `level_fm`).
- Only TROPOMI, SCIAMACHY and GOSAT have layers.
- GOSAT already maps `level_dim` to `level` and `layer_dim` to `layer` in its
  key. Strictly, that also departs from "source name without a leading n".

### 2.3 N6: the two matrix axes

An averaging kernel says how the retrieval responds to the true atmosphere.
For a profile retrieval:

```
x_retrieved[i] = x_apriori[i] + sum_j A[i, j] * (x_true[j] - x_apriori[j])
```

- **Rows, i (`level`)**: the retrieved level. Row i is how the retrieved
  value at level i depends on the true atmosphere at every level: the
  retrieval's vertical smoothing at that level.
- **Columns, j (`level_2`)**: the true-state level. Column j is how a change
  in the true atmosphere at level j spreads into every retrieved level.
- **Both axes are the same pressure grid**: `pressure[i]` and `pressure[j]`
  in the geolocation store.
- **Why two names:** a zarr or xarray array cannot have the dim `level`
  twice. The TROPESS files declare `(target, level, level)`, which xarray
  cannot represent, so one axis has to be renamed either way.
- **Why `level` for rows:** the result of applying a kernel is on the rows,
  so it joins `pressure` directly.
- **Applying it to a model profile `xm`** (on the product's levels, in the
  kernel's space; ln for the `_log` kernels):

  ```python
  xr_sim = xa + (A * (xm - xa).rename(level='level_2')).sum('level_2')
  ```

- **Why not `level_retrieved` / `level_true`:** the same two-axis convention
  should serve the covariances later (N12). A covariance is symmetric and
  has no retrieved/true sense. A neutral `level_2`, plus a `matrix_axes`
  attribute ("rows: retrieved state; columns: true state"), fits both.

### 2.4 N9: the TES block splits

- **What the blocks are.** TES retrieves ln HDO and ln H2O together. Its
  state vector has 34 entries: ln HDO at 17 levels, then ln H2O at the same
  17. Its 34 x 34 kernel therefore holds four 17 x 17 blocks:

  ```
  ln HDO_ret = ln HDO_ap + A_DD (ln HDO_true - ln HDO_ap) + A_DH (ln H2O_true - ln H2O_ap)
  ln H2O_ret = ln H2O_ap + A_HD (ln HDO_true - ln HDO_ap) + A_HH (ln H2O_true - ln H2O_ap)
  ```

  - `A_DD`: retrieved HDO with respect to true HDO.
  - `A_DH`: retrieved HDO with respect to true H2O (cross).
  - `A_HD`: retrieved H2O with respect to true HDO (cross).
  - `A_HH`: retrieved H2O with respect to true H2O.
- **Why split.** The guide requires it (stacked arrays, and matrices into
  blocks). After the split each block sits on the same `level` / `level_2`
  grid as every other product's kernel, rather than on a composite axis
  whose halves mean different species.
- **Why keep the cross blocks.** The guide requires that too, and the
  physics needs them. To simulate TES's HDO, and hence δD (ln HDO - ln H2O),
  from a model, both terms of each line are needed. Dropping `A_DH` and
  `A_HD` would bias simulated δD wherever HDO and H2O are correlated in the
  retrieval, which is everywhere.
- **Why this naming:**
  - **The row species leads.** A block is the kernel *of* a retrieved
    quantity, so it takes that quantity's name plus the role suffix, as
    every other kernel does (N1).
  - **The diagonal blocks take no suffix.** `A_HH` is the same quantity as
    a single-species H2O kernel would be, so it gets that name.
  - **`_cross_<species>` names the true-state species** of an off-diagonal
    block.
  - **The alternative**, suffixing every block (`_wrt_hdo`, `_wrt_h2o`), is
    symmetric. But the diagonals would then be named unlike every other
    product's kernels.

| block | name |
| --- | --- |
| `A_DD` | `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log` |
| `A_DH` | `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log_cross_h2o` |
| `A_HD` | `water_vapor_h2o_mole_fraction_dry_air_averaging_kernel_log_cross_hdo` |
| `A_HH` | `water_vapor_h2o_mole_fraction_dry_air_averaging_kernel_log` |

### 2.5 N10: the IASI SVD

- **What it is.** MUSICA retrieves water vapour in two "proxy" states per
  level, both in ln space:
  - the humidity proxy, 0.5 (ln H2O + ln HDO);
  - the δD proxy, ln HDO - ln H2O.

  The state vector is 2 x 29 = 58 entries, so each observation's kernel is a
  58 x 58 matrix in proxy space.
- **How it is published.** To save space, MUSICA does not store that matrix.
  It stores its truncated singular value decomposition,
  `A = L diag(s) R^T`:
  - `musica_wvp_avk_lvec`: L, the left vectors, (obs, proxy, rank, level);
  - `musica_wvp_avk_rvec`: R, the right vectors, the same shape;
  - `musica_wvp_avk_val`: s, the singular values, (obs, rank);
  - `musica_wvp_avk_rank`: the number of valid components per obs.
- **Why the components, not the matrix.** Rebuilding A would be a
  derivation, which the guide does not allow without approval. It would also
  be larger:

  | form | floats per obs | full record, uncompressed |
  | --- | --- | --- |
  | rebuilt 58 x 58 matrix | 3,364 | ~21.5 TB |
  | the published components, at rank 13 | 1,521 | ~9.7 TB |

- **Why split by proxy.**
  - L's rows are the 58 retrieved proxy values, which stack two
    quantities; R's rows likewise stack the two true-state quantities. That
    is the stacked-array case the guide names.
  - Splitting loses nothing. Block (k, l) of the kernel is
    `L_k diag(s) R_l^T`, where k is the retrieved proxy and l the true one.
  - The δD-proxy block that δD comparisons use needs only `L_δD`, s and
    `R_δD`: two of the four big stores.
  - s and the rank belong to the whole matrix, not to one proxy, so each is
    one store.
- **Why pad `rank`.**
  - Every store has one fixed size per secondary dim, but the files differ:
    `wv_avk_rank` is 12 or 13 (F3).
  - Inside a file, MUSICA already pads. In the 2016-06-15 morning file
    (dim 12), the first 200,000 obs have per-obs ranks of 5 to 12, and every
    component past an obs's own rank is NaN.
  - Padding a 12-file to 13 adds one more all-NaN component: the source's
    own convention, which costs almost nothing compressed. It is recorded in
    the metadata.
  - The record maximum must be found from the headers before building.
- **Alternatives:**
  - keep `proxy` as a dim: 4 stores instead of 6, but it breaks the
    stacked-array rule;
  - rebuild the matrix: a derivation, and 2.2 times larger.

### 2.6 N11: GOSAT `dry_column`

- **What it is.** The number of dry-air molecules in each of GOSAT's 5
  layers, per unit area: a dry-air partial column, the same quantity as
  TROPOMI's `dry_air_subcolumns`.
- **What it is for.** It converts between layer mole fractions and layer
  partial columns, and so would let a user form XH2O from a model profile as
  `sum(x_j * dry_j) / sum(dry_j)`.
- **Why GOSAT's kernel does not need it.** FOCAL's own operator uses the
  pressure weights:

  ```
  XH2O_sim = sum_j w_j * (xa_j + a_j * (x_model_j - xa_j))
  ```

  These are `pressure_weight`, `xh2o_averaging_kernel` and
  `h2o_profile_apriori`, all proposed for storing.
- **Why hold it.**
  - Its unit, `no. of molecules`, has no area.
  - Its values are consistently ~1/4 of the hydrostatic dry column in
    molec cm-2 (F2; ratio p1-p99 3.97-4.04). A factor of 4 matches no area
    conversion (cm² to m² is 1e4).
  - The guide lets a wrong source unit be corrected only when the correct
    unit is demonstrated. Here it is shown to be wrong, but not what is
    right, so there is no exact canonical conversion to apply.
- **What holding costs:** nothing permanent.
  - It can be added later as a new store on the same obs axis.
  - In the meantime the stored `pressure` gives the hydrostatic dry column
    to within the usual small corrections.
- **To resolve it:** read the ESA GHG-CCI Product Specification Document
  v3, which the file cites, or ask IUP Bremen.

### 2.7 N12: what is left out of this pass

- **Error covariance matrices** give a retrieval's uncertainty, including
  how errors at different levels are correlated:
  - TES `ObservationErrorCovariance` (measurement + systematic +
    cross-state; the file says it is "for comparisons with other
    measurements and for assimilation"), `MeasurementErrorCovariance` and
    `TotalErrorCovariance` (adds smoothing error). All are 34 x 34 in
    ln(vmr)^2, so each splits into 4 blocks: 12 stores, ~40 GB uncompressed
    in all.
  - TROPESS FS `observation_error` (17 x 17, HDO/H2O ratio) and
    `observation_error_h2o` (17, a ln-space relative H2O error).
    ~50-80 GB uncompressed.
- **The IASI temperature cross-kernel** (`musica_wvp_xavkat_*`, also an SVD)
  is the sensitivity of the retrieved proxies to the true temperature
  profile. It is used to estimate how temperature errors leak into
  humidity and δD. ~4.5 TB uncompressed.
- **Why defer them.**
  - Task 7 as written covers kernels, priors, dry-air columns and pressure.
  - These are not needed for the main model-comparison step, applying the
    kernel to a model profile. They are needed for error-weighted
    comparisons and assimilation.
  - No build waits on them: GOSAT has none.
  - The grammar already fixes their pattern, so deferring cannot lock in a
    one-product name:
    `<quantity>_observation_error_covariance_log[_cross_<species>]`.
- **The cost of naming them now:** ~18 more rows. The TES and TROPESS ones
  are cheap to build. Ask, and they join this pass.

### 2.8 Where `partial_column` is used

Only in the SRON products, plus GOSAT's held `dry_column`:

| product | source | name |
| --- | --- | --- |
| TROPOMI, SCIAMACHY | `target_product/h2o_profile_apriori` | `water_vapor_partial_column_h2o_apriori` |
| TROPOMI, SCIAMACHY | `target_product/hdo_profile_apriori` | `water_vapor_partial_column_hdo_apriori` |
| TROPOMI, SCIAMACHY | `meteo/dry_air_subcolumns` | `dry_air_partial_column` |
| GOSAT, GOSAT-2 | `dry_column` | `dry_air_partial_column`, if N11 resolves |

- SRON calls the priors "profile" (`h2o_profile_apriori`). Their own
  `long_name` is "A-priori vertically integrated partial column of water in
  layers", and the values are molec cm-2 per layer.
- **The token is needed** because a partial column and a total column share
  `mol m-2`. SCIAMACHY publishes both (2.1). Without it, the layer prior
  would read as an a priori total column.
- TES, TROPESS and IASI publish no partial columns.

### 2.9 Explicit `h2o` (N13)

- **Agreed:** the species is always explicit. Every new name carries `h2o`
  (or `hdo`, `delta_d`, `hdo_h2o_ratio`, a proxy). The revised names are in
  sections 3 and 4.
- **The only implicit cases left are two existing rows:**
  `water_vapor_column_mole_fraction_dry_air` and
  `water_vapor_column_mole_fraction_dry_air_standard_error` (style_guides
  `3966e69`).
- **Recommendation: rename them now** to
  `water_vapor_column_h2o_mole_fraction_dry_air[_standard_error]`.
  - Canonical names are meant to be permanent, but nothing in the lake
    uses these yet. Only TROPOMI stores exist, and they do not include
    them. GLEAM and MSWEP do not use them.
  - Their only users are the GOSAT key and the two GOSAT configs (fixture
    and production), and the GOSAT fixture stores on scratch, which are
    rebuilt anyway.
  - Before GOSAT production is the last cheap moment.
- **If you decline**, the GOSAT kernel's name (`water_vapor_column_h2o_mole_fraction_dry_air_averaging_kernel`)
  no longer matches its parent's.

## 3. The grammar, applied

- **Quantity**: `water_vapor` (as in the 2026-10-14 rows), `dry_air`,
  `pressure_weight`.
- **Vertical form**: `column` (total or column-averaged), `partial_column`
  (per layer, 2.8), or none (a value at a level, or a layer mean).
- **Species or form**, always explicit: `h2o`, `hdo`, `delta_d`,
  `hdo_h2o_ratio`, `proxy_humidity`, `proxy_delta_d`. `dry_air` is its own
  quantity.
- **Basis**: `mole_fraction_dry_air`.
- **Role**: `apriori`, `averaging_kernel[_log][_cross_<species>]`,
  `averaging_kernel_svd_{left_vectors,right_vectors,singular_values,rank}`,
  `standard_error`.

The retrieved quantities the grammar implies get rows when their readers are
built, not now. They show that the pattern holds for the profile products:

| implied name | products (source) |
| --- | --- |
| `water_vapor_h2o_mole_fraction_dry_air` | TES (`Species` H2O half), TROPESS (`x_h2o`), IASI (`musica_h2o`) |
| `water_vapor_hdo_mole_fraction_dry_air` | TES (`Species` HDO half) |
| `water_vapor_hdo_h2o_ratio` | TROPESS (`x`) |
| `water_vapor_delta_d` | IASI (`musica_deltad`) |
| `water_vapor_proxy_humidity`, `water_vapor_proxy_delta_d` | IASI (`musica_wvp`, split) |

## 4. Proposed rows for `nomenclature_data.md` (24 new, 2 renamed)

| canonical_name | canonical_units | long_name |
| --- | --- | --- |
| `water_vapor_column_h2o_averaging_kernel` | unitless | column averaging kernel of the total column of water vapor (H2O), with respect to layer partial columns |
| `water_vapor_column_hdo_averaging_kernel` | unitless | column averaging kernel of the total column of HDO water vapor, with respect to layer partial columns |
| `water_vapor_column_h2o_mole_fraction_dry_air_averaging_kernel` | unitless | normalized column averaging kernel of the column-averaged dry-air mole fraction of water vapor (H2O), with respect to the layer dry-air mole fraction |
| `water_vapor_partial_column_h2o_apriori` | mol m-2 | a priori layer partial column of water vapor (H2O) |
| `water_vapor_partial_column_hdo_apriori` | mol m-2 | a priori layer partial column of HDO water vapor |
| `water_vapor_h2o_mole_fraction_dry_air_apriori` | 1e-6 | a priori dry-air mole fraction of water vapor (H2O) |
| `water_vapor_hdo_mole_fraction_dry_air_apriori` | 1e-6 | a priori dry-air mole fraction of HDO water vapor |
| `water_vapor_hdo_h2o_ratio_apriori` | unitless | a priori HDO/H2O mole ratio of water vapor |
| `water_vapor_delta_d_apriori` | 1e-3 | a priori delta D of water vapor |
| `water_vapor_proxy_humidity_apriori` | unitless | a priori humidity proxy state of water vapor, 0.5 (ln H2O + ln HDO) |
| `water_vapor_proxy_delta_d_apriori` | unitless | a priori delta D proxy state of water vapor, ln HDO - ln H2O |
| `water_vapor_hdo_h2o_ratio_averaging_kernel_log` | unitless | averaging kernel of the ln HDO/H2O mole ratio of water vapor, with respect to the true ln ratio |
| `water_vapor_h2o_mole_fraction_dry_air_averaging_kernel_log` | unitless | averaging kernel of the ln dry-air mole fraction of water vapor (H2O), with respect to the true ln H2O mole fraction |
| `water_vapor_h2o_mole_fraction_dry_air_averaging_kernel_log_cross_hdo` | unitless | averaging kernel of the ln dry-air mole fraction of water vapor (H2O), with respect to the true ln HDO mole fraction |
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

Renamed (N13):

| current canonical_name | new canonical_name | long_name |
| --- | --- | --- |
| `water_vapor_column_mole_fraction_dry_air` | `water_vapor_column_h2o_mole_fraction_dry_air` | column-averaged dry-air mole fraction of water vapor (H2O) |
| `water_vapor_column_mole_fraction_dry_air_standard_error` | `water_vapor_column_h2o_mole_fraction_dry_air_standard_error` | standard error of the column-averaged dry-air mole fraction of water vapor (H2O) |

## 5. Per product and source

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

- **TROPOMI:** 5 new variable stores, plus `pressure` added to the existing
  geolocation store (as the corners were), on the same obs axis.
  - ~29 TiB estimated.
  - Compression is measured before any 2-D store (step 3).
- **SCIAMACHY** also publishes total-column priors (`h2o_column_apriori`,
  `hdo_column_apriori`). They are not in this pass; they would be
  `water_vapor_column_{h2o,hdo}_apriori`.

### GOSAT and GOSAT-2 (IUP FOCAL v3.0.1)

`layer_dim` 5, `level_dim` 6. Order **surface_first** (file comment). All from
the H2O file; DED has no kernel or prior. The vertical fields are shared and
identical where both files hold a sounding (`docs/products/gosat.md`).

| source | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- |
| `xh2o_averaging_kernel` | `water_vapor_column_h2o_mole_fraction_dry_air_averaging_kernel` | unitless | (obs, layer) | none |
| `h2o_profile_apriori` | `water_vapor_h2o_mole_fraction_dry_air_apriori` | 1e-6 | (obs, layer) | none; layer means |
| `pressure_weight` | `pressure_weight_column_average` | unitless | (obs, layer) | none |
| `pressure_levels` | geolocation `pressure` | Pa | (obs, level) | x 100 from `hPa`; layer boundaries |
| `dry_column` | held (N11) | — | (obs, layer) | — |

`pressure_weight` is within 0.0026 of dp / p_surface, but not equal. So it is
stored as published, not derived.

### TES (Aura L2 HDO Nadir Lite v006)

`Grid_Pressure_Composite` 34 = HDO levels 0-16, then H2O 17-33, on the same
17 pressures. Order **surface_first**. Each 34 x 34 matrix splits into four
17 x 17 blocks (2.4). Rows are the retrieved state and columns the true state,
per the file's own `AveragingKernel` description: "sensitivity of retrieved
ln(vmr) to the true ln(vmr)".

| source | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- |
| `ConstraintVector[0:17]` | `water_vapor_hdo_mole_fraction_dry_air_apriori` | 1e-6 | (obs, level) | x 1e6 from `mole/mole` |
| `ConstraintVector[17:34]` | `water_vapor_h2o_mole_fraction_dry_air_apriori` | 1e-6 | (obs, level) | x 1e6 |
| `AveragingKernel[0:17, 0:17]` | `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log` | unitless | (obs, level, level_2) | none |
| `AveragingKernel[0:17, 17:34]` | `water_vapor_hdo_mole_fraction_dry_air_averaging_kernel_log_cross_h2o` | unitless | (obs, level, level_2) | none |
| `AveragingKernel[17:34, 0:17]` | `water_vapor_h2o_mole_fraction_dry_air_averaging_kernel_log_cross_hdo` | unitless | (obs, level, level_2) | none |
| `AveragingKernel[17:34, 17:34]` | `water_vapor_h2o_mole_fraction_dry_air_averaging_kernel_log` | unitless | (obs, level, level_2) | none |
| `Pressure[0:17]` | geolocation `pressure` | Pa | (obs, level) | x 100 from `hPa`; the build checks that both halves are equal on every obs |

No dry-air partial column is published. `AirDensity` is a number density on
levels, so it is left out.

### AIRS and CrIS (TROPESS / MUSES)

`level` 17. Order **surface_first**. Only FS (Standard) has the kernel and
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
truncated SVD over the 2 x 29 proxy state (2.5).

| source | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- |
| `musica_h2o_apriori` | `water_vapor_h2o_mole_fraction_dry_air_apriori` | 1e-6 | (obs, level) | none (respell `ppmv`) |
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

- **Proxy priors versus physical priors.**
  - The proxy priors are what the kernel applies to.
  - The H2O and δD priors are the physical ones. The proxies follow from
    them only through ln and a reference ratio, so not exactly in float32.
  - Both pairs are proposed; the physical pair could be dropped.
- **Size:** each SVD vector store is ~2.4 TB uncompressed (1.6e9 obs x 13 x
  29 x 4 B), ~9.7 TB for the four.

## 6. Findings from this pass (2026-10-19)

| # | finding | where recorded |
| --- | --- | --- |
| F1 | **Vertical order differs by product.** Top first in TROPOMI, SCIAMACHY and IASI (level 0 at 0 Pa or 46 Pa); surface first in GOSAT, TES and TROPESS. | N7 |
| F2 | **GOSAT `dry_column` is ~1/4 of the hydrostatic dry column.** In molec cm-2, dp / (g M_dry) x N_A per layer, divided by `dry_column`, gives p1 / p50 / p99 = 3.97 / 3.99-4.00 / 4.04. Two days, 2011-01-15 and 2015-06-01 (2,984 soundings). The units say `no. of molecules`. | gosat.md G7 |
| F3 | **IASI `wv_avk_rank` varies by file**: 12 or 13 in seven files sampled 2014-2020. Within a file, components past each obs's own rank (5-12 in one file) are NaN. | iasi.md I6 |
| F4 | **IASI changes processor version and platforms in 2019.** `IASIAB_MUSICA_030201` runs through 2019; `IASIAB_MUSICA_030300` and `IASIABC_MUSICA_030300` start in 2019 (MetOp-C joins). The store name carries one version. | iasi.md I7 |
| F5 | **TROPESS FS `pressure` level 0 is -999** on the targets sampled (one 2023 file). RS level 0 holds the surface pressure. | tropess.md R10 |
| F6 | **The TES kernel is in ln(vmr) space**, rows retrieved and columns true, per its own attribute. | N8, tes.md |

## 7. After agreement

1. Add the agreed rows to `nomenclature_data.md`, and make the N13 renames if
   approved (user review before commit).
2. Map them in each product's key as its reader is built. GOSAT first (with
   the N13 renames in its key and configs), then TROPOMI's model-comparison
   stores on the existing obs axis.
3. Before any 2-D store, measure kernel compression with a scratch script
   (login node). The chunk rule sizes 2-D arrays: 50 layers take 131,072 obs.
