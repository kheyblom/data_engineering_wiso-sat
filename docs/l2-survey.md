# L2 product survey (all WISO-SAT products)

Evidence gathered on 2026-10-13/14 while settling the Level 2 rules (now in
the style guide) and the canonical units. Read this before writing a new
product's reader or nomenclature key. Decisions taken from it are in the root
`CLAUDE.md`. The original rule proposals (L2-1 .. L2-12, each with the gridded
precedent it follows) are in this file's history at `7a0af0a`, when it was
`tropomi/l2-standards-draft.md`.

Per-product facts a reader needs (paths, dims, time and fill encodings,
quirks) are in `docs/products/`. The scripts that produced this evidence are
in `tools/survey/`.

## Units across the L2 sensors

Header reads of one file per product, 2026-10-14. The AIRS and CrIS FS units
were checked to be the same across processor versions (R1p11..R1p19); only
their `long_name` wording drifts. Excluded as L3: the `AIRS_TROPESS_gridded_*`
files, the IASI data bag (`L3pp`), `TROPOMI_averaged_files`, and the GOSAT-2
`monthly_1deg`/`.mat` files. **`SCIAMACHY/H2O` and `SCIAMACHY/HDO` actually hold
ESA MIPAS files** (a different instrument on the same Envisat platform).

### What each product publishes

| sensor (product) | δD | other isotope form | water amount |
| --- | --- | --- | --- |
| TROPOMI (SRON L2 0003) | `deltad`, column: **`1`** | — | `h2o_column`, `hdo_column`: **`molec. cm-2`** |
| SCIAMACHY (SRON SICOR L2) | none | — | `h2o_column`, `hdo_column`: **`molec. cm-2`** |
| AIRS (TROPESS Summary, RS) | `dd_col_p` (850-250 hPa), `dd_004`: **`1e-3`** | HDO/H2O ratio profile `x`: `1` | `x_h2o` dry-air VMR profile: **`1`**; `x_h2o_col_p` (850-250 hPa): **`1e-6`** |
| CrIS-SNPP (TROPESS Summary, RS) | same as AIRS RS: **`1e-3`** | same: `1` | same: **`1`** / **`1e-6`** |
| AIRS (TROPESS Standard, FS) | none | `x`: `1` | `x_h2o` VMR profile: **`1`** |
| CrIS-JPSS1 (TROPESS Standard, FS) | none | `x`: `1` | `x_h2o` VMR profile: **`1`** |
| GOSAT, GOSAT-2 (IUP FOCAL v3.0.1) | `xded`, column-averaged: **`1e-3`** | — | `xh2o` column-avg dry-air mole fraction: **`1e-6`** |
| IASI (KIT MUSICA L2) | `musica_deltad` profile: **`1e-3`** | ln-space proxy state `musica_wvp`: `1` | `musica_h2o` profile: **`ppmv`** |
| MIPAS (ESA L2, in `SCIAMACHY/`) | none | separate HDO VMR profile: `1E-6` | H2O VMR profile, "in air": **`1E-6`** |
| TES (L2 HDO Nadir Lite v006) | none | — | `Species` = stacked HDO + H2O dry-air VMR profiles: **`VMR`**; `TotalColumnDensity` (HDO): labelled **`molecules/m2`**, actually molec cm-2 |

The differences are mostly **different quantities**, not different units for
one quantity, so there is one canonical unit per quantity family. A different
quantity gets its own canonical name, never a conversion.

### Value check (2026-10-14)

Read one file per product (one orbit for TROPOMI), applied each variable's
declared fill, and compared percentiles with physical expectations. Single
files, so this confirms units, not the distribution of the record.

