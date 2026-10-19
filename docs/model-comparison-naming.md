# Model-comparison naming pass (TASKS.md task 7, step 1)

**Status: proposal, revised 2026-10-19 after the second review.** Review in
place with `#@CLAUDE` comments.
- N13 is applied, uncommitted: the two renamed rows in `nomenclature_data.md`,
  plus the GOSAT key and configs. The fixture test passes 46 cases.
- None of the new rows is in `nomenclature_data.md` yet.

Scope: every product's column averaging kernels, a priori profiles, dry-air
partial columns and pressure grid, named once across all products. Evidence:
header reads of one file per product on 2026-10-19 (plus the 2026-10-14
survey), and the checks under Findings.

## 1. Decisions

| # | decision | recommendation | status |
| --- | --- | --- | --- |
| N1 | **Name grammar** | `<quantity>[_<vertical form>]_<species or form>[_<basis>][_<role>]`. Roles are suffixes, as `_standard_error` already is. The species is always explicit (N13) | approved, pending the answers in section 2 |
| N2 | **No `profile` token** | the dims say the shape (`level` or `layer`); the name says the quantity. It causes no conflict in any product (2.1) | **approved** |
| N3 | **Pressure** | a coordinate named `pressure` in the geolocation store, in the key's coordinate table, with no nomenclature row | **approved** |
| N4 | **Pressure units** | `Pa`; GOSAT, TES and TROPESS convert x 100 from `hPa` | **approved** |
| N5 | **Vertical dims** | `level` and `layer` in every product, mapped per sensor in 2.2. Departs from the guide's "source name without a leading n" | **approved** |
| N6 | **Matrix axes** | rows on `level`, columns on `level_2` (2.3) | **approved** |
| N7 | **Vertical order** | keep each source's order; record it in a `vertical_order` attribute | **approved** |
| N8 | **Log-space kernels** | `_log` after `averaging_kernel` | **approved** |
| N9 | **TES block splits** | the row species leads the name; `_cross_<species>` names the true-state species of an off-diagonal block (2.4) | **approved** |
| N10 | **IASI SVD** | split the singular vectors per proxy state; pad `rank` to the record maximum with NaN (2.5). **Revised: one store per SVD kernel**, holding its components as arrays (2.10) | split and padding approved; one store per kernel open (needs a style-guide amendment) |
| N11 | **GOSAT `dry_column`** | hold until its unit is resolved (2.6). Noted for later in STATE.md and `gosat.md` G7 | **approved** (held) |
| N12 | **Error covariances and the IASI temperature cross-kernel** | added to this pass (2.7): 19 more rows | **approved** |
| N13 | **Rename two existing rows** | `water_vapor_column_mole_fraction_dry_air[_standard_error]` become `water_vapor_column_h2o_mole_fraction_dry_air[_standard_error]` (2.9) | **approved; applied**, uncommitted for your review |
| N14 | **Error role names** (new, from N12) | `<type>_error_covariance` for the three TES matrices (`observation`, `measurement`, `total`: established terms, kept whole), and `observation_standard_error` for a 1-sigma observation error, after the existing `_standard_error` (2.7) | **approved** |
| N15 | **TES covariance cross blocks** (new) | store both, though `S_HD` is exactly `S_DH` transposed (F8): ~3.4 GB each, the guide's rule as written, and the same four-block set as the kernel (2.7) | **approved** |
| N16 | **TROPESS `observation_error` is not a valid covariance** (new, F7) | **revised: leave it out**, and add no row for it. It has negative variances in every processor version sampled, at the levels the retrieval is sensitive to. Revisit if TROPESS documents or fixes it (2.11) | open |
| N17 | **IASI cross-kernel units** (new, F9) | the singular values take `K-1`, a corrected source unit (the files say `1`), with no value change. The vectors stay `unitless` (2.12) | open |

## 2. Answers to the reviews

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
- **Separate stores (your question).** Every component is its own store,
  since the guide puts one variable in each store; only the geolocation store
  holds several arrays.
  - The kernel is six stores: two left-vector stores, two right-vector
    stores, the singular values and the rank.
  - They share the obs axis and granule index like every other store, so a
    user opens the six together.
  - The temperature cross-kernel adds five more (2.7).

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

