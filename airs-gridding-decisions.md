# AIRS gridding: decisions

*Started 2026-11-13. Moved here from a Claude Docs doc the same day.*

AIRS needs eight decisions before it can be gridded. Four of the method's
five inputs are missing for AIRS or don't mean the same thing as TROPOMI's.
Each section gives the facts, the options and a recommendation, and ends
with a **Your decision** line. Edit that line, or add `#@CLAUDE` comments
in place, and tell me in chat. Once a decision is agreed, it is recorded in
`docs/products/tropess.md` (a new "Gridding inputs" section) and in
`gridding/STATE.md` ("AIRS v1 decisions"). Only rules that hold for every
sensor go into `gridding/CLAUDE.md`.

**Where things stand.** Three AIRS L2 products are finalized under
`zarr/airs/l2/`:

- v1 RS: 2002-08-30 .. 2020-03-31, 17.1 M obs;
- v1 FS: 2021-02-01 .. 2026-05-31, 47.9 M obs;
- v2 FS: 2026-06, 1.0 M obs.

**Scope (user decision 2026-11-13): v1 only, RS and FS.** v2 is settled at
a later date. v2 facts below are kept for then; they do not drive any v1
decision.

There is no AIRS data from 2020-04 to 2021-01 (R1). The gridding engine is
built around TROPOMI: it uses footprint corners, a column δD, a noise-only σ
and an H2O column in mol m-2. The issue IDs (R1, Q2b, ...) refer to
`docs/products/tropess.md`.

## Decisions at a glance

| # | Decision | Recommendation | Status |
| --- | --- | --- | --- |
| D1 | Footprint model | C2: 1.1° FOV polygons (32 vertices) from the raw L2 geometry fields, validated once against L1B | **completed 2026-11-13**; validated against L1B the same day (1.4 revised: height from the orbit phase) |
| D2 | δD input | D + E: a vertical product, and an H2O-weighted 850-250 hPa δD from the profiles | **completed 2026-11-13** |
| D3 | σ input | None: no standard error and no σ sums | **completed 2026-11-13** |
| D4 | Weight | overlap area × H2O partial column of the gridded layer (mol), plus companion H2O statistics | **completed 2026-11-13** |
| D5 | Selection | `summary`: DOF > 1.1, or DOF missing and `dd_col_p` written; no cloud limit | **completed 2026-11-13** |
| D6 | Grid and frequency | 1° lat/lon, `day` only; other grids and frequencies on request | **completed 2026-11-13** |
| D7 | Day and night in RS | C: an all-overpass set and a daytime set (`v_1.rs.daytime`, `v_1.fs.daytime`), as separate stores | **completed 2026-11-13** |
| D8 | Products, and when to grid v2 | One gridded product per L2 product (RS, FS v1), each also as a daytime set (D7); v2 deferred | **completed 2026-11-13** (v1); v2 deferred |
| D9 | Gridded stores and names | 32 stores per set and layout: 14 column, 12 per level (with four sums beyond 2.7), 6 surface statistics | **completed 2026-11-14** (store set 2026-11-13; names approved 2026-11-14, style_guides `540b122`) |

## D1. Footprint model [COMPLETED 2026-11-13]

**Decided: C2, polygons (see the end of this section).** The first
recommendation was centre binning (option A), kept below for the record.

**Facts**

- The AIRS L2 stores hold only `time`, `lat` and `lon`. TROPESS publishes no
  corners, and `airs_view_ang` and `airs_xtrack` were left out of the L2
  stores (P3, Q4).
- The AIRS footprint is about 13.5 km at nadir (Sarkar et al. 2026,
  Table 2). It grows off-nadir, and the stores can't say by how much.
- TROPESS keeps about one target per 0.7° box per overpass. The median
  nearest-neighbour spacing is ~110 km in RS and 54-78 km in FS (R14).
- The drafting notes' rule of thumb (`notebooks/drafting/gridding-notes.md`):
  centre binning when cells are much larger than footprints, overlap when
  they are near the same size.

**Options**

| option | a retrieval is | needs | trade-off |
| --- | --- | --- | --- |
| A. Centre binning (recommended) | a point, in one cell | `lat`, `lon` | Sound at cells much larger than 13.5 km. Area statistics are undefined: coverage, footprint area, the footprint-to-cell ratio and Σa are not built. |
| B. Nominal 13.5 km circle | a polygon at every target | a fixed diameter | Keeps the overlap engine. The size is wrong off-nadir, so it adds precision the data doesn't have. At 1°, results are close to A. |
| C. Footprint sized by view angle | a polygon per target | `airs_view_ang` as a new L2 store, so additions to finalized stores | The most faithful option. It reopens the L2 stores and needs an AIRS FOV-shape model researched first. |

**Option C investigated (2026-11-13, at your request).** A polygon can be
built, but not from official information alone. At least one modelling step
remains that no AIRS or TROPESS document prescribes.

*What is verified*