| product | variable (declared unit) | p1 / p50 / p99 | verdict |
| --- | --- | --- | --- |
| TROPOMI | `deltad` (`1`), flag == 0 | -0.99 / -0.25 / 13.3 | **fraction confirmed** (p50 = -250 per mil) |
| TROPOMI | `h2o_column`, `hdo_column` (`molec. cm-2`) | p50 5.5e22, 1.3e19 | confirmed (~16 mm precipitable water; HDO/H2O ~2.3e-4) |
| TROPOMI | column averaging kernels (`1`) | p50 1.02 / 2.01 | unitless confirmed |
| SCIAMACHY | columns, kernel (`molec. cm-2`, `1`) | p50 1.1e22, 4.3e18; 0.27 | confirmed |
| TROPESS RS/FS | `x` HDO/H2O ratio (`1`) | 1.1e-4 / 2.3e-4 / 3.0e-4 | **mole ratio confirmed** (p50 = -260 per mil vs VSMOW) |
| TROPESS RS/FS | `x_h2o`, `x_h2o_raw` (`1`) | 2.5e-6 / 6e-4 / 3e-2 | **mol mol-1 confirmed** |
| TROPESS FS | `observation_error_h2o` (`1`) | 0.017 / 0.088 / 0.37 | **relative (ln-space) error, not a mole fraction** — must not be x 1e6 |
| TROPESS RS | `dd_col_p`, `dd_004` (`1e-3`); `x_h2o_col_p` (`1e-6`) | -327 / -247 / -153; 965 / 4077 / 9828 | confirmed |
| GOSAT, GOSAT-2 | `xded` (`1e-3`); `xh2o` (`1e-6`); kernel (`1`) | -220 / -136 / -46; 131 / 2417 / 5951; ~1.0 | confirmed |
| IASI | `musica_deltad` (`1e-3`); `musica_h2o` (`ppmv`) | -598 / -341 / 2; 2.7 / 168 / 28,450 | confirmed |
| IASI | `musica_wvp` (`1`) | -0.88 / 0.12 / 10.0 | **ln-space state** (ln of ppmv, ln of ratio), not a mole fraction |
| MIPAS | H2O `profile` (`1E-6`) | 0.9 / 6.0 / 452 | confirmed (stratospheric ppm) |
| MIPAS | HDO `profile` (`1E-6`) | ~0 / 9.5e-4 / 0.039 | confirmed (HDO ~1e-3 ppm in the stratosphere) |
| TES | `Species` / `Retrieval/HDO_H2O` (`VMR`) | HDO 4.7e-8, H2O 2.2e-4 (p50) | **mol mol-1 confirmed, but the array stacks two profiles** |
| TES | `TotalColumnDensity` (`molecules/m2`) | p50 7.9e18 | **mislabelled: values are HDO in molec cm-2** |

Findings that change the plan:

1. **TES `TotalColumnDensity` is in molec cm-2, not molecules/m2.**
   Integrating the TES HDO profile over pressure gives a median 7.83e22
   molecules/m2, and the file's value is exactly 1.000e-4 of that, per target.
   It is the HDO column. Conversion to `mol m-2` is therefore x 1e4 / N_A, the
   same as TROPOMI, not the 1 / N_A the label implies. The build must declare
   the corrected source unit and record it in metadata.
2. **TES `Species` (and `Retrieval/HDO_H2O`, an identical array) stacks two
   profiles.** Levels 0-16 are HDO and 17-33 are H2O, on the same 17 pressures
   repeated. `HDO_H2O` is a name, not a ratio. The two halves become two
   variables, which is a restructuring the style guide would have to allow;
   the ratio they imply is physical (p50 2.2e-4; δD from -82 per mil at the
   surface to -650 aloft).
   - Sarkar et al. (2026) confirm the stacked state vector, and that the
     `AveragingKernel` (34 x 34) holds separate HDO and H2O blocks.
   - The kernel, `ObservationErrorCovariance` and the error covariances
     therefore split into four 17 x 17 blocks (HDO-HDO, HDO-H2O, H2O-HDO,
     H2O-H2O). The cross blocks are needed to apply the kernel to δD, so they
     cannot be dropped.
3. **Two `1`-unit variables are log-space and must never be scaled with their
   neighbours:** TROPESS `observation_error_h2o` and IASI `musica_wvp`. The
   nomenclature key must map them to their own canonical names, with units `1`.
4. Not unit problems, but worth recording:
   - TROPOMI `processing_quality_flags == 0` still passes δD from -0.99 to
     +13 (p1/p99) and `h2o_column` up to 1.7e26; SRON's own filtering
     guidance needs to go in the metadata.
   - TROPOMI column kernels reach p99 ~700 in some layers.
   - TROPESS `x_h2o` reaches 0.44 mol mol-1 (unphysical).
   - The GOSAT and GOSAT-2 files contain only flag-0 soundings, so they arrive
     pre-filtered.

### Canonical units (decided 2026-10-14)

**δD → `1e-3`** *(decided)*.
- TROPOMI converts x 1000.
- AIRS/CrIS RS, GOSAT, GOSAT-2 and IASI are unchanged.
- Products publishing a ratio or separate HDO/H2O are not converted into δD:
  that would be a derivation, not a unit change.