### 2.7 N12: error covariances and the IASI temperature cross-kernel (added)

An error covariance gives a retrieval's uncertainty, including how errors at
different levels correlate. They are used for error-weighted comparisons and
assimilation. The temperature cross-kernel gives how errors in the true
temperature leak into the retrieved humidity and δD. 19 rows, in 4 and 5.

**Role names (N14).**
- The three TES matrices are named by their own error budget, as
  `<row parent>_<type>_error_covariance_log[_cross_<species>]`:
  - `observation`: measurement + systematic + cross-state. The file says
    it is "for comparisons with other measurements and for assimilation".
  - `measurement`: "propagated measured radiance noise".
  - `total`: smoothing + systematic + measurement.

  These are established terms, so they stay whole.
- A 1-sigma observation error is `<parent>_observation_standard_error_log`,
  after the existing `_standard_error` role.
- The alternative order, `_standard_error_observation`, would put the
  qualifier after the role. Here that splits the established term
  "observation error".

**TES: 12 stores.** Three matrices x four blocks, on the `level` / `level_2`
grid of the kernel.
- `MeasurementErrorCovariance` and `TotalErrorCovariance` say
  `ln(vmr)^2`, which is dimensionless (`unitless`).
- `ObservationErrorCovariance` has no `Units` attribute. Declare it as
  `ln(vmr)^2`, from its siblings and its description, and record that in the
  key.
- **Cross blocks (N15).** `S_DH[i, j]` is the covariance of ln HDO at
  level i with ln H2O at level j. `S_HD` is exactly `S_DH` transposed (F8).
  - Storing both costs ~3.4 GB uncompressed each.
  - It follows the guide's rule as written.
  - It gives the same four-block set as the kernel, so a user never has to
    transpose.
  - Dropping one is the alternative. It is exact, but the user would have to
    know which block to transpose.
- ~40 GB uncompressed for the 12.

**TROPESS FS: 2 stores.**
- **`observation_error` (17 x 17)** becomes
  `water_vapor_hdo_h2o_ratio_observation_error_covariance_log`.
  - Its own `source` attribute says it is derived from the MUSES
    observation error covariance blocks as
    `obs_dd + obs_hh - obs_hd - obs_dh`: the covariance of
    ln HDO - ln H2O.
  - Built that way it must be symmetric with a non-negative diagonal. **It
    is neither** (F7).
  - **N16:** store it as published (the guide keeps data as published and
    records issues). State the defect in its metadata and in `tropess.md`
    R11.
  - Re-check every processor version (R1p11-R1p20) when the reader is built.
    If all have it, decide then whether to keep it.
  - ~47 GB (AIRS FS) + ~35 GB (CrIS-JPSS1) uncompressed.
- **`observation_error_h2o` (17)** becomes
  `water_vapor_h2o_mole_fraction_dry_air_observation_standard_error_log`.
  - It is 1-sigma in ln space, inferred rather than stated: p50 0.093,
    against p50 0.089 for the square root of TES's H2O observation-error
    variance.
  - Confirm against the TROPESS user guide. Never scaled (project rule).

**IASI: 5 stores.**
- The cross-kernel is published as an SVD, like the main kernel:
  `A_xT[k] = L_k diag(s) R^T`.
  - Its rows are the 58 retrieved proxy values, k being the proxy.
  - Its columns are 29 levels of the true air temperature, a single
    quantity. So L splits per proxy and R does not: R has no proxy dim in
    the file.
- `_cross_<quantity>` names the true-state quantity, as `_cross_<species>`
  does for TES; here it is `air_temperature`:

| source | name |
| --- | --- |
| `musica_wvp_xavkat_lvec[:, 0]` | `water_vapor_proxy_humidity_averaging_kernel_cross_air_temperature_svd_left_vectors` |
| `musica_wvp_xavkat_lvec[:, 1]` | `water_vapor_proxy_delta_d_averaging_kernel_cross_air_temperature_svd_left_vectors` |
| `musica_wvp_xavkat_rvec` | `water_vapor_proxy_averaging_kernel_cross_air_temperature_svd_right_vectors` |
| `musica_wvp_xavkat_val` | `water_vapor_proxy_averaging_kernel_cross_air_temperature_svd_singular_values` |
| `musica_wvp_xavkat_rank` | `water_vapor_proxy_averaging_kernel_cross_air_temperature_svd_rank` |

