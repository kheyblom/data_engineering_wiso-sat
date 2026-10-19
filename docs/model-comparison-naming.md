# Model-comparison naming (cross-product reference)

How the Level 2 products' kernels, priors, dry-air columns, covariances and
pressure grids are named and laid out. Decided across all products in one
pass, approved 2026-10-19 (TASKS.md task 7). Use it to name any new variable
of this kind.

**Where things live:**
- **The rows** are in `nomenclature_data.md` (style_guides `fee64ec`: 48 rows;
  `a585066`: the XH2O rename).
- **The rules** for matrix stores and vertical dims are in the style guide's
  Level 2 section (`a585066`).
- **Each product's mapping** (source, name, units, dims, conversion, stores)
  is in the Model-comparison variables section of `docs/products/<product>.md`.
  Its key takes rows from there when its reader is built.
- **The review discussion** is in this file's git history, up to `e87a8e1`.

## The grammar (N1)

`<quantity>[_<vertical form>]_<species or form>[_<basis>][_<role>]`

| slot | values | notes |
| --- | --- | --- |
| quantity | `water_vapor`, `dry_air`, `pressure_weight` | |
| vertical form | `column` (total or column-averaged), `partial_column` (per layer), or none | none means a value at a level, or a layer mean |
| species or form | `h2o`, `hdo`, `delta_d`, `hdo_h2o_ratio`, `hdo_and_h2o` (a joint state), `proxy_humidity`, `proxy_delta_d`, `proxy` (both proxies) | always explicit (N13) |
| basis | `mole_fraction_dry_air` | dry-air only: a total-air quantity would be a different name |
| role | `apriori`, `standard_error`, `averaging_kernel[_log][_cross_<quantity>]`, `averaging_kernel[_cross_<quantity>]_svd_{left_vectors,right_vectors,singular_values,rank}`, `{observation,measurement,total}_error_covariance_log[_cross_<species>]`, `observation_standard_error_log` | suffixes, after `_standard_error` |

Rules that come with it:
- **No `profile` token (N2).** The dims say the shape. A retrieved H2O profile
  is `water_vapor_h2o_mole_fraction_dry_air`, the name a gridded 3-D field
  would take.
  - No product publishes one quantity at two shapes that only a `profile`
    token could tell apart.
  - One name may span a layer mean (GOSAT) and level values (TES, IASI): the
    dim and the `long_name` say which.
- **`partial_column` is needed** because a partial and a total column share
  `mol m-2`. SCIAMACHY publishes both for its priors.
- **A quantity at one level or over one range** (surface, 850-250 hPa) always
  carries a qualifier. Two examples, for when their readers are built:
  TROPESS `x_h2o_col_p` and `dd_004`.
- **`_log`** marks a kernel or covariance in ln space (N8). A linear kernel of
  the same parent is a different quantity.
- **`_cross_<quantity>`** names the true-state quantity of an off-diagonal
  block: a species, or `air_temperature`.
  - The row quantity leads the name.
  - Diagonal blocks carry no suffix (N9).
- **Established terms stay whole:** `averaging_kernel`, `delta_d`, `dry_air`,
  `observation_error_covariance`, `standard_error`.

Names the grammar implies for retrieved quantities. They get rows when their
readers are built:

| name | products (source) |
| --- | --- |
| `water_vapor_h2o_mole_fraction_dry_air` | TES (`Species` H2O half), TROPESS (`x_h2o`), IASI (`musica_h2o`) |
| `water_vapor_hdo_mole_fraction_dry_air` | TES (`Species` HDO half) |
| `water_vapor_hdo_h2o_ratio` | TROPESS (`x`) |
| `water_vapor_delta_d` | IASI (`musica_deltad`) |
| `water_vapor_proxy_humidity`, `water_vapor_proxy_delta_d` | IASI (`musica_wvp`, split) |
| `water_vapor_column_{h2o,hdo}_apriori` | SCIAMACHY (`h2o_column_apriori`, `hdo_column_apriori`) |

## Layout

**Pressure (N3, N4).** `pressure` is a variable store of its own, on `level`,
in Pa, with its own nomenclature row. It is not in the geolocation store
(revised by the user 2026-10-19: a 51-level grid would make TROPOMI's
geolocation store ~6x larger, and a user who needs only position and time
should not carry it). GOSAT, TES and TROPESS convert x 100 from hPa.

**Vertical dims (N5).**
- `level`: the points where pressure is given.
- `layer`: the slab between levels i and i+1, holding layer integrals or
  means. Only TROPOMI, SCIAMACHY and GOSAT have layers.

These names hold in every product, whatever the source calls them.

**Vertical order (N7).** Each source keeps its own order, recorded in a
`vertical_order` attribute:
- `top_first`: TROPOMI, SCIAMACHY, IASI;
- `surface_first`: GOSAT, TES, TROPESS.

No cross-product code can be layout-agnostic anyway, and the per-obs pressure
grid is always needed.

