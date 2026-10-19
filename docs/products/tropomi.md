# TROPOMI (SRON HDO L2, product 0003, processor 8.1)

Everything known about the TROPOMI raw data, and how the reader, configs and
key handle it. Rules that apply to every product are in the root `CLAUDE.md`
and the style guide; cross-product evidence is in `docs/l2-survey.md`.

Each known data issue has an ID (T1, T2, ...) and a status:
- **handled:** the build and the verifier deal with it, and the stores record
  it in their metadata;
- **open:** not resolved yet;
- **record only:** a property of the data that users should know about; the
  stores keep it as published.

Unless marked otherwise, an issue is upstream: present in SRON's own copy,
not introduced by the download.

## Raw data

```
/glade/derecho/scratch/kheyblom/data/wisosat/raw/TROPOMI/tropomi.grid.surfsara.nl/
  hdo/<YYYY>/<MM>/<DD>/<orbit>/s5p_l2_hdo_<product_version>_<orbit:05d>.nc
  hdo/2017/11/08/373/s5p_l2_hdo_0003_00373.nc     (~1.1 GB each)
```

- **Record (after the 2026-10-16 re-download):** 38,648 orbit files from
  2017-11-08 to 2025-11-29, in 39,001 orbit directories.
  - 5-14 orbits a day. Not every orbit number has a file.
- **Versions:** product version `0003` (file name). Processor version `8.1`
  (root `version` attribute) in every file; the stores are named by it.
- **Size:** ~3.3e10 observations stored. That is ~130 GB uncompressed per 1-D
  float32 variable and ~6.5 TB per `(obs, 50)` variable.

## Record coverage and file defects

Every file was audited on 2026-10-16 (develop job 7839486,
`tools/survey/tropomi_file_audit.py`; TESTING.md finding 7). For each file,
the audit recorded whether it opens, its version, and whether every source the
pipeline reads was written.

| result | files |
| --- | --- |
| complete | 38,459 (99.5%) |
| partially processed (T5) | 77 |
| shells, nothing written (T4) | 109 |
| corrupt upstream (T3) | 3 |

Plus 353 empty orbit directories (T2) and 77 days with no files (T1). The
defects cluster in 2019 (93 shells, 74 partial). 2017, 2020 and 2025 are
clean. The orbit lists are in the appendix.

| # | issue | status |
| --- | --- | --- |
| T1 | **77 days have no data upstream** between 2017-11-08 and 2025-11-29. Each returned HTTP 404 from `tropomi.grid.surfsara.nl` (58 checked 2026-10-14, 19 on 2026-10-16). The longest runs are 2017-11-30..12-11 and 2018-01-10..01-27. | handled: `expected_missing_days` |
| T2 | **353 orbit directories are empty upstream**: the directory exists on the server but holds no file. Each was checked against the server listing (2026-10-14). | handled: `expected_empty_granules` |
| T3 | **3 files are corrupt upstream**, byte-identical to the server copies, and HDF5 cannot open them. Worth reporting to SRON: **03335** (2018-06-05, "wrong fractal heap header signature"), **07821** (2019-04-17, truncated to 3.6 MB of 645 MB) and **07844** (2019-04-19, truncated to 18 MB of 1.2 GB). | handled: `expected_unreadable_granules`; left out of every store and named in `known_data_gaps`. The build confirms each still fails to open. |
| T4 | **109 shell files**: every variable is declared at full size (e.g. 693,590 observations), but no data was ever written, so every read returns fill. Mostly 68,534 bytes; 93 are in 2019. The upstream copies are identical. | handled: indexed as granules with no observations; `granule_source_rows` keeps their declared size |
| T5 | **77 partially processed files.** In 73 of them, 93-100% of rows were never processed: time, lat/lon, SZA and every retrieval variable are unwritten. Across all 48,741,476 such rows, none of the 20 other variables the pipeline reads holds a value. In the other 4, every row was processed but some retrieval variables were never written. The processed rows (1,356,964 in all) often lack retrieval variables, quality flags and even scanline indices too. Mostly 2019. | handled (user decision 2026-10-16; TESTING.md finding 8): an observation is a row whose time is written. Unprocessed rows are left out, but only after the build confirms every source is fill on them; the verifier re-derives this from raw. `granule_source_rows` keeps each file's own row count. |
| T6 | **The upstream record ends at 2025-11-29.** The server lists 2025-11-30, but its 14 orbit directories are empty. | record only |
| T7 | **The first download (2026-10) was incomplete**; details below. | handled: re-downloaded 2026-10-16 and re-audited |
| T8 | **6 rows have a time but no position**, in three partial files: orbit 8480 (row 0), 8674 (rows 0 and 3) and 8726 (rows 0-2), all June 2019. Each is the only row its file has a time on. SRON wrote the time (2-3 rows share one timestamp), SZA ~100.5-101 deg (night), solar azimuth, viewing zenith, and in 8674 viewing azimuth. Lat/lon centre and corners, scanline, ground pixel, every retrieval, meteo and flag variable are fill. The first production build stored them, with lat/lon 9.96921e36 in the geolocation store; verification caught it (2026-10-17). | handled: a row needs time, lat and lon to be an observation (user decision 2026-10-17); `allowed_on_rows_left_out` lets their SZA go. The three orbits hold no observations (TESTING.md finding 10) |

### History: the first download (found 2026-10-14, resolved 2026-10-16)

Each gap was checked against `https://tropomi.grid.surfsara.nl/hdo/`, one
request per gap.
- **Orbits:** 31,492 orbit directories reached only to 2024-05-30. 692 of
  them were empty: 353 are empty upstream too (T2), but **339 held a file
  upstream that never arrived.** By month: 2019-05 1, 2020-09 25, 2023-02 1,
  2023-03 2, **2023-04 290**, 2023-06 1, 2023-07 4, 2023-08 4, 2023-10 4,
  2023-12 2, 2024-01 4, 2024-02 1.