- **Units (N17).**
  - The files say `1` for every component. But the description says the
    kernel is of "natural logarithms of mixing ratios in ppmv with respect to
    atmospheric temperature in K", so the kernel is in K-1.
  - The vectors are orthonormal (F9), so they are unitless, and the singular
    values carry the K-1.
  - That is a demonstrably wrong source unit, corrected with its evidence
    recorded, as the guide allows. No value changes.
  - The main kernel's singular values stay `unitless` (ln over ln).
- **Rank dim:** `wv_xavkat_rank` (8 in the file read) becomes
  `rank_temperature`. That way the two SVDs never share a dim name with two
  sizes. It is padded as in N10.
- ~4.5 TB uncompressed (1.6e9 obs x (2 x 8 x 29 + 8 x 29) x 4 B).

**Not added:** IASI's `musica_h2o_error`, `musica_deltad_error` and
`musica_wvp_error` are 1-sigma retrieval errors, not covariances. They are
named with the retrieved quantities when the IASI reader is built (e.g.
`water_vapor_h2o_mole_fraction_dry_air_standard_error`).

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
- **Applied 2026-10-19** (approved), uncommitted for your review:
  - the two rows in `nomenclature_data.md`, whose long names now end
    "(H2O)" like `water_vapor_column_h2o`;
  - `nomenclature-key_gosat.md`, whose long names said "(XH2O)" and now
    match the rows;
  - `config/gosat/config_zarr.yaml` and `config_zarr_fixture.yaml`.

  No code names them. The fixture test passes 46 cases over both products.

### 2.10 N10, third review: one store per SVD kernel

**Are the components always opened together?** Yes. No component is useful
alone:
- Any block of the kernel, `A_kl = L_k diag(s) R_l^T`, needs a left-vector
  array, the singular values and a right-vector array. The δD-proxy block,
  the one δD comparisons use, needs `L_δD`, s and `R_δD`.
- The vectors carry NaN past each obs's rank, so the rank is needed to slice
  them (or the NaN must be zeroed).
- The singular values alone are at most a diagnostic. The vectors alone mean
  nothing.

That separates them from the TES blocks, each of which is a usable kernel by
itself (e.g. H2O-H2O for H2O comparisons). So the TES blocks stay separate
stores.

**A clean single-store layout.** It follows the pattern the geolocation store
already uses, one store holding several arrays on the same `obs` axis and
granule index:

```
wisosat.iasi.<version>.inst.native_swath.water_vapor_proxy_averaging_kernel_svd.zarr
  water_vapor_proxy_humidity_averaging_kernel_svd_left_vectors   (obs, rank, level)
  water_vapor_proxy_delta_d_averaging_kernel_svd_left_vectors    (obs, rank, level)
  water_vapor_proxy_humidity_averaging_kernel_svd_right_vectors  (obs, rank, level)
  water_vapor_proxy_delta_d_averaging_kernel_svd_right_vectors   (obs, rank, level)
  water_vapor_proxy_averaging_kernel_svd_singular_values         (obs, rank)
  water_vapor_proxy_averaging_kernel_svd_rank                    (obs)

wisosat.iasi.<version>.inst.native_swath.water_vapor_proxy_averaging_kernel_cross_air_temperature_svd.zarr
  (the five temperature cross-kernel arrays, on rank_temperature)
```

- **The arrays keep their canonical names and rows**, unchanged. Only the
  store name is new, the factorization's name.
- **The proxy split stays**, as the stacked-array rule requires. Keeping a
  `proxy` dim inside the store instead (4 arrays, not 6) would need a second
  exception.
- **Chunks:** each array is chunked by the existing rule, halving
  `chunks.obs` per array until it fits 40 MiB. Boundaries stay aligned across
  arrays, as they are between `time` and the corners in the geolocation
  store.
- **Gains:**
  - one store to open per kernel;
  - one icechunk commit covers every component, so the components can never
    be at different granules;
  - 2 stores instead of 11.