**Matrix axes (N6).** Rows on `level`, columns on `level_2`, with a
`matrix_axes` attribute. For a kernel, rows are the retrieved state and
columns the true state:

```
x_retrieved[i] = x_apriori[i] + sum_j A[i, j] * (x_true[j] - x_apriori[j])
```

```python
xr_sim = xa + (A * (xm - xa).rename(level='level_2')).sum('level_2')   # ln space for _log kernels
```

- Both axes are the same pressure grid.
- An array cannot use `level` twice, and TROPESS's `(target, level, level)`
  cannot be opened as written, so the second axis is renamed.
- `level_2` is neutral, so it also fits a symmetric covariance.

**Stacked arrays and matrix stores (N9, N10, N18).**
- A stacked source array splits into one store per quantity, as TES's HDO and
  H2O priors do.
- A matrix published in pieces is **one store**, named for the whole matrix,
  with each piece as its own array under its own canonical name. The pieces
  are either the blocks of a stacked state, or the components of a
  factorization.
  - TES: the kernel and three covariances, 4 blocks each, with both cross
    blocks kept.
  - IASI: the kernel SVD and the temperature cross-kernel SVD, with the
    vectors split per proxy.
- **Why one store:** a matrix's pieces mean nothing apart.
  - Even an H2O-only comparison needs TES's `A_HD` as well as `A_HH`.
  - Any SVD block needs L, s and R.
- **Why stop at matrices:** a kernel, a prior, a dry-air column and a pressure
  weight are each complete quantities used alone. As separate stores they
  are built, verified and finalized on their own, and can be added later.
- **IASI's rank dims are padded** to the record maximum with NaN, as each file
  already pads past each obs's rank.

## Decisions

| # | decision | why |
| --- | --- | --- |
| N1 | the grammar above | one pattern for every product's kernels, priors and errors |
| N2 | no `profile` token | the dims carry the shape; it causes no conflict in any product |
| N3 | `pressure` is a variable store, with a row (revised 2026-10-19; first decided as a geolocation coordinate) | the geolocation store stays position and time only; TROPOMI's grid alone is ~3 TiB |
| N4 | `pressure` in Pa | SI, and native in TROPOMI, SCIAMACHY and IASI (~99% of the volume) |
| N5 | `level` / `layer` in every product | a common join name across products |
| N6 | matrix rows on `level`, columns on `level_2` | an array cannot repeat a dim; neutral for covariances |
| N7 | keep each source's vertical order, with `vertical_order` | no restructuring; the pressure grid is always needed anyway |
| N8 | `_log` for ln-space kernels and covariances | a linear kernel of the same parent is a different quantity |
| N9 | TES blocks: the row species leads; `_cross_<species>` off the diagonal | a block is the kernel *of* its retrieved quantity |
| N10 | IASI: SVD components stored as published, split per proxy, rank padded | rebuilding is a derivation and 2.2x larger; the split loses nothing |
| N11 | GOSAT `dry_column` held | ~1/4 of the hydrostatic dry column, with no area in its unit, so no exact conversion (`gosat.md` G7) |
| N12 | covariances and the IASI temperature cross-kernel are included | needed for error-weighted comparison and assimilation |
| N13 | the XH2O rows renamed with explicit `h2o` | the species is always explicit; no store used the old names |
| N14 | `<type>_error_covariance` and `observation_standard_error` | the TES error budgets are established terms; follows `_standard_error` |
| N15 | both TES covariance cross blocks are stored | the guide's rule; a user never has to transpose (`S_HD` is exactly `S_DH^T`) |
| N16 | TROPESS `observation_error` left out, with no row | not a valid covariance in any version sampled (`tropess.md` R11) |
| N17 | IASI cross-kernel singular values in `K-1` | ln per kelvin; the vectors are orthonormal, so s carries the unit (`iasi.md` I8) |
| N18 | one store per matrix, in every product | a matrix's pieces are always used together |

## Evidence

Header reads and value checks, 2026-10-19. Each finding is recorded in full in
the product doc named:

| # | finding | recorded in |
| --- | --- | --- |
| F1 | the vertical order differs by product | each product doc's Model-comparison variables |
| F2 | GOSAT `dry_column` is ~1/4 of the hydrostatic dry column | `gosat.md` G7 |
| F3 | IASI `wv_avk_rank` is 12 or 13 by file, NaN past each obs's rank | `iasi.md` I6 |
| F4 | IASI changes processor version and platforms in 2019 | `iasi.md` I7 |
| F5 | TROPESS FS `pressure` level 0 is -999 in R1p17 and R1p20 | `tropess.md` R10 |
| F6 | the TES kernel is ln(vmr), rows retrieved and columns true | `tes.md` |
| F7 | TROPESS `observation_error` has negative variances in every version, and is asymmetric after R1p11 | `tropess.md` R11 |
| F8 | TES covariance cross blocks are exact transposes | `tes.md` |
| F9 | IASI singular vectors are orthonormal | `iasi.md` I8 |