**Column amount → `mol m-2`** *(decided)*.
- TROPOMI, SCIAMACHY and TES (corrected label) all convert x 1e4 / N_A
  (= 1.66053907e-20), with N_A = 6.02214076e23 exact.

**Mole fraction → `1e-6`** *(decided)*, dry-air basis. Where it applies (MIPAS rows kept for the record; MIPAS is excluded):

| product | variables | conversion |
| --- | --- | --- |
| GOSAT, GOSAT-2 | `xh2o`, `xh2o_uncertainty`, `h2o_profile_apriori` | none |
| AIRS, CrIS-SNPP (RS) | `x_h2o_col_p`, `x_h2o_col_p_error` | none |
| AIRS, CrIS-SNPP (RS); AIRS, CrIS-JPSS1 (FS) | `x_h2o`, `x_h2o_raw` profiles | x 1e6 |
| IASI | `musica_h2o`, `_apriori`, `_error` | none (respell `ppmv`) |
| MIPAS | H2O and HDO `profile`, `profile_error`, `extended_profile`, `a_priori_profile` | none (respell `1E-6`) |
| TES | HDO and H2O halves of `Species`; `ConstraintVector`, `Retrieval/Initial` | x 1e6 (`ConstraintVector` declares `mole/mole`) |
| TROPOMI, SCIAMACHY | none — they publish columns | — |

- MIPAS covariances are `1E-12`, i.e. (1e-6)^2, and stay consistent.
- HDO in ppm is small (MIPAS ~1e-3, TES p50 0.05). That costs no precision in
  float32, whose relative precision does not depend on magnitude.
- Not mole fractions, so they stay `1`: the HDO/H2O ratios (TROPESS `x`,
  `xa`, `x_raw`), the log-space variables (finding 3), averaging kernels, and
  flags.

All conversions are a single multiplication applied once in float32. The
verifier compares against `raw x factor` computed the same way, so the
expected mismatch is zero, with a 1-ulp tolerance stated if it is not.

## Dry-air vs total-air mole fraction (decided: one dry-air basis; option A for any future total-air product)

1. **The two quantities.**
   - Dry-air mole fraction: x_dry = n_w / n_dry.
   - Total (moist) air mole fraction: x_tot = n_w / (n_dry + n_w).
   - So x_tot = x_dry / (1 + x_dry), and x_dry = x_tot / (1 - x_tot).
   - Both are mol mol-1, so **no unit conversion can tell them apart or
     reconcile them**. Specific humidity (a mass fraction) is a third,
     different quantity.
2. **How much it matters.** The relative difference is about x itself:

   | regime | typical x | dry vs total |
   | --- | --- | --- |
   | tropical surface | 30,000 ppm | ~3% (30,000 dry is 29,126 total) |
   | mid-latitude surface | 5,000 ppm | 0.5% |
   | upper troposphere | 100 ppm | 0.01% |
   | stratosphere (MIPAS) | 5 ppm | negligible |

   The tropical figure is larger than GOSAT's own `xh2o` uncertainty (p50
   15.5 ppm on 2,417, ~0.6%), so the difference is not noise.
3. **What it does not affect.**
   - δD and HDO/H2O ratios: the basis cancels if both species share it.
   - Columns in `mol m-2`, which are absolute amounts.
   - Column-averaged "X" quantities (GOSAT `xh2o`, TROPESS `x_h2o_col_p`),
     which are dry-air by convention (column / dry-air column).
4. **What each product declares.**
   - Dry, explicitly:
     - GOSAT and GOSAT-2 `xh2o` (CF-style standard name
       `dry_atmosphere_mole_fraction_of_water_vapor`) and their a priori;
     - TROPESS RS `x_h2o` ("dry_air_volume_mixing_ratio") and `x_h2o_col_p`;
     - TES `Species` ("relative to dry air").
   - Total air: MIPAS, via the CF standard name
     `mole_fraction_of_water_vapor_in_air`. In CF "in_air" includes the water
     vapour; whether ESA meant that exactly is worth confirming, though it is
     negligible at MIPAS altitudes.
   - Not stated in the files (the headers say nothing either way), but
     **dry per Sarkar et al. (2026)**:
     - IASI MUSICA H2O: the paper describes it as "VMR relative to dry air
       (ppmv)". That is for the L3 product, which is built from the same L2pp
       retrieval.
     - TROPESS FS `x_h2o`: the paper's Table 1 defines satellite VMR as
       "relative to dry air", and FS is the same MUSES algorithm as RS, whose
       files say dry explicitly. The paper does not call out FS by name.