- **Days:** 70 days had no directory. 58 are upstream gaps, but **12 exist
  upstream**: 2024-01-01..04 and 2024-04-10..17.
- **Download artifacts:**
  - truncated duplicates named `<file>.nc?action=show` beside complete files
    (orbits 00608 and 16210);
  - a `.smbdelete*` file (orbit 9453);
  - 195 `.DS_Store` files.

  The reader matches file names exactly and walks only all-digit
  directories, so stray files are ignored.

Because the build refuses undeclared gaps, it would not have run on that
tree. The re-download filled every gap and extended the record to
2025-11-29, adding 19 missing days, all real upstream gaps (T1). The full
lists of what was missing are in git history (`0b0a3d7`,
`docs/products/tropomi-download-gaps.md`).

## File format

- **Groups.** There are no root variables, so a source is named by its HDF5
  path, `<group>/<variable>`:
  - `target_product`: δD, H2O/HDO columns, precisions, averaging kernels and
    a priori profiles;
  - `instrument`: lat/lon centre and corners, time, geometry and pixel ids;
  - `diagnostics`: the flags;
  - `meteo` and `side_product`.
- **Observation layout.** Everything is indexed by `nobs`, the full L1B swath
  flattened in scanline-then-pixel order (e.g. 4173 x 215 = 897,195).
  Scanline is i // 215 and ground pixel is i % 215; the verifier confirms
  this on every file, on the rows where the indices were written.
- **Secondary dims.**
  - `nlayer` 50, `nlevel` 51, `ncorner` 4;
  - `nwin` 1 (squeezed);
  - `ntime` 7: `instrument/time` is a broken-down timestamp.
- **Storage.** Each variable is one HDF5 chunk spanning the whole variable,
  zlib level 1 with shuffle. Reading the 19 variables of one orbit took 2.6 s
  cold. Reading a file's metadata takes ~0.9 s on one process, because each
  variable's header sits in a different part of the 1 GB file.
- **Day boundary.** In the sampled pair, orbits did not straddle UTC
  midnight. The build checks that `time` never decreases.

| # | issue | status |
| --- | --- | --- |
| T8 | **No `_FillValue`.** Missing values are the netCDF defaults, float 9.96921e36 and int -2147483647. In a complete file (orbit 13847):<br>- float fill occurs in every retrieval, aerosol, albedo and chi-squared variable, but not in SZA, lat or lon;<br>- int fill occurs in `iterations` and both spectral-point counts;<br>- `processing_quality_flags` holds int fill only on the 238 processed rows of partial files that have no flags. | handled: declared per source in `source_fill_values` and masked. The verifier fails if a declared fill never occurs, or an undeclared default fill appears. |
| T9 | **Real NaNs in `deltad_precision`** alongside the fill (5,447 in orbit 13847). | record only: they stay NaN, indistinguishable from masked fill |
| T10 | **Time is broken down**: `instrument/time` is int32 (nobs, 7), year .. millisecond. | handled: decoded exactly to int64 ms since 1900 |
| T11 | **Three variables are "not implemented"**: `quality_flag`, `convergence` and `glintflag`. The real flag is `processing_quality_flags`, with CF `flag_masks`/`flag_values`. | handled: only `processing_quality_flags` is stored, as `quality_flags_retrieval` |
| T12 | **The `standard_name`s are SRON's own**, not CF (`delta_d`, `water_column`, `height_scattering_layer`, ...). | record only: retained unchanged, per the style guide |
| T13 | **Cloud parameters are named after aerosol.** Schneider et al. (2022) Table 1 filters on "cloud" optical thickness and height, and these are `aerosol_optical_thickness` and `aerosol_height`, SRON's effective scattering layer (evidence under Build details). | handled: stored as `optical_thickness_scattering_layer` and `height_scattering_layer`; explained in `filtering_guidance` |
| T14 | **Reduced chi-squared is undefined.** Table 1 filters on it, but the files hold only the unreduced `chi_squared` and per-pixel spectral point counts (details under Build details). | handled: both inputs stored; the inferred reduction is recorded in the metadata |
| T15 | **`nobs` varies widely.** It was ~697,800 per orbit in 2018-2019 and ~897,000 from 2020 (the August 2019 along-track resolution change). Complete files run from 625,220 to 1,204,215, and short orbits go down to 1,505. Every orbit is a whole number of 215-pixel scanlines. | handled |
| T16 | **Some units are byte strings** (`b'1'`) when read with h5py. | handled: decoded |
| T17 | **Units:** `deltad` is a fraction (`1`, median -0.25), and the columns are `molec. cm-2`. | handled: x 1000 to per mil, and x 1e4 / N_A to `mol m-2` |

## Values (record only)