- **Costs:**
  - **A style-guide amendment.** The guide says "one store per data
    variable", and the geolocation store is its only multi-array store. The
    proposed wording: "a matrix published as a factorization (e.g. a
    truncated SVD) is one store, named for the factorization, holding its
    components as arrays, each with its own canonical name." The edit is
    shown to you before commit.
  - **A store-name rule.** The variable slot holds the factorization's name,
    which gets its own row in `nomenclature_data.md` (2 more rows).
    `geolocation` is the precedent for a store name that no single array
    takes.
  - **A shared-code change.** Today every variable store has one source; a
    store with several sources is new outside geolocation. The build,
    verifier and config gain it, and every product's fixture tests it.
- **Recommendation: adopt it**, for these two IASI kernels only.

### 2.11 N16, third review: the TROPESS ratio covariance

**What it is meant to be.**
- MUSES retrieves ln HDO and ln H2O together, as TES does. Its observation
  error covariance has the same four blocks: `S_dd`, `S_hh`, `S_hd`, `S_dh`.
- TROPESS publishes the ratio's covariance instead, and its `source`
  attribute gives the formula: `obs_dd + obs_hh - obs_hd - obs_dh`. That is
  the covariance of ln HDO - ln H2O = ln(HDO/H2O), the quantity the FS kernel
  and prior describe.
- Users would apply it to weight model-minus-retrieval differences, or in
  assimilation.

**Why what is published cannot be that.** Any covariance has two properties:
- **Symmetry.** cov(i, j) = cov(j, i). The formula keeps it, since
  `S_dh = S_hd^T`.
- **Non-negative variances.** The diagonal is var(ln HDO_i - ln H2O_i), a
  variance, which cannot be below zero. A transposed or swapped block cannot
  make it negative either: `S_hd` and `S_dh` share their diagonal.

What the files hold, in three versions:

| file | targets | symmetric? | targets with a negative variance, 750 / 681 / 619 hPa |
| --- | --- | --- | --- |
| AIRS FS 2021-02-10, R1p11 F0p1 | 21,129 | yes (to 7e-9) | 22% / 20% / 20%, and 99-100% above 180 hPa |
| CrIS-JPSS1 FS 2022-07-10, R1p17 F0p4 | 25,335 | **no**: median asymmetry 1.6x the median variance | 30% / 28% / 18% |
| AIRS FS 2023-06-15, R1p20 F0p6 | 29,650 | **no**: median asymmetry 1.0x the median variance | 31% / 28% / 16% |

- The negative variances sit where the retrieval is sensitive. The
  kernel's diagonal peaks at 511 hPa in all three files, and is largest from
  750 to 420 hPa.
- So the defect cannot be avoided by using only some levels.
- The asymmetry appears in versions after R1p11. The negative variances are
  in every version.
- No legitimate matrix form matches: a factor of a covariance (e.g.
  Cholesky) would have a positive diagonal.

**Options.**
- **Leave it out (recommended).**
  - Variable selection is ours to make; the guide forbids dropping
    observations, not variables. The TROPOMI subset already leaves out 50.
  - A matrix that is wrong at every level and in every version, in a way
    users cannot repair, adds risk and no value.
  - It saves ~80 GB.
  - Its row is not added. The name stays reserved in this document, and the
    defect is recorded in `tropess.md` R11.
  - Revisit if TROPESS documents or fixes it. Reporting it to the TROPESS
    team is worth doing; the evidence is in the table above.
- **Store it as published**, with the defect in its metadata: the guide's
  default for a flawed variable. A user who misses the warning gets negative
  error weights.
- Masking the bad values is not an option: it would alter the data.

`observation_error_h2o` is unaffected. Its values are positive throughout
(p10 0.024), so it stays in.

### 2.12 N17, third review: the IASI cross-kernel units

**What it is.** The temperature cross-kernel says how the retrieved water
vapour proxies respond to an error in the true temperature profile:

```
delta proxy_retrieved[i] = sum_j A_xT[i, j] * delta T_true[j]
```

- The proxies are natural logs of mixing ratios: dimensionless.
- T is in K.
- So `A_xT` must be in **K-1**: a change in ln mixing ratio per kelvin.

The file's own description says the same: "natural logarithms of mixing
ratios in ppmv ... with respect to atmospheric temperature in K".