5. **Options.**
   - **A (recommended):** separate canonical names that carry the basis
     (e.g. `..._mole_fraction_dry_air` / `..._mole_fraction_in_air`). Each is
     stored as published, with a `mole_fraction_basis` attribute.
   - B: convert everything to one basis. H2O can convert itself exactly, but
     HDO needs the matching H2O value. That is a derivation, which the guide's
     "exactly represents the original data" rules out without approval.
   - C: ignore the difference. Not acceptable, given point 2.
6. **Consequence of the paper:** every mole fraction in the WISO-SAT
   products is dry-air. The only total-air quantity on disk is MIPAS, which
   the paper does not include (see the cross-check below). If MIPAS is out of
   scope, a single dry-air canonical basis covers everything, with no
   `_in_air` names needed now. Option A stays the rule for any future
   total-air product.

## Shared geolocation store: volume estimate

Per product, from file counts and per-file `obs` sizes sampled across each
record (4-6 files; TES and MIPAS vary most). Coordinates as they would be
stored:
- `time` as int64 and `lat`/`lon` as float32 (every source publishes float32
  centres): **16 B per observation**.
- A per-observation pressure grid on top for profile products: 4 B x levels.

All figures are uncompressed. `time` compresses very well and `lat`/`lon`
little, so the stored savings will be somewhat smaller.

| product | files | ~obs | lat/lon/time per store | pressure grid per profile store |
| --- | --- | --- | --- | --- |
| TROPOMI | 31,492 orbits | 2.6e10 | **419 GB** | 5.3 TB (51 levels) |
| IASI (MUSICA) | 4,568 | 1.6e9 | **25 GB** | 182 GB (29) |
| SCIAMACHY (SICOR) | 41,616 | 7.8e7 | 1.25 GB | 19 GB (61) |
| AIRS FS | 1,424 | 4.1e7 | 0.66 GB | 2.8 GB (17) |
| CrIS-JPSS1 FS | 1,208 | 3.0e7 | 0.48 GB | 2.0 GB (17) |
| AIRS RS | 6,361 | 1.1e7 | 0.18 GB | 0.76 GB (17) |
| GOSAT H2O / DED | 4,498 / 4,498 | 7.2e6 / 2.5e6 | 0.12 / 0.04 GB | 0.17 / 0.06 GB (6) |
| TES | 75 | 2.9e6 | 0.05 GB | 0.20 GB (17) |
| CrIS-SNPP RS | 1,865 | 2.8e6 | 0.05 GB | 0.19 GB (17) |
| MIPAS H2O / HDO | 35,124 / 30,213 orbits | 2.3e6 / 1.9e6 | 0.04 / 0.03 GB | 0.25 / 0.21 GB (27) |
| GOSAT-2 H2O / DED | 1,010 / 1,010 | 1.4e6 / 6.1e5 | 0.02 / 0.01 GB | 0.03 / 0.01 GB (6) |

How to read it:
- **Saving = (N - 1) x the per-store figure**, for N variable stores of one
  product.
  - At TROPOMI N = 6, a shared store saves **~2.1 TB** of lat/lon/time.
  - If profile variables carried their own pressure grid, each extra profile
    store would add 5.3 TB more.
- **Relative to the data, for 1-D float32 variables:** coordinates in every
  store cost 20 N B/obs against 4 N + 16 B/obs shared. That is 64% less at
  N = 5 and 72% less at N = 10, the same for every sensor because the dtypes
  are the same.
- **TROPOMI is ~94% of the total**, and IASI most of the rest. For the TROPESS,
  GOSAT, MIPAS and TES products the saving is under 1 GB per store.

What a shared store costs:
- A variable store alone no longer says where its values are.
- The join on `obs` relies on the identical-`obs`-axis rule, which the
  verifier already checks.
- The guide allows the geolocation store as the one store per product that
  holds several arrays.
- Decided form: one `<...>.geolocation.zarr` per product with
  `time`, `lat`, `lon` and, for profile products, the per-observation pressure
  grid. Every variable store keeps the granule index, so subsetting by day or
  granule still works without it.

## Cross-check against Sarkar et al. (2026), WISO-SAT data descriptor

Read 2026-10-14. The paper describes the eight products these raw files were
gathered for (its L3 gridding is out of scope here). Full text, local only:
`docs/sarkar-2026-wiso-sat.md` (from the Article in Press PDF, added
2026-10-22; this cross-check predates it).