- **Each retrieval is one AIRS footprint.** TROPESS uses single-footprint
  AIRS L1B radiances, not cloud-cleared 3x3 fields of regard
  ([TROPESS ATBD](https://docserver.gesdisc.eosdis.nasa.gov/public/project/TROPESS/TROPESS_ATBDv1.1.pdf)
  Table 2 and 3.5.1;
  [Worden et al. 2019](https://amt.copernicus.org/articles/12/2331/2019/amt-12-2331-2019.pdf);
  [Fu et al. 2018](https://amt.copernicus.org/articles/11/5587/2018/amt-11-5587-2018.pdf)).
- **Every raw AIRS file names that footprint**, in RS, FS v1 and v2 alike.
  The `geolocation` group has `airs_granule` (1-240), `airs_atrack` (0-134),
  `airs_xtrack` (0-89) and `airs_view_ang` (unsigned, degrees). v2 also has
  `l1b_filename`. None of these are in the L2 stores (P3, Q4). RS 2010-06-15
  uses only cross-track 36-75 (view angle ≤ 33.5°); v2 uses the full swath
  (≤ 49°).
- **Documented geometry:** 90 footprints per scan, each with a 1.1° FOV, a
  ±49.5° swath and a 705.3 km orbit. The footprint is 13.5 km at nadir and
  41 × 21.4 km at the scan edge
  ([README.AIRIBRAD](https://docserver.gesdisc.eosdis.nasa.gov/repository/Mission/AIRS/3.3_ScienceDataProductDocumentation/3.3.4_ProductGenerationAlgorithms/README.AIRIBRAD.pdf);
  [L1B ATBD](https://docserver.gesdisc.eosdis.nasa.gov/repository/Mission/AIRS/3.3_ScienceDataProductDocumentation/3.3.4_ProductGenerationAlgorithms/AIRS_L1B_ATBD_Part_1.pdf)).
- **My check:** a 1.1° cone from 705.3 km onto a sphere gives 13.5 km at
  nadir and 41.0 × 22.4 km at the outermost footprint (48.95°). That matches
  the README's figures, to 5% along-track.

*What is not settled*

- **No official polygon algorithm.** Neither AIRS nor TROPESS gives a
  formula for a footprint's ground outline. The
  [L1C guide](https://docserver.gesdisc.eosdis.nasa.gov/public/project/AIRS/V6.7_L1C_Product_User_Guide.pdf)
  gives the edge as ~20 × 30 km, which contradicts the README's
  41 × 21.4 km.
- **The real beam is not a cone.** JPL says it "is irregular and depends on
  the cross-track scan angle", and it changes by channel. JPL publishes
  spatial response functions per channel and footprint, in instrument angles
  ([JPL](https://airs.jpl.nasa.gov/mission/instrument-calibration/spatial-ancillary)).
  The fields of view are ~5% elliptical
  ([Yanovsky et al. 2024](https://airs.jpl.nasa.gov/internal_resources/580/Yanovsky2024_SPIE-AIRS-PSF-Uncertainties.pdf)).
  So a polygon needs a boundary we choose: the nominal 1.1° cone, or a
  contour of the response function for MUSES's HDO channels.
- **Inputs only in AIRS L1B:** the satellite position and height, `satazi`
  (the footprint's orientation), and the sign of the scan angle. The sign
  might follow from `airs_xtrack`, but that is inferred. L1B documents its
  indices as 1-based while TROPESS's are 0-based, so the mapping needs
  checking against L1B.
- **The JPL footprints page** (opened 2026-11-13;
  https://airs.jpl.nasa.gov/mission/airs-project-instrument-suite/footprints)
  describes how the beam is built: "The beam shape envelope 1.1° disk", "cut
  down to 0.6° in dispersion direction by the field stop", "rotated
  depending on scan mirror position" (45° at 45° scan), and "smeared out
  along the scan direction by 1.101°". At nadir (705.3 km) that gives a
  13.54 km disk with flat sides 7.39 km apart. With the smear, the envelope
  is "a 13.54 km × 20.94 km rectangle with slightly soft corners", while
  "At FWHM, the footprint is approximately a 13.5-km square". So there is no
  conflict with 13.5 km: 20.94 km is the outer envelope. The page gives
  shapes off nadir only in a figure, with no dimensions.

*C therefore splits in two*

| variant | geometry from | modelling step | cost |
| --- | --- | --- | --- |
| C1 | AIRS L1B geolocation for every granule holding a target (satellite position and height, `satazi`, `scanang`) | the footprint boundary (1.1° cone or a response-function contour) | A download of L1B geolocation for up to ~240 granules a day over ~8,200 days; whether a subsetting service can serve just those fields is still to check. Then new L2 stores (polygons) on the existing obs axis. |
| C2 | the L2 raw fields alone, with nominal 705.3 km and the orientation fitted from each granule's targets (lat/lon against `airs_atrack`/`airs_xtrack`) | the boundary, plus the fitted orientation and the nominal height | No download. The orientation fit is untested. New L2 stores as in C1. |

For scale: footprints are 13.5-41 km and a 1° cell is ~111 km. At 1°,
polygons change the result mainly for footprints near cell edges.

**Engine change for A:** a `centre` model in `gridding/utils/footprints.py`,
with its own independent version in the verifier. The reader then reads
`lat`/`lon` instead of corners. On EASE grids the centre is projected.

**Your decision (2026-11-13): C2.** Polygons built from the raw L2 fields
alone, with no L1B download for production.

**C2 sub-decisions (all recommendations approved 2026-11-13)**

| # | question | recommendation | why |
| --- | --- | --- | --- |
| 1.1 | The footprint boundary | the 1.1° circular FOV, projected from the satellite onto the ground | The only boundary the documents define at every scan angle ("1.1 degree diameter FOV", README; "envelope 1.1° disk", JPL). It reproduces the README's 13.5 km and 41 × 21.4 km. It ignores the field-stop cut and the scan smear, which JPL gives only at nadir and in a figure. The alternatives: JPL's nadir FWHM square (~27% more area than the disk), the smeared envelope (20.94 km wide at nadir, an outer bound rather than the footprint), or a contour of the measured response functions (it needs a contour level and a channel set, both our choice). |
| 1.2 | Where the scan plane lies on the ground (the cross-track direction at each target) | prototype two methods and keep the one that matches L1B (1.6): a fit within each granule of the targets' lat/lon against `airs_atrack`/`airs_xtrack`, and an orbit model (Aqua's inclination with the ascending or descending pass taken from the granule's latitude trend) | RS has only ~11 targets per granule, so the fit may be weak there. The orbit model needs only documented constants. |
| 1.3 | Which side of the track a target lies on (`airs_view_ang` is unsigned) | taken from `airs_xtrack` (0-44 and 45-89 lie on opposite sides), with the side's direction confirmed against L1B (1.6) | The L1B README numbers footprints from the left as seen along the satellite's path, 1-based; TROPESS's indices are 0-based. |
| 1.4 | Earth and orbit model | the WGS84 ellipsoid and the nominal 705.3 km altitude, both stated in the metadata | Footprint size scales with altitude, so a few km of altitude variation changes it by well under 1%. The L1B sample (1.6) measures this. |
| 1.5 | Polygon vertices | 32 points on the projected cone edge | A 32-gon misses 0.6% of the area (a 16-gon 2.6%, an 8-gon 10%). The engine's `MAX_VERTICES` (8, sized for quadrilaterals) becomes the vertex count + 4. AIRS is small (~30 M selected rows), so the cost is minor. |
| 1.6 | Validation | download a handful of AIRS L1B granules (an RS day and an FS day) and compare our polygons with polygons built from L1B's `satheight`, `sat_lat`/`sat_lon`, `satazi` and `scanang` | It confirms the orientation (1.2), the side (1.3) and the altitude (1.4) before production. It is a one-off check; production stays on L2 alone. The download is shown to you first. |
| 1.7 | Where the polygons are computed | L2 gains the four published geometry fields (`airs_granule`, `airs_atrack`, `airs_xtrack`, `airs_view_ang`) as new stores on the existing obs axis, as published; gridding computes the polygons (a footprint model `airs_fov`), and the verifier recomputes them independently | The same split as D2 (2.4): L2 keeps only published values, and derived ones are made in gridding. Storing derived polygons in L2 would be an exception to "as published". The four stores need nomenclature rows. |

**1.6 result: the prototype against L1B (2026-11-13).** Eight AIRIBRAD.005
granules (RS 2010-06-15: 126, 182, 235; FS 2022-06-01: 053, 115, 180; FS
2026-05-15: 193, 232), every target TROPESS retrieved in them (2,548).
Scripts `gridding/tools/survey/airs_fov_polygon.py` (the model and its
L2-only self-checks), `airs_l1b_fetch.sh` and `airs_fov_l1b.py`; output in
`gridding/logs/airs_fov_{polygon,l1b}_20261113.log`. The engine's own
module (`gridding/utils/airs_fov.py`, the code production runs) was checked
against the same granules on 2026-11-14, after its orbit-phase fit was
tightened: area 0.997-1.011 of L1B's, common area at least 0.987, the side
right on all 2,548 (`gridding/logs/airs_fov_engine_l1b_20261114.log`). The
granules (458 MB) were then deleted with the user's approval;
`airs_l1b_fetch.sh` fetches them again.

| sub-decision | result |
| --- | --- |
| 1.2 scan plane | **The orbit model, in the inertial frame.** One phase fit per file: u = u0 + k (n - n_mid), n = 135 (`airs_granule` - 1) + `airs_atrack`, fitted to the targets' latitudes for a circular orbit at 98.2° (residual at most 0.3°). The scan plane is perpendicular to the orbit's inertial heading: the bearing from each target to nadir is within 2.1° of L1B's `satazi` (p50 0.1-1.6° by granule). Perpendicular to the ground track it is off by up to 5.0°. The per-granule fit is off by up to 32° at high latitudes (and common area down to 0.68): not kept. L1B's roll, pitch and yaw are under 0.01°. `time` is not used: RS stores it in 64 s steps. |
| 1.3 side and indices | **Confirmed on all 2,548.** `airs_atrack` and `airs_xtrack` address L1B's arrays 0-based as they are (centres agree to 1e-5°; shifted by one they miss by 0.1-1.8°). `airs_view_ang` equals \|`scanang`\| exactly, and `scanang` is negative for `airs_xtrack` ≤ 44: the left of the flight direction. |
| 1.4 height | **Revised (user decision 2026-11-13): the height from the orbit phase**, not the nominal 705.3 km. L1B's `satheight` runs 705-720 km in 2010 and 2022 (higher in the south: a frozen orbit over an oblate Earth) and 692-700 km in 2026 (Aqua has descended ~15 km since its manoeuvres stopped). With 705.3 km, footprint areas are 0.950-1.048 of those drawn from L1B's satellite position (5% small in the southern mid-latitudes in 2022, 2-5% large in 2026). The height is now a (1 - e sin u) less the ellipsoid's radius under the satellite, with a = 7082.8 km × (k0 / k)^(2/3) (Kepler's third law on the fitted phase rate; k / k0 was 1.00001, 1.00012 and 1.00343 on the three days) and e = 0.0014, both constants read off the 2010 L1B granules and stated in the metadata. |
| polygons | **Chosen model against polygons drawn the same way from L1B's satellite position:** area 0.997-1.011 of L1B's (p50 1.000-1.001 per day), common area (intersection over union) at least 0.987, p50 0.997-0.998. |

Also measured from L2 alone (FS 2022-06-01, 8,032 scans holding two or more
targets): targets of one scan give the same sub-satellite point to a median
3.4 km (the satellite moves ~13 km while the mirror sweeps one scan line,
which the model leaves out: a 0.5° skew of the scan line).

**Knock-on effects:** with polygons, the area statistics come back
(coverage, footprint area, the footprint-to-cell ratio), and D4's weight is
overlap area × H2O partial column, in mol, as for TROPOMI. The L2 addition
(1.7) is an `l2/` task: new stores, verified, and a new tag on the AIRS v1
stores.

**Your decision:** C2, and 1.1-1.7 as recommended (2026-11-13).

## D2. δD: what is gridded [COMPLETED 2026-11-13]

**Decided (2026-11-13): two H2O-weighted δD products, both computed from the
17-level profiles.**

- **D2a, vertical:** δD and H2O on each retrieval level.
- **D2b, 850-250 hPa column:** the δD of each retrieval's HDO and H2O
  partial columns between 850 and 250 hPa, then gridded.

TROPESS's `dd_col_p` and `dd_col_p_error` (the 850-250 hPa fields) and
`dd_004` are not gridded. `dd_col_p` is an unweighted mean of the level
ratios: that mean reproduces it exactly on three files, RS 2010-06-15,
FS 2022-06-01 and v2 2026-06-01 (the file's own `source` attribute says
`np.mean(x_hdo[:] / x_h2o[:])`). An H2O-weighted mean differs from it
substantially:

| from the same levels (250 ≤ p < 850 hPa) | minus `dd_col_p`, p50 | p95 \|diff\| | max \|diff\| |
| --- | --- | --- | --- |
| unweighted mean of the ratio (TROPESS's `source`) | 0.000 ‰ | 0.000 ‰ | 0.000 ‰ |
| H2O-weighted, Σ R·q / Σ q | +56 to +59 ‰ | 104-107 ‰ | 163-227 ‰ |
| H2O × Δp weighted (HDO/H2O of the partial columns) | +56 to +58 ‰ | 103-106 ‰ | 166-225 ‰ |
| pressure-weighted, Σ R·Δp / Σ Δp | +5 to +6 ‰ | 10-14 ‰ | 27-39 ‰ |

**What the profiles give**

- **Coverage:** the ratio R (bias corrected), the H2O mole fraction q (dry
  air, 1e-6) and `pressure` are on 17 levels for every row. That includes
  the v1 Summary-only days: checked on RS 2020-03-31, 1,588 of 1,588 rows,
  where DOF is missing. The exception is v1 Standard row 0's R, masked
  (R22): one row per day.
- **Levels:** the grid levels are fixed pressures, 1000 to 0.1 hPa. The
  lowest valid level holds the surface pressure, and levels below the
  surface are fill (R10). 250-850 hPa usually spans 8 levels, and 5-9 over
  high ground.
- **MUSES forms columns hydrostatically.** v2's published `column_air`
  equals Δp/(g·M_air) to 0.3% (median ratio 1.003, p1-p99 0.999-1.013, all
  five column types, 2026-06-01). g and M cancel in a ratio of HDO and H2O
  columns, so a partial-column δD is Σ R·q·Δp / Σ q·Δp. Neither the ATBD nor
  the User Guides define the column operator further.
- **DOF:** about 1-2 per profile (v1 Summary rows have DOF > 1.1), so the
  levels are not independent, and some are mostly a priori.

**Sub-decisions (all recommendations approved 2026-11-13)**

| # | question | decision | why |
| --- | --- | --- | --- |
| 2.1 | Interpolation for the column integral | q (H2O) and R·q (HDO) each linear in ln p between levels (wording corrected 2026-11-13, below); layers cut exactly at 850 hPa, 250 hPa and the surface | Standard for mixing-ratio profiles. Exact cuts make D2b independent of where the levels fall. |
| 2.2 | Ratio to δD | δD = 1000 (R / 3.11e-4 − 1), TROPESS's constant | Matches TROPESS's own δD fields. VSMOW gives 3.1152e-4, which shifts δD by ~1.2 ‰. |
| 2.3 | D2b's name | `water_vapor_column_delta_d_850_250hpa`, a new row | The existing `water_vapor_delta_d_850_250hpa` means the unweighted mean (Q2b). D2b is a column average, so the grammar's `column` applies. |
| 2.4 | Where D2b is computed | in gridding, from the L2 stores, with the verifier recomputing it independently | The L2 stores stay as published, and nothing in L2 is rebuilt. |
| 2.5 | The surface level in D2a | the fixed levels gridded by level; the surface value gridded as its own field, with its pressure | One gridded level never mixes pressures. |
| 2.6 | Contents of D2a | per level: δD, H2O, count, the a priori δD and the kernel diagonal | Shows where the profile is retrieval and where it is prior. |
| 2.7 | D2a's sums | per level Σ w·δ, Σ w, Σ w·δ² and N, with w each footprint's H2O partial column in that level's layer (mol m-2) | The sums add over days, cells and levels, so a layer built from them is H2O-weighted. It matches D2b only where its edges fall on layer edges, and D2b is stored exactly anyway. |

**2.1, wording corrected (user decision 2026-11-13).** The row first read
"q and R linear in ln p", but the script behind the table below
(`gridding/tools/survey/airs_column_lnp.py`) interpolates q and R·q: the
H2O and HDO mole fractions, each linear in ln p. The user confirmed that
scheme. Read literally, "q and R" gives a column δD lower by a median
2.1-2.4 ‰ (p95 3.7-5.7 ‰, max 12-16 ‰; RS 2010-06-15, FS 2022-06-01). With q
and HDO, each layer's integral is exact and a column is a weighted sum of
the level values, so every level has a share of the H2O column and the
shares add to the column exactly (2.7's weights). The engine's operator is
`gridding/utils/columns.py`; it agrees with a 20,000-step integration to
1e-5 ‰.

**2.1, measured after approval.** The approved scheme (ln p interpolation,
exact cuts) against half-way thicknesses, on the same three files and every
row with `dd_col_p`:

| file | D2b δD p5 / p50 / p95 | approved minus half-way, p50 | p95 \|diff\| | max \|diff\| |
| --- | --- | --- | --- | --- |
| RS 2010-06-15 (2,019 rows) | -277 / -186 / -104 ‰ | -0.50 ‰ | 5.1 ‰ | 12.0 ‰ |
| FS 2022-06-01 (12,476) | -293 / -187 / -88 ‰ | -0.04 ‰ | 5.4 ‰ | 17.8 ‰ |
| v2 2026-06-01 (15,679, `quality == 1`) | -277 / -171 / -88 ‰ | -0.01 ‰ | 5.7 ‰ | 31.7 ‰ |

The two schemes agree in the median, and differ mainly where the 850 hPa cut
or the surface falls between levels. D2b sits ~60 ‰ above `dd_col_p`
(median -249, -249 and -231 ‰ on these files), as expected for an
H2O-weighted column.

**Knock-on effects**

- **D3:** there is still no valid σ, for a level or for the column.
- **D4:** w becomes the H2O partial column, as for TROPOMI, so equal weight
  is no longer the recommendation.
- **D5:** `dd_col_p` is not gridded, but it still marks the Summary-only
  rows, where DOF is missing (D5's rule).
- **Engine:** D2a adds a level dimension to the sums, stores, names and
  verifier. It is the largest engine change.

**Your decision:** D + E, and 2.1-2.7 as recommended (2026-11-13).

## D3. σ input [COMPLETED 2026-11-13]

**Recommendation (updated 2026-11-13 for D2): no σ for D2a or D2b.** The
standard-error stores and the two σ sums are not built. Spread and count
remain.

**Facts**

- `dd_col_p_error` no longer applies, because it belongs to the unweighted
  mean that D2 dropped. It is also -9999 on ~70% of the v1 rows where
  `dd_col_p` is written (R17).
- A σ for a level or for D2b would come from propagating an error covariance
  through the column operator. The covariance TROPESS publishes on every v1
  and v2 row is `observation_error`, which is not a valid covariance: it has
  negative variances and is asymmetric (R11). It was left out of the L2
  stores for that reason. v2's 17×17 observation-error blocks have the same
  defect.
- The method's σ is retrieval noise only. Only v2 Full publishes a
  noise-only (measurement) covariance:
  `characterization/hdo_hdo_measurement_error_covariance`, `h2o_h2o_...` and
  `hdo_h2o_...`. These are not in the L2 stores, and their validity has not
  been checked. v1 has no equivalent.
- The reader drops every row that is missing an input, so a σ written on
  only some rows would silently thin the grid.

**Options**

| option | effect | trade-off |
| --- | --- | --- |
| A. None (recommended) | no standard error in any AIRS product; spread and count remain | The same for v1 and v2. No retrieval-based uncertainty per cell. |
| B. Noise σ for v2 only, from the measurement covariance | a standard error in the v2 products | Deferred with v2 (scope). New L2 stores and a validity check first; v1 and v2 would then differ in what they carry. |
| C. From `observation_error` | — | Not workable: the covariance is invalid (R11). |

**Engine change for A:** σ becomes an optional input, and the set of stores
follows from the inputs the config names.

**Your decision:** A, no σ (2026-11-13). Documented in `docs/products/tropess.md` ("Gridding inputs, AIRS v1", R47) and `docs/technical/gridding-method.md` (Sections 2, 7, 10).

## D4. Weight [COMPLETED 2026-11-13]

**Recommendation (rewritten 2026-11-13 after D2): w = the H2O partial column
of the gridded layer, in mol m-2.** For D2b that is the 850-250 hPa column;
for D2a, each level's layer. If D1 chooses polygons, w is also multiplied by
the overlap area, giving mol, exactly as for TROPOMI.

**Facts**

- With D2's partial-column δD, the method's identity holds again: the
  H2O-weighted mean of the footprints' column δD equals the δD of their
  summed HDO and H2O columns.
- The H2O partial column comes from the same integral as D2b (2.1):
  ∫ q dp / (g·M_air). MUSES's `column_air` matches Δp/(g·M_air) to 0.3%
  (D2).
- g, and dry versus total air, cancel in the δD ratio, but not in the
  absolute H2O column. The choice changes the H2O column by up to a few
  percent in moist air. It matters only if the H2O column is stored as a
  statistic.

**Options**

| option | weight | trade-off |
| --- | --- | --- |
| A. H2O partial column (recommended) | moist footprints count more, as for TROPOMI | Needs g and an air-basis convention for the absolute column (below). |
| B. Equal weight | each retrieval counts once | A plain mean of column δD, which is no longer the δD of the cell's water. |

**Companion H2O statistics:** the mean H2O partial column (850-250 hPa,
mol m-2), and per level the mean H2O mole fraction (1e-6). They need new
rows, e.g. `water_vapor_column_h2o_850_250hpa`.

**Open with A:** the absolute-column convention. Proposed: g = 9.80665 m s-2
and dry-air molar mass, stated in the metadata, since TROPESS documents
neither. A latitude-dependent g changes columns by up to ~0.3%.

**Your decision:** A, with the companion H2O statistics and the proposed convention (2026-11-13). With D1's polygons, w = overlap area × H2O partial column, in mol, as for TROPOMI. Recorded in `docs/products/tropess.md` ("Gridding inputs, AIRS v1").

## D5. Selection [COMPLETED 2026-11-13]

**Recommendation (v1, revised 2026-11-13): TROPESS's Summary rule, DOF >
1.1, applied in two halves.** Keep a row if DOF > 1.1, or if DOF is missing
and `dd_col_p` is written (the Summary-only days). The same rule for RS and
FS. Whether to add a cloud limit is your call.

**Facts**

- v1 has no quality variable. The TROPESS README says Standard products
  already have quality flags applied, yet FS Standard DOF goes down to ~0
  (R9). Summary is exactly the Standard rows with DOF > 1.1 (Product
  scheme).
- **Checked on every v1 row (L2 stores at `v1-verified-20261023`,
  2026-11-13):**

  | | RS | FS |
  | --- | --- | --- |
  | rows | 17,109,546 | 47,882,856 |
  | DOF > 1.1 and `dd_col_p` written | 11,061,544 | 19,018,211 |
  | DOF > 1.1, no `dd_col_p` | 1,939 | 54,510 |
  | `dd_col_p` written, no DOF (Summary-only days) | 1,588 | 53,455 |
  | `dd_col_p` written and DOF ≤ 1.1 | 0 | 0 |
  | **kept by the recommended rule** | **11,065,071** | **19,126,176** |

  The 1,939 and 54,510 rows are expected to be the Standard-only days
  (RS 2, FS 6; R23), where `dd_col_p` is missing; the build will confirm
  that by date. A rule on `dd_col_p` alone would drop them, and a rule on
  DOF alone would drop the Summary-only rows.
- DOF and COD are NaN on v1 Summary-only days (R23), so a COD threshold
  drops those 55,043 rows.
- Five rows have DOF of exactly 1.1 at float32, and Summary leaves them out,
  so the comparison is strict (R31).
- TROPESS's pre-filter has no cloud check (User Guide 1.11).
- Recorded guidance, not a criterion: Sarkar et al. filter FS with DOF ≥ 1
  and COD ≤ 0.5. The User Guide's rule of thumb is DOFS > 0.7.
- Deferred with v2: v2 `quality == 1` reproduces v2 Standard exactly, and
  every such row has DOF > 1.1; DOF alone keeps 13-19% more rows (R41).

**Options** (a quality level in a new `gridding/products/tropess.py`)

| level | v1 rule | trade-off |
| --- | --- | --- |
| `summary` (recommended) | DOF > 1.1, or DOF missing and `dd_col_p` written | Every row TROPESS's Summary product would hold, plus the Standard-only days. |
| `summary` + COD ≤ X | as above, plus COD ≤ X | Adds a cloud screen. It drops the 55,043 Summary-only rows, and X needs choosing. |
| `dof` | DOF > 1.1 | Drops the 55,043 Summary-only rows. |

Thresholds are compared at the stored precision, and the rows are checked
for gaps between them (the TROPOMI T24 rule).

**Your decision:** `summary` as recommended, with no cloud limit (2026-11-13). Recorded in `docs/products/tropess.md` ("Gridding inputs, AIRS v1"). Confirmed by date on 2026-11-14 from the L2 stores: the DOF-only rows (RS 1,939, FS 54,510) are exactly the declared Standard-only days (RS 2002-08-30 and -31; FS 2021-02-12, 2024-02-07, 2024-08-05, 2025-01-12, 2025-01-24, 2025-03-05).

## D6. Grid and frequency [COMPLETED 2026-11-13]

**Recommendation: 1° lat/lon, with `day` and `month`.** The month grid is
the usable product, and the day grid lets users build their own composites.

**Facts**

- Retrievals per day after D5's selection (measured): RS 1,737 and FS v1
  10,440, over 6,372 and 1,832 observation days.
- RS covers only 50°S to 70°N (R34). FS reaches ~67°S to 85°N.
- Cell size barely changes the build's cost: AIRS v1 is ~30 M selected
  retrievals, against TROPOMI's 32.7 G.
- Rows for `day` and `month` already exist in the nomenclature. A lat/lon
  resolution must divide 180.

**Options** (measured 2026-11-13; corrected after your comment). Every v1
row passing D5, binned by its centre, over the whole record: RS 6,372 days and
209 months, FS 1,832 days and 61 months (months with at least 20 days of
data). Each cell is p50 over the periods, with p5-p95 in brackets. "Filled"
is the share of cells in the stream's latitude band (RS 50°S-70°N, FS
67°S-85°N) holding at least one retrieval; "per cell" is the retrievals in a
filled cell, p50 (mean). The earlier table assumed retrievals spread evenly
over the band: that gave the right average per band cell (RS ~1.2 at 1°) but
hid that many cells are empty and the rest hold more.

| grid | cells | RS day filled | FS day filled | RS month filled | RS month per cell | FS month filled | FS month per cell |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.25° (as TROPOMI) | 1,036,800 | 0.24% (0.19-0.34) | 1.1% (0.7-1.9) | 5.7% (4.7-8.0) | 1 (1.3) | 18% (13-26) | 1 (1.9) |
| 1° (recommended) | 64,800 | 3.8% (2.9-5.2) | 14% (9-21) | 57% (49-70) | 2 (2.1) | 66% (57-81) | 6 (8.3) |
| 2° | 16,200 | 9.3% (7.4-12) | 29% (21-41) | 78% (70-91) | 5 (6.2) | 72% (65-87) | 22 (30) |

- **A day** fills a few percent of cells at 1°, almost always with one
  retrieval each (RS mean 1.02, FS 1.34).
- **At 1°, the RS month leaves ~43% of band cells empty**, and a filled
  cell holds a median of 2 retrievals; FS holds a median of 6 (p95 26). At
  2°, RS fills 78% with a median of 5.
- These are centre counts. With D1's polygons a footprint (13.5-41 km)
  touches 1-4 cells, so fill rises a little, mostly at 0.25°.
- Some band cells are never sampled in a month for reasons other than cell
  size (box sampling, clouds, and the DOF > 1.1 selection), so even 2°
  stops short of full cover.

**Frequencies:** `day` and `month` at one grid gives 4 store sets
(2 frequencies × spatial and temporal). The engine reads each day once for
every grid and frequency, so adding 2° later is a config entry and a build.

**Your decision:** 1° lat/lon at `day` only (2026-11-13), as TROPOMI began (0.25° day). `month`, 2° and other grids are added on request: each is a config entry and a build, and a month's sums are its days' sums. Recorded in `docs/products/tropess.md` ("Gridding inputs, AIRS v1").

## D7. Day and night in RS [COMPLETED 2026-11-13]

**Decided (user, 2026-11-13): C, both, as separate store sets.** The first
recommendation (A, keep all) is kept below for the record.

**Facts**

- 55-57% of RS retrievals are at local night. FS is almost all daytime
  (~13:30 local), except at |lat| ~67-76° in summer (R13).
- RS fills 6-10x fewer 0.7° boxes per day than FS (R14).
- `day_night_flag` is -999 on 28 RS rows (R29).

**Options**

| option | effect | trade-off |
| --- | --- | --- |
| A. Keep all (recommended) | RS daily means mix ~01:30 and ~13:30 overpasses | A sampling seam at the RS-FS change, which is documented, not removed. |
| B. RS daytime only (`day_night_flag == 1`) | RS sampled like FS | About half of RS is lost. |
| C. Both, as two configs | the user chooses | Two RS store sets. |

**Your decision (2026-11-13): C.** Two RS store sets: every overpass, and
daytime only.

**Measured (2026-11-13):** the rows D5 selects, by `day_night_flag`
(TROPESS's `sunlit_binary_mask`; 1 sunlit, 0 not):

| | flag 1 | flag 0 | flag -999 | selected |
| --- | --- | --- | --- | --- |
| RS | 5,066,094 (45.8%) | 5,998,972 (54.2%) | 5 | 11,065,071 |
| FS | 18,423,705 (96.3%) | 668,400 (3.5%) | 34,071 (0.2%) | 19,126,176 |

The flag marks sunlight, not the overpass. In polar summer the night pass is
sunlit, and in polar night the 13:30 pass is dark. That is why FS, though
nearly all 13:30 passes (R13), has 3.5% flag 0.

**C sub-decisions (all recommendations approved 2026-11-13)**

| # | question | recommendation | why |
| --- | --- | --- | --- |
| 7.1 | How the daytime set is named | in the version slot: `wisosat.airs.v_1.rs.daytime.day.latlon_1p0x1p0.<variable>.zarr` (frequency `day`, set `daytime`)| The style guide puts a product name after the version, separated by a period (`v_3_5.nrt`), and `v_1.rs` already does. The daytime set is our selection rather than an upstream product, so this stretches the rule: it needs your approval (an exception for this collection). The alternatives are a qualifier on every variable name (a nomenclature row per store) or a separate directory with identical names (which collide once flattened). |
| 7.2 | What "daytime" means | `day_night_flag == 1`, as published; the flag -999 rows are left out of the daytime set and stay in the all-overpass set | The published flag needs no derivation. The alternative is the ascending (13:30) pass, derivable once D1's geometry stores exist (latitude against `airs_atrack` within a granule). That is closer to "sampled like FS" in local time, but derived, and it differs from the flag only at high latitudes. |
| 7.3 | A daytime FS set too | yes: `v_1.fs.daytime` beside `v_1.fs`   | Then the daytime record runs on one basis across the RS-FS change. It is cheap: it drops FS's 3.5% flag 0 and 0.2% flag -999 rows. Without it, RS daytime continues into an FS set that still holds polar-night rows. |
| 7.4 | The selection | a quality level `summary_daytime` in `products/tropess.py`: D5's `summary` rule and flag 1 | Every value falls in a row: `summary` holds all of `summary_daytime`, and the rows dropped from it are flag 0 or -999. |

**Your decision:** C, and 7.1-7.4 as recommended (2026-11-13). 7.1 is an approved style-guide exception for the AIRS v1 gridded stores only (the `daytime` token in the version slot); it is not carried to another product or collection without approval. Recorded in `docs/products/tropess.md` ("Gridding inputs, AIRS v1").

## D8. Products, and when to grid v2 [COMPLETED 2026-11-13 for v1]

**Decided (user, 2026-11-13): v1 only for now, as two gridded products (RS
and FS v1), one per L2 product as in L2. v2 is settled at a later date;
options B and C below are kept for then.**

**Facts**

- In L2, RS and FS stay separate products (user decision 2026-10-23), and
  v2 is a separate `v_2` store set. The gridded store names carry the L2
  version token, e.g.
  `wisosat.airs.v_1.rs.<frequency>.<grid>.<variable>.zarr`.
- v2 L2 holds 30 days (2026-06) at tag `v2-verified-20261028`, and later
  days get a new tag each time.
- A gridded store's last period can be partial, and extending it means
  rewinding that period first (`gridding/CLAUDE.md`). v2 (~1 M retrievals)
  is cheap to rebuild whole.

**Options**

| option | effect | trade-off |
| --- | --- | --- |
| A. v1 now, v2 later (**chosen**) | no rework while v2 grows | No gridded AIRS after 2026-05 for now. |
| B. All three now; rebuild v2 at each new L2 tag | complete now | A rebuild and re-finalize per append. |
| C. One gridded product joining FS v1 and v2 | a continuous FS record | It hides the sample change at 2026-06-01 (1.3-1.5x more targets) and breaks the one-L2-tag-per-store rule. |

**Your decision:** A, v1 only (RS and FS v1 as separate gridded products);
v2 deferred (2026-11-13).

## D9. Gridded stores and names [COMPLETED 2026-11-14]

*Added 2026-11-13.* D2 and D4 fix what is gridded; this section turns it
into stores, names and nomenclature rows. Nothing here is built or added to
style_guides until you approve it. Each store set (`v_1.rs`,
`v_1.rs.daytime`, `v_1.fs`, `v_1.fs.daytime`) gets the same stores, at
`day` on `latlon_1p0x1p0`, in `spatial/` and `temporal/`.

**Three groups of stores**

| group | what | dimensions |
| --- | --- | --- |
| column | the 850-250 hPa partial column (D2b) | (time, lat, lon) |
| levels | the 16 fixed pressure levels (D2a) | (time, level, lat, lon), `level` in Pa, surface first: 1000 to 0.1 hPa |
| surface | each retrieval's surface level, its lowest valid one (2.5) | (time, lat, lon) |

A fixed level counts for a retrieval only where it lies above that
retrieval's surface level, so the per-level count falls towards the
ground. The weight w is the overlap area times the H2O partial column of
the group's layer, in mol: 850-250 hPa for the column, the level's share of
the whole column for a level or the surface (`gridding/utils/columns.py`).

**Column group: 14 stores** (TROPOMI's 17 less the three σ stores)

| quantity | proposed store variable | units | row |
| --- | --- | --- | --- |
| δD, Σwδ / Σw | `water_vapor_column_delta_d_850_250hpa` | 1e-3 | new (2.3) |
| spread | `water_vapor_column_delta_d_850_250hpa_standard_deviation` | 1e-3 | new |
| mean H2O partial column, Σw / Σa | `water_vapor_column_h2o_850_250hpa` | mol m-2 | new (D4) |
| effective number | `observation_count_effective` | unitless | existing |
| count | `observation_count` | unitless | existing |
| coverage | `footprint_coverage` | unitless | existing |
| mean footprint area | `footprint_area` | km2 | existing |
| Σa | `footprint_overlap_area_sum` | km2 | existing |
| Σw, Σwδ, Σwδ², Σw², ΣwA, ΣwW | `gridding_weight_850_250hpa_sum`, `..._850_250hpa_delta_d_sum`, `..._850_250hpa_delta_d_squared_sum`, `..._850_250hpa_squared_sum`, `..._850_250hpa_footprint_area_sum`, `..._850_250hpa_footprint_weight_sum` | as TROPOMI's | 6 new |

The existing `gridding_weight_*` rows say "times its total column of water
vapor (H2O)", which is not this weight, so the sums need rows of their own.

**Levels group, per level** (2.6 lists the statistics, 2.7 the sums)

| quantity | proposed store variable | units | row | in 2.6 / 2.7 |
| --- | --- | --- | --- | --- |
| δD, Σwδ / Σw | `water_vapor_delta_d` | 1e-3 | new | 2.6 |
| a priori δD, Σwδa / Σw | `water_vapor_delta_d_apriori` | 1e-3 | existing | 2.6 |
| kernel diagonal, ΣwK / Σw | `water_vapor_hdo_h2o_ratio_averaging_kernel_log_diagonal` | unitless | new | 2.6 |
| H2O mole fraction, Σaq / Σa | `water_vapor_h2o_mole_fraction_dry_air` | 1e-6 | existing | 2.6, D4 |
| count | `observation_count_level` | unitless | new | 2.6, 2.7 |
| Σw | `gridding_weight_level_sum` | mol | new | 2.7 |
| Σwδ | `gridding_weight_level_delta_d_sum` | mol 1e-3 | new | 2.7 |
| Σwδ² | `gridding_weight_level_delta_d_squared_sum` | mol 1e-6 | new | 2.7 |
| Σwδa | `gridding_weight_level_delta_d_apriori_sum` | mol 1e-3 | new | **not in 2.7** |
| ΣwK | `gridding_weight_level_averaging_kernel_diagonal_sum` | mol | new | **not in 2.7** |
| Σa | `footprint_overlap_area_level_sum` | km2 | new | **not in 2.7** |
| Σaq | `footprint_overlap_area_h2o_mole_fraction_sum` | km2 1e-6 | new | **not in 2.7** |

**Question 9.1: the four sums 2.7 does not list.** 2.6's a priori δD,
kernel diagonal and H2O statistics cannot be formed again over a longer
period or a coarser grid without their own sums (Σwδa, ΣwK, Σa, Σaq).

| option | level stores | trade-off |
| --- | --- | --- |
| A. Add the four sums (recommended) | 12 | Every statistic follows from stored sums, as for TROPOMI (method Section 8). |
| B. 2.7 as written | 8 | A month's a priori, kernel diagonal and H2O must be regridded from L2, or approximated from the daily statistics. |

**Surface group.** The same quantities at each retrieval's surface level,
plus the mean surface pressure (Σw p_s / Σw).

**Question 9.2: how much of the surface group to store.**

| option | surface stores | trade-off |
| --- | --- | --- |
| A. Statistics only (recommended) | 6: δD, a priori δD, kernel diagonal, H2O mole fraction, count, surface pressure | The surface level's pressure differs between retrievals, so its sums add less cleanly than a fixed level's; the DOF there is low. Names take `_surface` (e.g. `water_vapor_delta_d_surface`, `pressure_surface`). |
| B. With every sum, as the levels | 14 | Re-aggregable like the levels; 8 more stores per set and layout. |
| C. None for now | 0 | 2.5 asked for the surface as its own field; this defers it. |

**Totals** per store set and layout, and over the 4 sets x 2 layouts:

| 9.1 | 9.2 | per set and layout | in all |
| --- | --- | --- | --- |
| A | A | 14 + 12 + 6 = 32 | 256 |
| B | A | 14 + 8 + 6 = 28 | 224 |
| A | B | 14 + 12 + 14 = 40 | 320 |

For scale: a level store is 16 x 180 x 360 cells a day, 6,372 days in RS
and 1,832 in FS, mostly empty cells (a day fills 4-14% of the 1° cells).

**Question 9.3: the counts' names.** The three groups share a directory,
so each count needs its own name. Proposed: `observation_count` for the
column group (footprints with an 850-250 hPa column, as TROPOMI's),
`observation_count_level` for the levels (footprints whose surface lies
below the level) and `observation_count_surface` for the surface group.

**Your decision (2026-11-13):** 9.1 A (the four sums added: 12 level
stores), 9.2 A (surface statistics only: 6 stores), so 32 stores per set
and layout, 256 in all. 9.3: the names are reviewed in style_guides: the 25
new rows were written there uncommitted on 2026-11-13
(`nomenclature_data.md`, the last 25 data-variable rows) and **approved as
proposed on 2026-11-14** (style_guides `540b122`). The surface names put `surface`
before the role, as `water_vapor_delta_d_850_250hpa_standard_error` does:
`water_vapor_delta_d_surface_apriori`,
`water_vapor_hdo_h2o_ratio_surface_averaging_kernel_log_diagonal`,
`water_vapor_h2o_mole_fraction_dry_air_surface`, `pressure_surface`.

## After the decisions

**With D2 agreed and the other recommendations as they stand, the engine
needs nine changes.** A rerun of the TROPOMI fixture must give the same
result as before, as the regression check. CrIS shares the TROPESS format,
so it should then need only a config. Its one extra decision is the SNPP
RS/FS overlap (R26).

| change | for | where |
| --- | --- | --- |
| Read 2-D L2 stores (ratio, H2O, pressure, a priori, kernel diagonal) and the v1 `dd_col_p` marker | D2, D5 | `utils/l2.py`, the verifier |
| Column operator: ln p interpolation with exact cuts at 850 hPa, 250 hPa and the surface, giving D2b and each level's layer H2O partial column | D2 (2.1, 2.7), D4 | a new `utils/columns.py`; a second, independent version in the verifier |
| A level dimension in the sums, stores and names, with the surface level as its own field | D2a (2.5-2.7) | `utils/sums.py`, `utils/stores.py`, `grid_wisosat.py`, `rechunk_wisosat.py`, the verifier |
| Footprint model `airs_fov`: 32-vertex polygons from the L2 geometry stores; `MAX_VERTICES` from the vertex count | D1 (C2; 1.1-1.7) | `utils/footprints.py`, the verifier; the four geometry stores in `l2/` |
| σ optional; the set of stores follows from the inputs | D3 | `utils/sums.py`, `utils/stores.py`, the verifier |
| Gridded names taken from each quantity, and new rows: D2b, per-level δD and H2O, the a priori, the kernel diagonal, companion H2O | D2 (2.3), D4 | `nomenclature-key_grid.md`, `utils/nomenclature.py`, `nomenclature_data.md` (your review) |
| TROPESS quality levels `summary` and `summary_daytime`; configs for the four store sets (`v_1.rs`, `v_1.rs.daytime`, `v_1.fs`, `v_1.fs.daytime`) | D5, D7 | `products/tropess.py`, the verifier's `SELECTIONS`, `config/airs_*/` |
| An AIRS fixture in the test | all | `validation/stage_fixture.py`, `validation/test_pipeline.py` |
| L2 read at a tag per store (the four footprint stores carry `v1-verified-20261113`, the rest `v1-verified-20261023`) | the L2 tag decision, 2026-11-13 | `utils/l2.py`, `utils/config.py`, the verifier |

**Order of work**

1. ~~Settle D1-D8 here (v1 only).~~ Done 2026-11-13.
2. ~~D1 prototype and validation: the polygon code against a handful of L1B
   granules (1.6), the download shown to you first.~~ Done 2026-11-13 (the
   1.6 result in D1; 1.4 revised to the height from the orbit phase).
3. ~~In `l2/`: the four AIRS geometry stores (1.7) for RS and FS v1, with
   their nomenclature rows, verified, and a new tag.~~ Done 2026-11-13:
   `granule_number_level_1b`, `scanline_index`, `ground_pixel_index`,
   `sensor_view_angle`; tag `v1-verified-20261113` on those four only (user
   decision), so gridding reads L2 at a tag per store.
4. ~~Write "Gridding inputs" in `docs/products/tropess.md`~~ (done
   2026-11-13). Add the vertical product, the column operator, the
   per-level sums and the `airs_fov` footprint to
   `docs/technical/gridding-method.md`. The AIRS decisions are in
   `gridding/STATE.md`; cut them there once the docs carry them.
5. Nomenclature rows in style_guides, shown to you before the commit.
6. Engine changes and the fixture test, committed from a clean tree.
7. ~~A one-month bench each for RS and FS v1, with the job shown to you first.~~
   Done 2026-11-14 (`gridding/TESTING.md`, "AIRS bench"): every check passes
   after both orbit-phase fits were made to run to the minimum.
8. Production for RS and FS v1, then verify, finalize (`--attrs`, `--tag`,
   `--gc`), rechunk and the temporal finalize, with your sign-off on every
   `--apply`.