**Which component carries the K-1.** The file stores `A_xT = L diag(s) R^T`
and labels all four components `1`. Only one of them can carry the unit:
- **L and R are orthonormal**: `L^T L = I` and `R^T R = I`, exact to 4
  decimals on the obs checked (F9). An identity matrix is dimensionless, so
  L and R are dimensionless.
- **So s carries all of it: K-1.** The rank is a count.
- For the main kernel, ln over ln, s is dimensionless, and `unitless` is
  right.

**Plausibility.** The largest singular value on the obs checked is
0.198 K-1. A 1 K temperature error then moves the ln humidity proxy by at most
~0.2, i.e. up to ~20% in humidity. That is plausible for a thermal-infrared
retrieval, where humidity and temperature are strongly coupled.

**Why correct it.**
- The guide: "if a source units attribute is demonstrably wrong, record the
  corrected source unit and the evidence for it" in the key and metadata.
- The evidence here is the description, the dimensions and the orthonormality.
- Only the units attribute changes, `1` to `K-1`; no value does. A `1`
  invites a user to read the kernel as normalized, and their temperature
  errors would then come out scaled wrongly.
- The nomenclature row has to state a true unit. `unitless` would be wrong
  for the singular values.

**Alternatives.**
- Keep `unitless` as published. That puts a wrong unit in the row.
- Attach the unit to the vectors. That is arbitrary, and contradicts their
  orthonormality.

## 3. The grammar, applied

- **Quantity**: `water_vapor` (as in the 2026-10-14 rows), `dry_air`,
  `pressure_weight`.
- **Vertical form**: `column` (total or column-averaged), `partial_column`
  (per layer, 2.8), or none (a value at a level, or a layer mean).
- **Species or form**, always explicit: `h2o`, `hdo`, `delta_d`,
  `hdo_h2o_ratio`, `proxy_humidity`, `proxy_delta_d`. `dry_air` is its own
  quantity.
- **Basis**: `mole_fraction_dry_air`.
- **Role**: `apriori`, `averaging_kernel[_log][_cross_<quantity>]`,
  `averaging_kernel[_cross_<quantity>]_svd_{left_vectors,right_vectors,singular_values,rank}`,
  `{observation,measurement,total}_error_covariance_log[_cross_<species>]`,
  `observation_standard_error_log`, `standard_error`.
- `_cross_<quantity>` names the true-state quantity of an off-diagonal
  block: a species (`h2o`, `hdo`) or `air_temperature`.

The retrieved quantities the grammar implies get rows when their readers are
built, not now. They show that the pattern holds for the profile products:

| implied name | products (source) |
| --- | --- |
| `water_vapor_h2o_mole_fraction_dry_air` | TES (`Species` H2O half), TROPESS (`x_h2o`), IASI (`musica_h2o`) |
| `water_vapor_hdo_mole_fraction_dry_air` | TES (`Species` HDO half) |
| `water_vapor_hdo_h2o_ratio` | TROPESS (`x`) |
| `water_vapor_delta_d` | IASI (`musica_deltad`) |
| `water_vapor_proxy_humidity`, `water_vapor_proxy_delta_d` | IASI (`musica_wvp`, split) |

## 4. Proposed rows for `nomenclature_data.md` (43 new, 2 renamed)

If N16 and N10 are approved as revised, the count changes:
- N16 drops `water_vapor_hdo_h2o_ratio_observation_error_covariance_log`;
- N10 adds the two store names `water_vapor_proxy_averaging_kernel_svd` and
  `water_vapor_proxy_averaging_kernel_cross_air_temperature_svd`.

That makes 44 new rows.

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

Added for N12 (19):