**Confirms earlier findings:**
- Units:
  - GOSAT and GOSAT-2 `XH2O` in ppmv dry and δD in per mil;
  - SCIAMACHY and TROPOMI columns in molec cm-2;
  - AIRS and CrIS on 17 levels, publishing the HDO/H2O ratio (not δD).
- The SCIAMACHY product is SRON's L2 HDO/H2O columns (Schneider et al. 2018),
  i.e. `HDO_SICORv10`, 2003-2012. It publishes no δD; WISO-SAT derives it.
- TES stores HDO and H2O as one stacked state vector (finding 2).
- **Pre-filtered sources:**
  - The TROPESS Summary (RS) files "include only retrievals passing internal
    convergence and sensitivity checks".
  - GOSAT and GOSAT-2 FOCAL v3.0 have undergone "rigorous multi-stage
    product-level quality control". This matches the all-flag-0 GOSAT files.
- The TROPESS FS kernel is logarithmic (HDO/H2O in ln space). This is
  consistent with treating `observation_error_h2o` as log-space.

**Corrects or adds:**
1. **MIPAS is not part of WISO-SAT.** The paper's SCIAMACHY is the SRON
   column product, not MIPAS limb profiles. `SCIAMACHY/H2O` and
   `SCIAMACHY/HDO` (MIPAS 2PE/2PS files, 2002-2012) look like a download that
   picked up the wrong Envisat instrument. Decided 2026-10-14: MIPAS is
   excluded.
2. **The dry-air basis is settled by the paper** for IASI and TROPESS FS (see
   the dry-air section, point 4).
3. **Upstream / WISO-SAT filtering guidance to record in metadata (style guide),
   not apply:**
   - TROPOMI: iterations <= 10, SZA <= 70°, cloud optical thickness < 0.3,
     surface albedo >= 0.02, plus the clear-sky criteria of Schneider et al.
     (2022) Table 1.
   - SCIAMACHY:
     - flag 0, iterations < 12, SZA < 70°;
     - 0.7 <= H2O/H2O_apriori <= 1.3 and 0.9 <= CH4/CH4_apriori <= 1.1;
     - -600 < δD < 0 per mil;
     - log(RMS) within ±6σ of the median, log uncertainties within ±5σ.
   - TROPESS Standard (FS): DOF >= 1, COD <= 0.5.
   - TES: strict COD <= 0.5 and DOF >= 1; relaxed COD <= 3.6 and DOF >= 0.5.
   - These are WISO-SAT's choices, citing the product papers. Each store's
     metadata should name its source.
4. **Coverage gaps against the paper's periods** (dates on disk, first ..
   last file):
   - **TES: 2004-09 .. 2010-12** (75 monthly files; 2005 has 11 months). The
     paper uses TES 2004-2015 (Table 2). 2011-2015 is missing from disk, or
     was deliberately not downloaded.
   - **AIRS: RS 2002-09 .. 2020-03, FS 2021-02 .. 2024-09.** That leaves a
     ~10-month gap (2020-04 .. 2021-01) between the two streams, against the
     paper's continuous 2002-2024.
   - CrIS: SNPP RS 2015-12 .. 2021-05 and JPSS1 FS 2021-04 .. 2024-09; they
     overlap by two months.
   - The others match the paper or exceed it: TROPOMI 2017-11 .. 2024-05
     against the paper's 2019-2021; SCIAMACHY 2003-01 .. 2012-04; GOSAT
     2009-2021; GOSAT-2 2019-2021; IASI L2 2014-2020.
5. **IASI:** the paper grids MUSICA *L3*, the KIT data bag excluded here. The
   `IASI_L2` files (`L2pp`, the a posteriori processed L2 of Diekmann et al.
   2021) are the L2 source of the same data. They are valid L2 but are not
   what WISO-SAT itself read.
6. *Aside (L3, out of scope):* the paper states the WISO-SAT TROPOMI
   `deltad_1deg` is in per mil. The `TROPOMI_averaged_files` sampled before
   the L3 exclusion had a median of -0.175, which is a fraction, and carry no
   `units` attribute. Worth raising with the authors if those files are the
   published ones.

**Previous answers re-checked:**
- Unit verdicts: unchanged.
- TES column label correction: unchanged. The paper does not address it; the
  integration test stands.
- Geolocation estimate: unchanged, except that the MIPAS rows drop out if
  MIPAS is out of scope.
- Withdrawn: the earlier recommendation of `mipas` as `data_source`. It is
  superseded by finding 1.