| # | issue |
| --- | --- |
| T18 | `processing_quality_flags == 0` still passes unphysical δD: -0.99 to +13 as a fraction (p1/p99), with extremes of -67,429 and +55,177. `h2o_column` reaches 1.7e26 molec cm-2. SRON's Table 1 filters are needed on top of the flag, and are recorded in every store's `quality_filtering`. In orbit 16820, 71% of `nobs` have an `hdo_column` and 65% have flag 0. |
| T19 | Flag-0 pixels reach negative surface albedo (p1 -0.95, minimum -1.97). The albedo >= 0.02 clear-sky cut removes them. |
| T20 | Column averaging kernels reach p99 ~700 in some layers. This is unexplained and not a unit issue; it matters once kernels are stored. |
| T22 | **Pressure is unphysical within ~0.1 deg of the North Pole.** In orbit 14069, 4 pixels at 89.91-89.98 N have a surface pressure of 5.2e5 to 1.2e8 Pa (the orbit's p99.9 is 1.03e5). `pressure_levels` still increases downward and its last level equals `meteo/surface_pressure`, and `dry_air_subcolumns` scales up with it, so this looks like SRON's meteo interpolation at the pole, not a read error. Orbit 32414 (January, polar night) has none. Stored as published (checked 2026-10-19). |

## Outside the Level 2 scope

| # | issue |
| --- | --- |
| T21 | The WISO-SAT TROPOMI L3 files (`TROPOMI_averaged_files`, excluded) seemed to hold `deltad_1deg` as a fraction (median -0.175), with no `units` attribute. Sarkar et al. (2026) state per mil. Worth raising with the authors if those are the published files. |

## Build details (built 2026-10-14; every file audited 2026-10-16; bench next)

- **Granule:** an orbit. The granule index has ~38.6k entries and is stored
  as one chunk. Resume starts after the last committed orbit, whose index entry
  is written in the same commit as its data.
- **Appends:** orbit sizes vary, so appends do not land on chunk boundaries.
  Each append rewrites the trailing partial chunk, which is safe only with a
  single writer.
- **Gaps and defects** (T1-T5) are declared in the config, never detected:
  `expected_missing_days`, `expected_empty_granules` and
  `expected_unreadable_granules`. The build fails on anything undeclared.
- **Fixture:** `validation/stage_tropomi.py` stages the following.
  - Orbits 13857, 13870, 13871, 13899 and 13900, each cut to 23-47 mid-orbit
    scanlines (38,055 obs). 2020-06-18, a real upstream gap, falls between
    them.
  - An empty orbit directory (13872).
  - Real defect files copied whole into 2020-06-16 as stand-ins: shell 6380,
    partial 8532 (10 of 697,890 rows processed), and the truncated 7821.
- **Chunking starting points for the bench** (the guide allows 5-40 MiB):
  - 4,194,304 obs for 1-D float32 (16 MiB);
  - 131,072 obs for `(obs, 50)` float32 (25 MiB).
- **Geolocation store:**
  - `time`;
  - `lat`, `lon` (pixel centre);
  - (`pressure` was planned here; since 2026-10-19 it is a variable store of
    its own: see Model-comparison variables);
  - pixel corners, optional (`corner`, 32 B/obs).
- **Filtering guidance to record in metadata, not apply.** Schneider et al.
  (2022) Table 1, read from the publisher's image. Sarkar et al. (2026)
  apply the all-scene and clear-sky rows.
  - All scenes:
    - iterations <= 10;
    - reduced chi-squared of the final fit <= 150;
    - reduced chi-squared of the pre-fit <= 150;
    - SZA <= 70°.
  - Clear sky: cloud optical thickness < 0.3 and surface albedo >= 0.02.
  - Cloudy scenes: cloud height <= 2000 m and cloud optical thickness > 0.3.
  - Schneider et al. recommend clear-sky and low-cloud scenes.
- **What Table 1's terms are in the file:**
  - **Cloud optical thickness and height:** these are `aerosol_optical_thickness`
    and `aerosol_height`, SRON's effective scattering layer. The evidence:
    - the paper fixes the layer's thickness d at 2500 m, and
      `aerosol_geometric_thickness` is 2500 m on every pixel;
    - SRON's PUM for the successor PAL product (SRON-ESG-RP-2024_020)
      uses `aerosol_optical_thickness < 0.3` for clear sky.
  - **Reduced chi-squared:** this is `chi_squared` / `number_of_spectral_points_*`,
    which is inferred because no source defines it. In orbit 13847
    (2020-06-15, flag 0):
    - the median is ~10;
    - 92% (final fit) and 99% (pre-fit) pass <= 150.
    The alternative divisor, points minus degrees of freedom, differs by
    ~2.5%. The counts vary per pixel (270-277 final, 309-316 pre-fit), so
    the raw inputs are stored and the reduction is recorded as inferred.
  - **No CH4 filter:** CH4 only drives the pre-fit of the cloud parameters.
  - **Negative albedo:** flag-0 pixels reach negative surface albedo (p1
    -0.95); the albedo >= 0.02 cut removes them.

## Production subset (decided 2026-10-14)

There are 16 one-dimensional stores, ~1.7 TB uncompressed. The rows are in
`nomenclature_data.md` (style_guides `fd94a93`).
- **Naming rule:** the quantity comes first, then qualifiers general to
  specific (location, component, fit, band).
- **Exception:** established terms stay whole (`solar_zenith_angle`).
- **`quality_flags_retrieval`** is shared across products; the store
  attributes carry each product's flag meanings.

**Core: the retrieval plus the mandatory flag.**

| source | canonical_name | units | conversion |
| --- | --- | --- | --- |
| `target_product/deltad` | `water_vapor_column_delta_d` | 1e-3 | x 1000 |
| `target_product/deltad_precision` | `water_vapor_column_delta_d_standard_error` | 1e-3 | x 1000 |
| `target_product/h2o_column` | `water_vapor_column_h2o` | mol m-2 | x 1e4 / N_A |
| `target_product/h2o_column_precision` | `water_vapor_column_h2o_standard_error` | mol m-2 | x 1e4 / N_A |
| `target_product/hdo_column` | `water_vapor_column_hdo` | mol m-2 | x 1e4 / N_A |
| `target_product/hdo_column_precision` | `water_vapor_column_hdo_standard_error` | mol m-2 | x 1e4 / N_A |
| `diagnostics/processing_quality_flags` | `quality_flags_retrieval` | unitless | none (int32; mandatory) |

**Filter inputs: everything Table 1 needs**, so users can filter without the
raw files.

| source | canonical_name | units | conversion |
| --- | --- | --- | --- |
| `diagnostics/iterations` | `iterations_retrieval` | unitless | none (int32) |
| `instrument/solar_zenith_angle` | `solar_zenith_angle` | degree | none (respell `degrees`) |
| `side_product/aerosol_optical_thickness` | `optical_thickness_scattering_layer` | unitless | none (squeeze `nwin`) |
| `side_product/aerosol_height` | `height_scattering_layer` | m | none (above surface) |
| `side_product/surface_albedo` | `albedo_surface_2365nm` | unitless | none (squeeze `nwin`) |
| `diagnostics/chi_squared` | `chi_squared_retrieval` | unitless | none (unreduced) |
| `diagnostics/chi_squared_prefit` | `chi_squared_prefit` | unitless | none (unreduced) |
| `diagnostics/number_of_spectral_points_in_retrieval` | `spectral_point_count_retrieval` | unitless | none (int32; squeeze `nwin`) |
| `diagnostics/number_of_spectral_points_in_prefit` | `spectral_point_count_prefit` | unitless | none (int32; squeeze `nwin`) |

**Model comparison:** kernels, priors, dry-air partial columns and the
pressure grid. Named 2026-10-19 and not built yet; see Model-comparison
variables below.

- **Left out unless asked:** every other variable. They are listed, with
  reasons and size estimates, under Variable inventory below.

## Model-comparison variables (named 2026-10-19)

Named in the cross-product naming pass. The grammar and decisions are in
`docs/model-comparison-naming.md`; the rows are in `nomenclature_data.md`
(style_guides `fee64ec`). Units are after conversion. The key rows and the
three configs carry them (2026-10-19), and the fixture builds and verifies
them. Not built at bench or production scale yet.

- **Dims:** `nlayer` (50) becomes `layer`; `nlevel` (51) becomes `level`, the
  layer interfaces.
- **Vertical order:** `top_first`. Level 0 is 0 Pa, and the last level is the
  surface pressure.

| source | canonical_name | units | dims | conversion |
| --- | --- | --- | --- | --- |
| `target_product/h2o_column_averaging_kernel` | `water_vapor_column_h2o_averaging_kernel` | unitless | (obs, layer) | none |
| `target_product/hdo_column_averaging_kernel` | `water_vapor_column_hdo_averaging_kernel` | unitless | (obs, layer) | none |
| `target_product/h2o_profile_apriori` | `water_vapor_partial_column_h2o_apriori` | mol m-2 | (obs, layer) | x 1e4 / N_A from `molec. cm-2` |
| `target_product/hdo_profile_apriori` | `water_vapor_partial_column_hdo_apriori` | mol m-2 | (obs, layer) | x 1e4 / N_A |
| `meteo/dry_air_subcolumns` | `dry_air_partial_column` | mol m-2 | (obs, layer) | x 1e4 / N_A |
| `meteo/pressure_levels` | `pressure` | Pa | (obs, level) | none; layer interfaces |

- SRON calls the priors "profile", but they are partial columns: "A-priori
  vertically integrated partial column of water in layers", in molec cm-2
  per layer. Hence `partial_column`.
- **Stores:** 6 new variable stores on the existing obs axis and granule
  index, `pressure` among them. `pressure` is its own store, not part of the
  geolocation store (user decision 2026-10-19), so the finalized geolocation
  store (697 GiB) keeps position and time only. None of the 19 existing
  stores is rebuilt.
- **Size: ~19 TiB with byte-shuffled blosc**, against ~29 TiB with zarr's
  default zstd (Variable inventory, group 1). Expect ~20-21 TiB on disk, since
  the method runs 5-10% low on floats.
  - The chunk rule gives 50 and 51 levels 131,072 obs per chunk.
  - **Compression measured 2026-10-19**, on orbits 14069 (2020-07-01) and
    32414 (2024-01-15): values prepared as the build prepares them, written
    at the production chunk to an in-memory zarr store under lossless
    zarr v3 codecs, every round trip exact. The two orbits agree within 2%.

    | est. TiB over the record | default zstd | blosc zstd 3 + shuffle | **blosc zstd 5 + shuffle** | blosc zstd 9 + shuffle |
    | --- | --- | --- | --- | --- |
    | H2O kernel | 3.7-3.8 | 3.15 | **3.1-3.2** | 2.9 |
    | HDO kernel | 3.6-3.7 | 2.7 | **2.6-2.7** | 2.5 |
    | H2O a priori | 5.5 | 4.0 | **3.6** | 3.5 |
    | HDO a priori | 5.5 | 4.0 | **3.6** | 3.5 |
    | dry-air partial column | 5.4 | 3.6 | **3.1-3.2** | 3.1 |
    | `pressure` | 5.4 | 3.5 | **3.1-3.2** | 3.0 |
    | total | 29.2-29.3 | 21.1 | **19.2** | 18.6 |

    - **Chosen (user, 2026-10-19): blosc zstd 5 + shuffle**, set per array in
      the configs' `compression` block. It writes at ~300-1000 MiB/s and
      reads as fast as the default.
    - Level 9 writes at 15-38 MiB/s, which would cost hundreds of core-hours
      over the record. zstd 9 without shuffle gains nothing. Bitshuffle, and
      transposing the chunk to layer-major, do worse.
    - Every other TROPOMI array keeps the default, including the rest of the
      geolocation store, so the 19 finalized stores are unchanged.
- **Fill (checked 2026-10-19), always whole rows:**
  - the kernels are fill wherever the retrieval wrote nothing: ~29% of rows
    in a complete orbit, and 1,356,955 kept rows of the partial files;
  - the priors, dry air and pressure are fill only on kept rows of partial
    files: 158, 161, 68 and 48 rows. They have none in the complete orbits
    sampled (14069, 32414).
  - None of the six is written on any row left out. That includes the six
    rows of finding 10, so `allowed_on_rows_left_out` is unchanged.
  - Method: the reader's own `read_granule` and row rule over all 77 partial
    files.
- **T20:** column kernels reach p99 ~700 in some layers. Record only.
- **T22:** pressure near the North Pole is unphysical. Record only.

## Variable inventory (2026-10-18)

Every variable in an orbit file is listed here, with what was done with it and
why. Any of the variables left out can be built later as a new store on the
same `obs` axis and granule index, without rebuilding the existing stores.
Each file holds 69 variables:
- 19 are stored, in the 16 variable stores and the geolocation store;
- 50 are not.

**Size estimates.** Each variable of orbit 14069 (2020-07-01, complete,
803,025 obs) was compressed with the stores' own codec, the zarr v3 default
zstd. Floats had fill masked to NaN, as the build does. The result was scaled
to the record's 32,657,526,234 obs.
- *raw GiB* is the uncompressed full-record size; *est. store GiB* is the
  compressed estimate.
- **Calibration:** against the bench's measured July 2020 stores, the method
  is within -3% to +12%, and float stores come out 5-10% low. Over all the
  stored variables it predicts 1.2 TiB against 1.3 TiB on disk.
- Treat the estimates as **±15%**. Where fill varies across the record they
  move with it: shells and partial files hold less, and night pixels hold no
  retrieval.
- Script: a scratch script, rerunnable on any orbit. It writes each variable
  to an in-memory zarr array and sums the chunk bytes.

**Totals by group (est. store size):**

| group | variables | est. store size |
| --- | --- | --- |
| stored | 19 | ~1.2 TiB (1.3 TiB on disk) |
| 1. deferred, model comparison | 6 | ~29 TiB |
| 2. not implemented | 3 | ~8 GiB |
| 3. redundant | 1 | ~82 GiB |
| 4. file bookkeeping | 4 | ~82 GiB (`pixel_id`); scanline and ground_pixel ~0 |
| 5. pixel corners | 2 | ~490 GiB |
| 6a-6e. left out unless asked | 34 | ~18.2 TiB, of which ~16.5 TiB is four 50-layer variables: meteo temperature and altitudes, and the CH4 and CO priors |

**Swath position: scanline and ground_pixel** (group 4).
- SRON's definitions:
  - `scanline`: "Zero-based scanline index of pixel in Level 1B file";
  - `ground_pixel`: "Zero-based ground-pixel index of pixel in Level 1B file".
  - Both are int32 with `units` 1. `pixel_id` is "One-based pixel index in
    Level 1B file".
- **The layout:** a file's row r is scanline r // 215, ground pixel r % 215.
  The verifier confirms this on every file.
- **From the granule index**, r = obs index - `granule_obs_start` for
  **38,450 granules (99.5%)**, those whose `granule_obs_count` equals
  `granule_source_rows` (nothing left out). So the swath position needs no
  store there.
- **This fails for 83 granules** that hold 8,690,054 obs (0.03%). There, rows
  that are not observations were left out, so an obs's position no longer
  gives its source row. Another 112 granules hold no obs at all.
- **In those 83 files SRON's indices fit the layout on every row that has
  both** (8,689,897). `scanline` is unwritten on 111 kept rows and
  `ground_pixel` on 157.
- **Cost:** both compress to ~0 (runs of 215, and a repeating 0-214), so
  storing them as is costs well under 1 GiB. A build-derived source-row index
  would cover all rows, including those 157, but compresses badly without a
  delta filter (~82 GiB).

**Pixel corners: not redundant** (group 5; tested on orbits 3700, 14069 and
32414, from 2018, 2020 and 2024).
- **Across track**, neighbouring pixels share their edge corners exactly.
- **Along track** they do not: consecutive scanlines' corners are ~11 m apart
  (at most 23 m).
- **Rebuilt from the centres** (each corner as the mean of the four
  surrounding centres, extrapolated at the swath edges):
  - interior corners are off by a median of 14 m, p99 ~211 m and at most
    ~280 m, against pixels of ~5.6-7 x 9.7 km;
  - edge pixels are off by up to ~0.86 km;
  - pixel width is not constant: it grows from ~7 km at nadir to ~40 km at
    the swath edges.
- **Rebuilding also needs the neighbouring pixels**, which a left-out row or
  a partial file removes.
- So corners are only approximately recoverable. Storing them costs ~490 GiB
  for the two stores, (obs, 4) float32.

**Stored (19 sources, 17 stores).**

| source | shape | raw GiB | est. store GiB | notes |
| --- | --- | --- | --- | --- |
| `target_product/deltad` | obs float32 | 122 | 79 | stored as `water_vapor_column_delta_d` |
| `target_product/deltad_precision` | obs float32 | 122 | 79 | stored as `water_vapor_column_delta_d_standard_error` |
| `target_product/h2o_column` | obs float32 | 122 | 79 | stored as `water_vapor_column_h2o` |
| `target_product/h2o_column_precision` | obs float32 | 122 | 80 | stored as `water_vapor_column_h2o_standard_error` |
| `target_product/hdo_column` | obs float32 | 122 | 79 | stored as `water_vapor_column_hdo` |
| `target_product/hdo_column_precision` | obs float32 | 122 | 80 | stored as `water_vapor_column_hdo_standard_error` |
| `diagnostics/processing_quality_flags` | obs int32 | 122 | 5 | stored as `quality_flags_retrieval` |
| `diagnostics/iterations` | obs int32 | 122 | 12 | stored as `iterations_retrieval` |
| `instrument/solar_zenith_angle` | obs float32 | 122 | 100 | stored as `solar_zenith_angle` |
| `side_product/aerosol_optical_thickness` | obs float32 | 122 | 81 | stored as `optical_thickness_scattering_layer` |
| `side_product/aerosol_height` | obs float32 | 122 | 66 | stored as `height_scattering_layer` |
| `side_product/surface_albedo` | obs float32 | 122 | 84 | stored as `albedo_surface_2365nm` |
| `diagnostics/chi_squared` | obs float32 | 122 | 82 | stored as `chi_squared_retrieval` |
| `diagnostics/chi_squared_prefit` | obs float32 | 122 | 84 | stored as `chi_squared_prefit` |
| `diagnostics/number_of_spectral_points_in_retrieval` | obs int32 | 122 | 6 | stored as `spectral_point_count_retrieval` |
| `diagnostics/number_of_spectral_points_in_prefit` | obs int32 | 122 | 4 | stored as `spectral_point_count_prefit` |
| `instrument/latitude_center` | obs float32 | 122 | 101 | stored as geolocation `lat` |
| `instrument/longitude_center` | obs float32 | 122 | 101 | stored as geolocation `lon` |
| `instrument/time` | obs x 7 int32 | 852 | (in geolocation) | int64 ms in the store |

**1. Model comparison (named 2026-10-19; see Model-comparison variables).** Why: needed for model comparison; not built yet. The estimates below use the default zstd. The chosen blosc + shuffle brings the six to ~19 TiB.

| source | shape | raw GiB | est. store GiB | notes |
| --- | --- | --- | --- | --- |
| `target_product/h2o_column_averaging_kernel` | obs x 50 float32 | 5.9 TiB | 3.8 TiB |  |
| `target_product/hdo_column_averaging_kernel` | obs x 50 float32 | 5.9 TiB | 3.7 TiB |  |
| `target_product/h2o_profile_apriori` | obs x 50 float32 | 5.9 TiB | 5.5 TiB |  |
| `target_product/hdo_profile_apriori` | obs x 50 float32 | 5.9 TiB | 5.5 TiB |  |
| `meteo/dry_air_subcolumns` | obs x 50 float32 | 5.9 TiB | 5.4 TiB |  |
| `meteo/pressure_levels` | obs x 51 float32 | 6.1 TiB | 5.4 TiB |  |

**2. Not implemented by SRON (T11).** Why: the file says "Not implemented"; the information is in `processing_quality_flags`.

| source | shape | raw GiB | est. store GiB | notes |
| --- | --- | --- | --- | --- |
| `diagnostics/quality_flag` | obs int32 | 122 | 4 | constant 93 |
| `diagnostics/convergence` | obs int32 | 122 | 4 | constant 0 |
| `instrument/glintflag` | obs int32 | 122 | <1 | all fill in orbit 14069 |

**3. Redundant.** Why: SRON: "No added information compared to chi_squared".

| source | shape | raw GiB | est. store GiB | notes |
| --- | --- | --- | --- | --- |
| `diagnostics/chi_squared_band` | obs float32 | 122 | 82 |  |

**4. File bookkeeping.** `scanline` and `ground_pixel` **are stored** (2026-10-18) as `scanline_index` and `ground_pixel_index`. The other two are left out. See "Swath position" above.

| source | shape | raw GiB | est. store GiB | notes |
| --- | --- | --- | --- | --- |
| `instrument/scanline` | obs int32 | 122 | <1 | compresses to ~0 |
| `instrument/ground_pixel` | obs int32 | 122 | <1 | compresses to ~0 |
| `instrument/pixel_id` | obs int32 | 122 | 82 | row + 1 |
| `instrument/l1b_file` | 1 string per file | - | - | one string per file, not per obs |

**5. Pixel corners: stored** (2026-10-18) in the geolocation store as `lat_corners` and `lon_corners`, on `corner`, because they cannot be derived exactly from the centres. See "Pixel corners" above.

| source | shape | raw GiB | est. store GiB | notes |
| --- | --- | --- | --- | --- |
| `instrument/latitude_corners` | obs x 4 float32 | 487 | 248 |  |
| `instrument/longitude_corners` | obs x 4 float32 | 487 | 245 |  |

**6a. Viewing geometry.** Why: not a Table 1 filter input (only SZA is).

| source | shape | raw GiB | est. store GiB | notes |
| --- | --- | --- | --- | --- |
| `instrument/solar_azimuth_angle` | obs float32 | 122 | 105 |  |
| `instrument/viewing_azimuth_angle` | obs float32 | 122 | 104 |  |
| `instrument/viewing_zenith_angle` | obs float32 | 122 | 103 |  |

**6b. Meteorology.** Why: not a retrieval output or filter input.

| source | shape | raw GiB | est. store GiB | notes |
| --- | --- | --- | --- | --- |
| `meteo/altitude_levels` | obs x 51 float32 | 6.1 TiB | 618 |  |
| `meteo/landflag` | obs int32 | 122 | <1 | all fill in orbit 14069 |
| `meteo/skin_temperature` | obs float32 | 122 | 87 |  |
| `meteo/surface_altitude` | obs float32 | 122 | 13 |  |
| `meteo/surface_altitude_stdv` | obs float32 | 122 | 13 |  |
| `meteo/surface_pressure` | obs float32 | 122 | 85 |  |
| `meteo/temperature` | obs x 50 float32 | 5.9 TiB | 4.9 TiB |  |
| `meteo/u10` | obs float32 | 122 | 109 |  |
| `meteo/v10` | obs float32 | 122 | 111 |  |

**6c. CH4 and CO side products.** Why: CH4 only drives the cloud pre-fit; no Table 1 filter uses CH4 or CO.

| source | shape | raw GiB | est. store GiB | notes |
| --- | --- | --- | --- | --- |
| `side_product/ch4_column` | obs float32 | 122 | 75 |  |
| `side_product/ch4_column_apriori` | obs float32 | 122 | 85 |  |
| `side_product/ch4_column_prefit` | obs float32 | 122 | 67 |  |
| `side_product/ch4_profile_apriori` | obs x 50 float32 | 5.9 TiB | 5.5 TiB |  |
| `side_product/co_column` | obs float32 | 122 | 78 |  |
| `side_product/co_column_precision` | obs float32 | 122 | 78 |  |
| `side_product/co_profile_apriori` | obs x 50 float32 | 5.9 TiB | 5.5 TiB |  |

**6d. Other scattering-layer, albedo and fit parameters.** Why: only the retrieved optical thickness, height and 2365 nm albedo are filter inputs.

| source | shape | raw GiB | est. store GiB | notes |
| --- | --- | --- | --- | --- |
| `side_product/aerosol_geometric_thickness` | obs float32 | 122 | 4 | constant 2500 m |
| `side_product/aerosol_geometric_thickness_precision` | obs float32 | 122 | <1 | all fill in orbit 14069 |
| `side_product/aerosol_height_apriori` | obs float32 | 122 | 68 |  |
| `side_product/aerosol_height_precision` | obs float32 | 122 | <1 | all fill in orbit 14069 |
| `side_product/aerosol_optical_thickness_apriori` | obs float32 | 122 | 81 |  |
| `side_product/aerosol_optical_thickness_precision` | obs float32 | 122 | <1 | all fill in orbit 14069 |
| `side_product/surface_albedo_apriori` | obs float32 | 122 | 14 |  |
| `side_product/surface_albedo_precision` | obs float32 | 122 | 80 |  |
| `side_product/surface_albedo_prefit` | obs float32 | 122 | 87 |  |
| `side_product/surface_albedo_prefit_apriori` | obs float32 | 122 | 14 |  |
| `side_product/multiplicative_offset` | obs float32 | 122 | 4 | constant 1.0 |
| `side_product/spectral_shift` | obs float32 | 122 | 76 |  |

**6e. Remaining fit diagnostics.** Why: not filter inputs.

| source | shape | raw GiB | est. store GiB | notes |
| --- | --- | --- | --- | --- |
| `diagnostics/degrees_of_freedom_total` | obs float32 | 122 | 58 |  |
| `diagnostics/degrees_of_freedom_total_prefit` | obs float32 | 122 | 67 |  |
| `diagnostics/rms` | obs float32 | 122 | 81 |  |

## Appendix: defect files (audit of 2026-10-16)

The audit output itself is
`/glade/derecho/scratch/kheyblom/data/wisosat/audit/tropomi_files.jsonl`.
Scratch is purged, so the lists below are the durable copy.

### Corrupt upstream (3)

`YYYY/MM/DD/<orbit>`: `2018/06/05/3335`, `2019/04/17/7821`, `2019/04/19/7844`

### Shells (109): nothing written

As `YYYY/MM/DD/<orbit>` (declared rows):

```
2019/01/06/6380  (693,590)
2019/01/13/6481  (697,675)
2019/01/15/6517  (697,890)
2019/01/19/6576  (697,675)
2019/01/20/6581  (697,675)
2019/01/23/6628  (624,575)
2019/01/27/6682  (697,675)
2019/01/27/6683  (697,890)
2019/01/27/6685  (697,675)
2019/02/08/6851  (697,890)
2019/02/10/6877  (697,675)
2019/02/15/6960  (697,675)
2019/02/16/6963  (697,675)
2019/02/17/6985  (697,675)
2019/02/21/7033  (624,575)
2019/02/24/7080  (697,675)
2019/03/01/7147  (697,890)
2019/03/10/7281  (697,890)
2019/03/10/7282  (697,675)
2019/03/15/7351  (697,890)
2019/03/17/7383  (697,675)
2019/03/24/7480  (697,675)
2019/03/24/7482  (697,675)
2019/03/29/7549  (697,890)
2019/04/04/7632  (697,675)
2019/04/07/7675  (697,675)
2019/04/13/7757  (697,890)
2019/04/13/7764  (697,675)
2019/04/14/7776  (697,890)
2019/04/20/7858  (624,575)
2019/04/21/7882  (697,675)
2019/04/22/7884  (697,675)
2019/04/23/7910  (697,675)
2019/04/27/7955  (697,890)
2019/04/27/7959  (697,675)
2019/04/28/7976  (697,675)
2019/04/28/7980  (697,890)
2019/04/29/7983  (697,675)
2019/05/01/8016  (697,675)
2019/05/02/8025  (697,675)
2019/05/03/8041  (697,675)
2019/05/03/8042  (697,890)
2019/05/03/8046  (697,675)
2019/05/05/8078  (697,675)
2019/05/06/8083  (624,575)
2019/05/08/8115  (697,890)
2019/05/08/8122  (697,675)
2019/05/10/8147  (697,675)
2019/05/10/8150  (697,675)
2019/05/12/8180  (697,675)
2019/05/15/8217  (697,890)
2019/05/19/8279  (697,675)
2019/05/27/8381  (697,890)
2019/05/31/8443  (624,575)
2019/06/01/8453  (697,890)
2019/06/03/8482  (697,675)
2019/06/06/8522  (697,890)
2019/06/06/8529  (697,675)
2019/06/07/8539  (697,890)
2019/06/07/8547  (697,675)
2019/06/09/8575  (697,675)
2019/06/12/8608  (624,790)
2019/06/12/8609  (697,890)
2019/06/12/8615  (697,675)
2019/06/12/8619  (697,675)
2019/06/13/8623  (624,790)
2019/06/13/8626  (697,890)
2019/06/13/8632  (697,675)
2019/06/14/8639  (697,675)
2019/06/14/8642  (697,675)
2019/06/14/8647  (697,675)
2019/06/15/8649  (697,675)
2019/06/15/8650  (697,890)
2019/06/15/8653  (624,575)
2019/06/16/8664  (697,890)
2019/06/16/8668  (624,790)
2019/06/17/8684  (697,675)
2019/06/20/8720  (697,890)
2019/06/20/8721  (697,675)
2019/06/21/8741  (697,890)
2019/06/21/8742  (697,890)
2019/06/22/8762  (697,890)
2019/06/23/8764  (697,890)
2019/06/23/8773  (624,790)
2019/06/24/8783  (697,675)
2019/06/26/8811  (697,675)
2019/06/26/8819  (697,675)
2019/06/28/8837  (697,675)
2019/06/29/8848  (624,575)
2019/06/29/8857  (697,675)
2019/06/29/8858  (697,675)
2019/06/29/8861  (697,675)
2019/07/01/8880  (697,890)
2022/08/22/25171  (896,980)
2022/08/23/25185  (896,980)
2022/08/24/25192  (852,260)
2022/08/25/25209  (896,980)
2022/08/28/25255  (897,195)
2023/07/29/30009  (852,045)
2023/07/30/30022  (852,475)
2023/08/08/30157  (852,045)
2023/09/03/30522  (881,285)
2023/10/25/31257  (851,830)
2023/10/28/31300  (852,045)
2023/11/11/31494  (852,045)
2023/12/01/31779  (852,045)
2023/12/02/31790  (851,830)
2024/04/06/33587  (896,980)
2024/05/15/34132  (856,990)
```

### Partially processed (77)

As `YYYY/MM/DD/<orbit>`: processed rows kept of rows declared; pipeline variables unwritten (of 21).

```
2018/10/30/5420   13,975 of    13,975  (14 unwritten)
2019/01/20/6580   32,786 of   697,890  (10 unwritten)
2019/01/26/6671        3 of   697,890  (17 unwritten)
2019/01/27/6687        1 of   697,675  (17 unwritten)
2019/02/16/6961        3 of   697,675  (17 unwritten)
2019/02/17/6979   15,160 of   624,790  (14 unwritten)
2019/02/17/6980   34,435 of   697,675  (6 unwritten)
2019/03/03/7176   34,856 of   697,675  (10 unwritten)
2019/03/03/7178   34,869 of   697,890  (10 unwritten)
2019/03/03/7180   31,211 of   697,675  (14 unwritten)
2019/03/03/7182   34,888 of   697,675  (10 unwritten)
2019/03/16/7360   27,696 of   697,675  (14 unwritten)
2019/03/17/7384   35,303 of   697,675  (10 unwritten)
2019/03/24/7484        1 of   697,675  (17 unwritten)
2019/03/27/7517        1 of   697,675  (17 unwritten)
2019/03/31/7583        2 of   697,675  (17 unwritten)
2019/04/03/7617       15 of   697,675  (17 unwritten)
2019/04/06/7665        2 of   697,675  (17 unwritten)
2019/04/07/7678        1 of   624,575  (17 unwritten)
2019/04/10/7719   26,328 of   697,890  (14 unwritten)
2019/04/11/7739   26,586 of   697,675  (14 unwritten)
2019/04/13/7759    4,752 of   697,675  (14 unwritten)
2019/04/14/7782       48 of   459,240  (16 unwritten)
2019/04/18/7829   27,559 of   697,675  (14 unwritten)
2019/04/19/7853   27,778 of   697,675  (14 unwritten)
2019/04/20/7856   31,217 of   697,675  (14 unwritten)
2019/04/20/7868        1 of   697,675  (17 unwritten)
2019/04/23/7911        3 of   697,675  (17 unwritten)
2019/04/25/7934   18,990 of   697,890  (14 unwritten)
2019/05/01/8013   15,233 of   697,675  (14 unwritten)
2019/05/02/8026   36,379 of   697,675  (14 unwritten)
2019/05/02/8034   30,102 of   697,890  (14 unwritten)
2019/05/06/8085   37,683 of   697,890  (10 unwritten)
2019/05/07/8109        3 of   697,675  (17 unwritten)
2019/05/10/8149        2 of   697,675  (17 unwritten)
2019/05/12/8172        3 of   697,675  (17 unwritten)
2019/05/17/8238        1 of   697,675  (17 unwritten)
2019/05/18/8253        1 of   697,890  (17 unwritten)
2019/05/19/8277   38,468 of   697,675  (10 unwritten)
2019/05/20/8280   38,485 of   697,675  (10 unwritten)
2019/05/20/8283   38,468 of   697,675  (10 unwritten)
2019/05/23/8329        4 of   554,700  (15 unwritten)
2019/05/26/8378   39,348 of   697,890  (3 unwritten)
2019/05/27/8383        2 of   624,575  (17 unwritten)
2019/05/29/8421        1 of   697,675  (17 unwritten)
2019/05/30/8430        3 of   697,675  (17 unwritten)
2019/05/31/8439   39,350 of   697,675  (10 unwritten)
2019/06/03/8480        1 of   697,675  (19 unwritten)
2019/06/06/8523   39,886 of   697,675  (12 unwritten)
2019/06/06/8531        2 of   697,890  (17 unwritten)
2019/06/06/8532       10 of   697,890  (17 unwritten)
2019/06/07/8543        4 of   697,675  (17 unwritten)
2019/06/09/8576   40,032 of   697,675  (10 unwritten)
2019/06/10/8579        1 of   624,575  (17 unwritten)
2019/06/10/8581   40,101 of   697,675  (10 unwritten)
2019/06/12/8614        4 of   697,890  (15 unwritten)
2019/06/12/8618   40,309 of   697,675  (13 unwritten)
2019/06/13/8624   40,423 of   697,890  (10 unwritten)
2019/06/13/8628   27,625 of   697,675  (14 unwritten)
2019/06/13/8630        4 of   697,675  (15 unwritten)
2019/06/13/8634   40,202 of   697,675  (14 unwritten)
2019/06/14/8638        4 of   624,575  (15 unwritten)
2019/06/14/8640   40,316 of   697,675  (10 unwritten)
2019/06/16/8674        2 of   697,675  (19 unwritten)
2019/06/17/8681   10,585 of   697,675  (14 unwritten)
2019/06/20/8726        3 of   697,890  (19 unwritten)
2019/06/21/8736   31,862 of   697,890  (14 unwritten)
2019/06/22/8758   40,852 of   624,790  (10 unwritten)
2019/06/22/8759   40,632 of   624,575  (14 unwritten)
2019/06/24/8785   40,692 of   697,675  (10 unwritten)
2019/06/26/8808        2 of   697,890  (17 unwritten)
2019/06/26/8815   40,746 of   697,675  (10 unwritten)
2019/06/28/8840        4 of   697,675  (15 unwritten)
2019/06/29/8850   27,224 of   697,675  (14 unwritten)
2019/11/12/10784   17,415 of    17,415  (14 unwritten)
2021/12/11/21566    1,505 of     1,505  (14 unwritten)
2022/01/20/22141   24,510 of    24,510  (14 unwritten)
```