| canonical_name | canonical_units | long_name |
| --- | --- | --- |
| `water_vapor_hdo_mole_fraction_dry_air_observation_error_covariance_log` | unitless | observation error covariance of the ln dry-air mole fraction of HDO water vapor |
| `water_vapor_hdo_mole_fraction_dry_air_observation_error_covariance_log_cross_h2o` | unitless | observation error covariance of the ln dry-air mole fraction of HDO water vapor with the ln H2O mole fraction |
| `water_vapor_h2o_mole_fraction_dry_air_observation_error_covariance_log_cross_hdo` | unitless | observation error covariance of the ln dry-air mole fraction of water vapor (H2O) with the ln HDO mole fraction |
| `water_vapor_h2o_mole_fraction_dry_air_observation_error_covariance_log` | unitless | observation error covariance of the ln dry-air mole fraction of water vapor (H2O) |
| `water_vapor_hdo_mole_fraction_dry_air_measurement_error_covariance_log` | unitless | measurement error covariance of the ln dry-air mole fraction of HDO water vapor |
| `water_vapor_hdo_mole_fraction_dry_air_measurement_error_covariance_log_cross_h2o` | unitless | measurement error covariance of the ln dry-air mole fraction of HDO water vapor with the ln H2O mole fraction |
| `water_vapor_h2o_mole_fraction_dry_air_measurement_error_covariance_log_cross_hdo` | unitless | measurement error covariance of the ln dry-air mole fraction of water vapor (H2O) with the ln HDO mole fraction |
| `water_vapor_h2o_mole_fraction_dry_air_measurement_error_covariance_log` | unitless | measurement error covariance of the ln dry-air mole fraction of water vapor (H2O) |
| `water_vapor_hdo_mole_fraction_dry_air_total_error_covariance_log` | unitless | total error covariance of the ln dry-air mole fraction of HDO water vapor |
| `water_vapor_hdo_mole_fraction_dry_air_total_error_covariance_log_cross_h2o` | unitless | total error covariance of the ln dry-air mole fraction of HDO water vapor with the ln H2O mole fraction |
| `water_vapor_h2o_mole_fraction_dry_air_total_error_covariance_log_cross_hdo` | unitless | total error covariance of the ln dry-air mole fraction of water vapor (H2O) with the ln HDO mole fraction |
| `water_vapor_h2o_mole_fraction_dry_air_total_error_covariance_log` | unitless | total error covariance of the ln dry-air mole fraction of water vapor (H2O) |
| `water_vapor_hdo_h2o_ratio_observation_error_covariance_log` | unitless | observation error covariance of the ln HDO/H2O mole ratio of water vapor |
| `water_vapor_h2o_mole_fraction_dry_air_observation_standard_error_log` | unitless | 1-sigma observation error of the ln dry-air mole fraction of water vapor (H2O) |
| `water_vapor_proxy_humidity_averaging_kernel_cross_air_temperature_svd_left_vectors` | unitless | left singular vectors of the cross averaging kernel of the water vapor proxy state with respect to air temperature, humidity proxy rows |
| `water_vapor_proxy_delta_d_averaging_kernel_cross_air_temperature_svd_left_vectors` | unitless | left singular vectors of the cross averaging kernel of the water vapor proxy state with respect to air temperature, delta D proxy rows |
| `water_vapor_proxy_averaging_kernel_cross_air_temperature_svd_right_vectors` | unitless | right singular vectors of the cross averaging kernel of the water vapor proxy state with respect to air temperature |
| `water_vapor_proxy_averaging_kernel_cross_air_temperature_svd_singular_values` | K-1 | singular values of the cross averaging kernel of the water vapor proxy state with respect to air temperature |
| `water_vapor_proxy_averaging_kernel_cross_air_temperature_svd_rank` | unitless | rank of the truncated singular value decomposition of the cross averaging kernel of the water vapor proxy state with respect to air temperature |

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
| `ObservationErrorCovariance`, 4 blocks as the kernel | `water_vapor_{hdo,h2o}_mole_fraction_dry_air_observation_error_covariance_log[_cross_{h2o,hdo}]` | unitless | (obs, level, level_2) | none; no `Units` attribute, declared `ln(vmr)^2` |
| `Characterization/MeasurementErrorCovariance`, 4 blocks | `water_vapor_{hdo,h2o}_mole_fraction_dry_air_measurement_error_covariance_log[_cross_{h2o,hdo}]` | unitless | (obs, level, level_2) | none; `ln(vmr)^2` |
| `Characterization/TotalErrorCovariance`, 4 blocks | `water_vapor_{hdo,h2o}_mole_fraction_dry_air_total_error_covariance_log[_cross_{h2o,hdo}]` | unitless | (obs, level, level_2) | none; `ln(vmr)^2` |

The block-to-name mapping of each covariance is the kernel's (2.4): `[0:17,
0:17]` HDO, `[0:17, 17:34]` HDO `_cross_h2o`, `[17:34, 0:17]` H2O
`_cross_hdo`, `[17:34, 17:34]` H2O.

No dry-air partial column is published. `AirDensity` is a number density on
levels, so it is left out.

### AIRS and CrIS (TROPESS / MUSES)

`level` 17. Order **surface_first**. Only FS (Standard) has the kernel and
prior; RS (Summary) has neither.

| source | streams | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- | --- |
| `observation_ops/xa` | FS | `water_vapor_hdo_h2o_ratio_apriori` | unitless | (obs, level) | none |
| `observation_ops/averaging_kernel` | FS | `water_vapor_hdo_h2o_ratio_averaging_kernel_log` | unitless | (obs, level, level_2) | none; "logarithmic_averaging_kernel_hdo_to_h2o_ratio" |
| `observation_ops/observation_error` | FS | `water_vapor_hdo_h2o_ratio_observation_error_covariance_log` | unitless | (obs, level, level_2) | none; not a valid covariance as published; left out if N16 is approved (F7) |
| `observation_ops/observation_error_h2o` | FS | `water_vapor_h2o_mole_fraction_dry_air_observation_standard_error_log` | unitless | (obs, level) | none; 1-sigma inferred; never scaled |
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
| `musica_wvp_xavkat_lvec[:, 0]` | `water_vapor_proxy_humidity_averaging_kernel_cross_air_temperature_svd_left_vectors` | unitless | (obs, rank_temperature, level) | none; rank padded |
| `musica_wvp_xavkat_lvec[:, 1]` | `water_vapor_proxy_delta_d_averaging_kernel_cross_air_temperature_svd_left_vectors` | unitless | (obs, rank_temperature, level) | none |
| `musica_wvp_xavkat_rvec` | `water_vapor_proxy_averaging_kernel_cross_air_temperature_svd_right_vectors` | unitless | (obs, rank_temperature, level) | none; temperature side, no proxy dim |
| `musica_wvp_xavkat_val` | `water_vapor_proxy_averaging_kernel_cross_air_temperature_svd_singular_values` | K-1 | (obs, rank_temperature) | none; corrected source unit `1` -> `K-1` (N17) |
| `musica_wvp_xavkat_rank` | `water_vapor_proxy_averaging_kernel_cross_air_temperature_svd_rank` | unitless | (obs) | none (int8) |
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
| F5 | **TROPESS FS `pressure` level 0 is -999** in R1p17 (CrIS-JPSS1 2022-07-10) and R1p20 (AIRS 2023-06-15), but holds the surface pressure in R1p11 (AIRS 2021-02-10), as it does in RS. | tropess.md R10 |
| F6 | **The TES kernel is in ln(vmr) space**, rows retrieved and columns true, per its own attribute. | N8, tes.md |
| F7 | **TROPESS FS `observation_error` is not a valid covariance.** Negative variances appear in all three versions sampled (R1p11, R1p17, R1p20), in 16-31% of targets at 750-619 hPa (2.11). R1p17 and R1p20 are also asymmetric, by as much as the variances themselves. In R1p20 (29,650 targets) 99.4% of targets have a negative variance somewhere, down to -14. Its `source` attribute says it is `obs_dd + obs_hh - obs_hd - obs_dh`, which must be symmetric with a non-negative diagonal. | N16, tropess.md R11 |
| F8 | **TES covariance cross blocks are exact transposes.** `S_HD == S_DH^T` with zero difference, for all three matrices in 3,000 targets (2008-07). Each matrix is symmetric to float rounding (at most 6e-8). | N15, tes.md |
| F9 | **IASI singular vectors are orthonormal** (max \|L^T L - I\| and \|R^T R - I\| = 0 to 4 decimals, for both the kernel and the temperature cross-kernel, one obs each). So the singular values carry a kernel's units: K-1 for the temperature cross-kernel, whose files say `1`. | N17, iasi.md I8 |

## 7. After agreement

1. Add the agreed rows to `nomenclature_data.md`, beside the N13 renames
   already made (user review before commit).
2. Map them in each product's key as its reader is built. GOSAT first (with
   the N13 renames in its key and configs), then TROPOMI's model-comparison
   stores on the existing obs axis.
3. Before any 2-D store, measure kernel compression with a scratch script
   (login node). The chunk rule sizes 2-D arrays: 50 layers take 131,072 obs.
