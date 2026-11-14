# Gridding Level 2 water-isotope retrievals

*Last edited: 2026-11-14 (profile sensors: Sections 1, 2, 5, 6, 7, 8, 10 and 11)*

This document describes how WISO-SAT Level 2 retrievals are averaged onto regular grids, by day or over
longer periods, and what each gridded quantity means. The method is the same for every sensor. What
differs between sensors (which variables supply each input, how a
footprint is defined, which observations are selected) is in that sensor's
product document under [`docs/products/`](../products/).

## Contents

1. [Overview](#1-overview)
2. [Inputs](#2-inputs)
3. [Grids](#3-grids)
4. [The day](#4-the-day)
5. [Assigning footprints to cells](#5-assigning-footprints-to-cells)
6. [Cell values](#6-cell-values)
7. [Uncertainty](#7-uncertainty)
8. [Combining cells and days](#8-combining-cells-and-days)
9. [Choosing a cell size](#9-choosing-a-cell-size)
10. [The gridded stores](#10-the-gridded-stores)
11. [Notation](#11-notation)
12. [References](#12-references)

## 1. Overview

Each footprint is treated as a polygon on the ground. It contributes to
every grid cell it overlaps, in proportion to the area it shares with that
cell multiplied by its H2O column. A cell's δD is the weighted mean over
all footprints that touch it during one period: a UTC day, or a
longer period made of whole UTC days ([Section 4](#4-the-day)). Its standard error comes
from the retrieval noise of those footprints.

Each cell keeps a set of weighted sums, and every cell value is computed
from them. The sums add exactly over days, and they can be added over any
set of cells to give a regional mean with bounds on its standard error
([Section 8](#8-combining-cells-and-days)).

Each grid is built directly from the Level 2 data. A coarse grid is never
derived from a finer one, so every cell value, including its standard
error, is exact at the grid's own cell size.

A sensor that retrieves profiles is gridded the same way three times over:
for a column between two pressures, for each fixed pressure level, and for
the surface level, each with the H2O partial column of its own layer as
the weight ([Section 2](#sensors-that-retrieve-profiles)).

## 2. Inputs

Every observation *f* supplies:

| input | symbol | meaning |
| --- | --- | --- |
| time | *t*_f | UTC time of the observation |
| footprint | — | the ground polygon given by the observation's corner coordinates |
| δD | δ_f | the retrieved δD, in 1e-3 (‰) |
| δD uncertainty | σ_f | the random (noise) part of the δD retrieval error, in 1e-3 |
| H2O column | *H*_f | the retrieved H2O column, in mol m-2 |

An observation is used only if it passes the selection applied before
gridding and all of these inputs hold values. A sensor with no valid
noise-only σ has no δD-uncertainty input at all: its grids carry no
standard error ([Section 7](#7-uncertainty)). The selection is the
product's quality level plus any product-specific thresholds. Each
product's selection, and the Level 2 variable behind each input, are in its
product document. The selection applied to a grid is recorded in its
attributes.

### Sensors that retrieve profiles

Some sensors publish HDO/H2O and H2O on vertical levels and no column δD
suited to an H2O-weighted mean. For them the inputs are computed from the
profiles when gridding (the Level 2 stores hold only published values).
Each retrieval gives three groups of inputs:

| group | δ_f | *H*_f |
| --- | --- | --- |
| column | δD of the HDO and H2O partial columns between two pressures | the H2O partial column between them, mol m-2 |
| level | δD at a fixed pressure level | the H2O partial column of that level's layer |
| surface | δD at the retrieval's surface level | the H2O partial column of that level's layer |

**Partial columns.** Between adjacent levels the H2O and HDO mole
fractions are each taken linear in ln *p*. A partial column is the integral
of the mole fraction over pressure between two pressures, divided by
*g* *M*: hydrostatic balance, with standard gravity (9.80665 m s⁻²) and the
molar mass of dry air (28.9644 g mol⁻¹). Each layer's integral is exact, and
the limits are exact too: a column from 850 to 250 hPa starts at 850 hPa
wherever the levels fall, or at the surface where the surface is higher.
*g* and *M* cancel in δD; they set only the H2O column itself.

**A level's layer.** The column integral is a weighted sum of the level
values. Each level's term in the integral of H2O over the whole profile is
the H2O partial column of that level's layer. These terms add up to the
whole column exactly, so the per-level sums of
[Section 6](#6-cell-values) combine over levels as they do over days.

**Fixed levels and the surface.** A retrieval's lowest level is its
surface, whose pressure differs from one retrieval to the next. It is
gridded as a group of its own, with its pressure. A fixed level is used for
a retrieval only where it lies above that retrieval's surface level, so one
gridded level never mixes pressures, and the count at a level falls towards
the ground.

A retrieval with no column between the two pressures is not gridded in any
group, so the three groups describe the same retrievals. Which sensors are
gridded this way, with their pressures and levels, is in the product
documents (AIRS v1: [`tropess.md`](../products/tropess.md), "Gridding
inputs, AIRS v1").

## 3. Grids

A gridded dataset uses one of two global grid types, at one cell size.

### Regular latitude-longitude

Square cells of side Δ degrees in latitude and longitude, where Δ divides
180°. Cell edges lie at −90° + *i*Δ in latitude and −180° + *j*Δ in
longitude. A cell includes its southern and western edges and excludes its
northern and eastern ones. The grid covers the whole globe.

A cell's area on a sphere of radius *R* = 6371 km is

$$
A_c = R^2 \, \Delta_\text{rad} \left( \sin\varphi_\text{north} - \sin\varphi_\text{south} \right),
$$

so cells shrink toward the poles as cos φ. A cell is about 111.2 Δ km
north-south and 111.2 Δ cos φ km east-west.

### EASE-Grid 2.0, global

NSIDC's global Equal-Area Scalable Earth grids (EPSG:6933; Brodzik et al.,
2012, 2014). The grid is a cylindrical equal-area projection of the WGS84
ellipsoid, true at ±30°, with square cells in projected metres:

- every cell has the same area, *s*², where *s* is the cell side;
- columns are evenly spaced in longitude, so cells narrow east-west toward
  the poles, as on a lat/lon grid;
- rows are evenly spaced in projected *y*, so cells lengthen north-south
  toward the poles. A cell is roughly *s* cos φ / cos 30° east-west by
  *s* cos 30° / cos φ north-south;
- the grid stops short of the poles. Footprints, or parts of footprints,
  poleward of its edge are not gridded.

The standard global grids form two families. A grid nests in another only
within its own family:

| family | cell side *s* (m) | columns × rows | cell area (km²) | latitude limit |
| --- | --- | --- | --- | --- |
| 36 km | 36,032.22 | 964 × 406 | 1,298.3 | ±85.04° |
| 9 km | 9,008.06 | 3,856 × 1,624 | 81.15 | ±85.04° |
| 3 km | 3,002.69 | 11,568 × 4,872 | 9.02 | ±85.04° |
| 1 km | 1,000.90 | 34,704 × 14,616 | 1.00 | ±85.04° |
| 25 km | 25,025.26 | 1,388 × 584 | 626.3 | ±84.44° |
| 12.5 km | 12,512.63 | 2,776 × 1,168 | 156.6 | ±84.44° |
| 6.25 km | 6,256.32 | 5,552 × 2,336 | 39.1 | ±84.44° |
| 3.125 km | 3,128.16 | 11,104 × 4,672 | 9.79 | ±84.44° |

Projected coordinates are computed in closed form on the WGS84 ellipsoid,
through the authalic latitude (Snyder, 1987).

### Comparing the two

Cell shape, east-west × north-south in km, for two pairs of similar size:

| latitude | 0.1° | EASE 9 km | 0.25° | EASE 25 km |
| --- | --- | --- | --- | --- |
| 0° | 11.1 × 11.1 | 10.4 × 7.9 | 27.8 × 27.8 | 28.8 × 21.8 |
| 30° | 9.6 × 11.1 | 9.0 × 9.0 | 24.0 × 27.8 | 25.0 × 25.1 |
| 60° | 5.6 × 11.1 | 5.2 × 15.6 | 13.8 × 27.8 | 14.5 × 43.0 |
| 80° | 1.9 × 11.1 | 1.8 × 44.5 | 4.8 × 27.8 | 5.2 × 119.1 |
| area (km²) | 124 cos φ | 81 | 773 cos φ | 626 |

At low and middle latitudes the two grid types behave alike at similar cell
sizes. At high latitudes they differ:

- **lat/lon** cells become small and thinly filled;
- **EASE** cells keep their area but grow long north-south, and the polar
  caps beyond the latitude limit are not covered.

## 4. The day

A daily grid for date *D* uses every selected observation whose UTC time
falls in [00:00, 24:00) UTC on *D*.

All of the day's observations of a cell are averaged together, whatever
the time between them:

- **Low and middle latitudes:** a polar-orbiting sensor usually sees a cell
  once a day, or on two consecutive orbits.
- **High latitudes:** a cell can be seen on several passes, hours apart.
  Its daily value then averages over those passes, which slightly damps
  its real day-to-day variability.

On the UTC day, the day's first and last orbits meet along a line of
longitude, where the date changes. Where they overlap, a cell joins
observations nearly 24 hours apart. Where this line falls depends on the
sensor's overpass time.

### Longer periods

A gridded dataset's period is a day, *n* days, a month or *n* months. A
longer period is made of whole UTC days, and its per-cell sums are its
days' sums added up ([Section 8](#8-combining-cells-and-days)), so its
values are exactly those of gridding all its observations at once.

Periods are consecutive blocks counted from 1 January 1900. An *n*-day
period is always exactly *n* days, and its boundaries fall on the same
dates for every sensor and every year. *n*-month periods start in January,
with *n* dividing 12 (three-month periods are January-March, April-June,
July-September and October-December). A period at either end of a
sensor's record holds only the days the record covers.

## 5. Assigning footprints to cells

### The footprint

A footprint is the polygon joining its corner points in order with straight
edges. The retrieved value is taken to hold uniformly over the polygon: every
point inside counts equally and nothing outside counts. Each sensor's
footprint definition is in its product document.

The polygon is drawn in the grid's own plane:

- on a **lat/lon** grid: (λ + 180°, φ + 90°), in degrees;
- on an **EASE** grid: projected metres.

A footprint whose corners span more than 180° of longitude crosses the
antimeridian. It is moved to one side of it, and the cells it covers past
±180° are wrapped back onto the grid. A footprint that still spans more than
90° of longitude after this encloses a pole and is not gridded. Nor is a
footprint with a missing corner.

A sensor that publishes no corners has its polygon drawn by a model of the
instrument's field of view, from published viewing geometry. The polygon
may then have many vertices (32 for AIRS); everything below applies
unchanged. The model, and what it was checked against, is in the product
document.

### Overlap with each cell

The polygon is clipped to every cell of its bounding box
(Sutherland and Hodgman, 1974), and the area of each clipped piece is taken
with the shoelace formula. Every cell with a positive overlap gets one
contribution from the footprint. A footprint's pieces add up to its whole
area.

Overlap areas are then converted to km², *a*_fc:

- on an **EASE** grid, the plane is equal-area, so the area in m² is exact;
- on a **lat/lon** grid, the overlap's share of its cell (degrees² over the
  cell's degrees²) is multiplied by the cell's true area *A*_c. This makes
  weights comparable between cells. Within one cell, a degree² is taken to
  cover the same ground everywhere. This is a small approximation, since
  cos φ changes across the cell. It matters only for coarse cells at high
  latitude.

Overlap never splits a footprint's value. Every cell the footprint touches
receives the same δ_f, σ_f and *H*_f, each carrying its own weight.

### Footprint area

Each footprint's whole area *A*_f, in km², is its shoelace area in the
EASE-Grid 2.0 global plane, which is equal-area on the WGS84 ellipsoid.
*A*_f is computed the same way whatever grid is being built, so it is
comparable between grids.

## 6. Cell values

### Weight

The weight of footprint *f* in cell *c* is its overlap area times its H2O
column:

$$
w_{fc} = a_{fc} \, H_f .
$$

In the stores, *w* is in mol: km² × 10⁶ m² km⁻² × mol m⁻², the moles of
water vapour the footprint puts in the cell. The unit cancels in every
statistic.

The footprint's total weight over the whole grid is

$$
W_f = \sum_c w_{fc} .
$$

With this weight, a cell's δD is the H2O-weighted mean of its footprints'
δD. If each footprint's δD is the ratio of its HDO and H2O columns, that
mean is the δD of the cell's summed HDO and H2O columns. A moist footprint
therefore counts for more than a dry one of the same area. The H2O column
is treated as exact: its own error is not propagated.

### Per-cell sums

For each cell, sums are taken over the footprints *f* that overlap it.
Writing *w* for *w*_fc:

| sum | used for |
| --- | --- |
| *N* = number of contributing footprints | count |
| Σ *a* | coverage, mean H2O column |
| Σ *w* | every weighted value |
| Σ *w* δ | δD |
| Σ *w* δ² | spread |
| Σ *w*² | effective number of footprints |
| Σ *w*² σ² | standard error |
| Σ *w* *A* | mean footprint area |
| Σ *w* *W* | effective number over a set of cells ([Section 8](#8-combining-cells-and-days)) |
| Σ *w* *W* σ² | standard error over a set of cells ([Section 8](#8-combining-cells-and-days)) |

Only cells with at least one contribution have values. All others are
missing.

**Levels.** For a sensor gridded from profiles
([Section 2](#sensors-that-retrieve-profiles)), the column group keeps the
sums above with δ and *H* the column's. Each fixed level keeps its own
sums, over the footprints that have that level, with *w* = *a* · *H* for
the level's layer: *N*, Σ *a*, Σ *w*, Σ *w* δ, Σ *w* δ², and one sum for
each further quantity averaged at the level (Σ *w* δa for the a priori δD,
Σ *w* *K* for the averaging kernel's diagonal, Σ *a* *q* for the H2O mole
fraction). A statistic at a level is its sum over Σ *w* (the H2O mole
fraction: Σ *a* *q* / Σ *a*, an area-weighted mean). Adding a level's Σ *w* δ
and Σ *w* over several levels gives the H2O-weighted δD of the layer they
span.

### Statistics

| quantity | formula | meaning |
| --- | --- | --- |
| δD | Σ *w* δ / Σ *w* | H2O-weighted mean δD of the footprints in the cell |
| spread | √(Σ *w* δ² / Σ *w* − δD²) | weighted standard deviation of the footprints' δD about the cell mean; 0 when one footprint contributes |
| standard error | √(Σ *w*² σ²) / Σ *w* | of the cell mean, from retrieval noise ([Section 7](#7-uncertainty)) |
| effective number of footprints | (Σ *w*)² / Σ *w*² | see below |
| count | *N* | footprints touching the cell, however little |
| mean H2O column | Σ *w* / Σ *a* | area-weighted mean H2O column, mol m-2 |
| coverage | Σ *a* / *A*_c | footprint area in the cell over the cell's area |
| mean footprint area | Σ *w* *A* / Σ *w* | weighted mean whole-footprint area, km² |
| footprint-to-cell ratio | mean footprint area / *A*_c | the scale the cell value represents, against the cell size |

How to read them:

- **δD** is a mean over the part of the cell the footprints saw, with each
  footprint's value spread evenly over its polygon.
- **Effective number of footprints** is the number of equally weighted
  footprints that would give the same precision. If all σ are equal, the
  standard error is σ / √*n*_eff. It is never more than the count, and it
  discounts footprints that only clip the cell's edge.
- **Coverage** adds up footprint areas, so it can exceed 1 where passes
  overlap. It is not the fraction of the cell that was observed: two passes
  over the same half of a cell give a coverage of 1.
- **Footprint-to-cell ratio** above 1 means the cell is smaller than the
  footprints behind it. Neighbouring cells then share footprints and repeat
  one another, and the cell value does not resolve detail at the cell's
  scale ([Section 9](#9-choosing-a-cell-size)).

## 7. Uncertainty

### What the standard error covers

The standard error of a cell's δD covers retrieval noise only (σ_f), and
assumes that different footprints' errors are independent. It excludes:

- **systematic error** (for example from clouds, aerosol, surface albedo,
  the a priori and spectroscopy), which averaging does not reduce;
- **sampling error.** Each satellite pass sees its own part of the cell,
  at its own viewing geometry and with its own mix of scenes. Two passes
  over the same cell can differ by much more than this standard error.
  A cell seen by one pass carries this error in full. A cell seen by
  several passes averages part of it away.

The standard error is therefore a lower limit on a cell's total
uncertainty. It falls as more footprints are averaged, and for coarse cells
it can become much smaller than the systematic error.

### Sensors without a standard error

A standard error is built only from a valid noise-only σ for every
retrieval. Where a sensor publishes none, its grids carry no standard error
and none of the sums that hold σ (Σ *w*² σ², Σ *w* *W* σ²). Every other
store is built as usual. A σ is never used on only some retrievals:
those without one would have to be dropped, which would change the grid.
The spread is not a substitute. It measures how much the retrievals in a
cell differ, which includes real variability, not the noise of their mean.
Which sensors have no standard error, and why, is in each product document
(AIRS v1: [`tropess.md`](../products/tropess.md), "Gridding inputs, AIRS
v1").

### Correlation between neighbouring cells

A footprint contributes to every cell it covers, so neighbouring cells
share footprints, and their errors are correlated. The correlation is
strongest:

- along the direction in which footprints are longest;
- where cells are smaller than the footprints (footprint-to-cell ratio near
  or above 1).

Each cell's standard error is correct on its own, and so is a single
cell's time series, since footprints never repeat across days. A mean over
several cells computed as if they were independent understates its standard
error. Use the sums in [Section 8](#8-combining-cells-and-days) for such
means.

### Averaging kernels

Grids do not carry averaging kernels. Applications that need them, such as
comparing with a model, should use the Level 2 averaging-kernel data.

The level stores of a profile sensor carry one number from the kernel: the
weighted mean of its diagonal at each level, beside the mean a priori δD.
Together they show where a level's δD comes from the measurement and where
it is mostly the a priori (a diagonal near 0). They are a guide to reading
the grid, not a kernel: the rows and the off-diagonal terms needed to
smooth a model profile are only in the Level 2 data.

## 8. Combining cells and days

### Over days

Each footprint belongs to exactly one day, so every per-cell sum adds
exactly over days. To get a cell value for a longer period (a month, a
season), add each sum over the days, then apply the formulas in
[Section 6](#6-cell-values). Do not average the daily cell values.

The same holds for the per-level sums of a profile sensor, level by level.
They also add over levels: Σ *w* δ and Σ *w* summed over several levels
give the H2O-weighted δD of the layer those levels span. The surface group
stores statistics only, so a longer period for it is gridded again from
Level 2, not combined from the daily stores.

### Over a set of cells

To get a mean over a set of cells *R* that is not itself a grid cell (a
basin, a mask, a latitude band), add each sum over the cells in *R*:

$$
\delta D_R = \frac{\sum_R \sum w\delta}{\sum_R \sum w} .
$$

Never average the cell δD values without their weights.

The exact standard error of this mean needs each footprint's total weight
inside *R*, which the cell sums do not hold once a footprint is split over
several cells. It is bounded instead:

$$
\frac{\sqrt{\sum_R \sum w^2\sigma^2}}{\sum_R \sum w}
\;\le\; \mathrm{SE}_R \;\le\;
\frac{\sqrt{\sum_R \sum w W \sigma^2}}{\sum_R \sum w} .
$$

- **The lower bound** is what treating the cells as independent gives.
- **The upper bound** holds because a footprint's weight inside *R* can
  never exceed its total weight *W*_f. It is exact for footprints wholly
  inside *R* and overstates only for those that straddle its boundary.

The bounds are tight when *R* is many footprints across, and loose when it
holds only one or two cells smaller than a footprint. The effective number
of footprints has the matching pair of bounds:

$$
\frac{\left(\sum_R \sum w\right)^2}{\sum_R \sum w W}
\;\le\; n_{\mathrm{eff},R} \;\le\;
\frac{\left(\sum_R \sum w\right)^2}{\sum_R \sum w^2} .
$$

These sums also add over days, so the same bounds apply to a region over
any period. Like the per-cell standard error, they cover retrieval noise
only.

### Between grids

Grids of different cell sizes or types are each built from the Level 2
data, not from one another. To compare resolutions, use each grid's own
values rather than coarsening a finer grid.

## 9. Choosing a cell size

Cell size is a choice of the dataset, not a property of the data. When a
daily cell is near or below the footprint size (footprint-to-cell ratio
near or above 1):

- a cell mostly holds one footprint, so the daily value gains little from
  averaging;
- neighbouring cells' errors become strongly correlated
  ([Section 7](#7-uncertainty));
- the map looks sharper than the footprints allow. Its true resolution is
  the footprint's, which varies across the swath and from day to day.

On a lat/lon grid these effects grow toward the poles as cells narrow. On
an EASE grid cells keep their area but grow long north-south. The
footprint-to-cell ratio and the effective number of footprints show, cell
by cell, where they apply.

## 10. The gridded stores

Each quantity is its own store. Every store of a dataset has the same grid,
period and time axis, in two layouts with the same values: one chunked for
maps (one period per chunk), one for time series (the whole record per
chunk of a small tile of cells).

| quantity | store variable | units | from the sums |
| --- | --- | --- | --- |
| δD | `water_vapor_column_delta_d` | 1e-3 | Σ *w* δ / Σ *w* |
| standard error | `water_vapor_column_delta_d_standard_error` | 1e-3 | √(Σ *w*² σ²) / Σ *w* |
| spread | `water_vapor_column_delta_d_standard_deviation` | 1e-3 | √(Σ *w* δ² / Σ *w* − δD²) |
| effective number of footprints | `observation_count_effective` | 1 | (Σ *w*)² / Σ *w*² |
| count | `observation_count` | 1 | *N* |
| mean H2O column | `water_vapor_column_h2o` | mol m-2 | Σ *w* / Σ *a* |
| coverage | `footprint_coverage` | 1 | Σ *a* / *A*_c |
| mean footprint area | `footprint_area` | km² | Σ *w* *A* / Σ *w* |
| Σ *a* | `footprint_overlap_area_sum` | km² | |
| Σ *w* | `gridding_weight_sum` | mol | |
| Σ *w* δ | `gridding_weight_delta_d_sum` | mol 1e-3 | |
| Σ *w* δ² | `gridding_weight_delta_d_squared_sum` | mol 1e-6 | |
| Σ *w*² | `gridding_weight_squared_sum` | mol² | |
| Σ *w*² σ² | `gridding_weight_squared_delta_d_variance_sum` | mol² 1e-6 | |
| Σ *w* *A* | `gridding_weight_footprint_area_sum` | mol km² | |
| Σ *w* *W* | `gridding_weight_footprint_weight_sum` | mol² | |
| Σ *w* *W* σ² | `gridding_weight_footprint_weight_delta_d_variance_sum` | mol² 1e-6 | |

A sensor without a valid σ has no standard error and no σ sums
([Section 7](#7-uncertainty)).

A sensor gridded from profiles ([Section 2](#sensors-that-retrieve-profiles))
has three groups of stores. Its column group is the table above, with the
column's pressures in the variable names and the weight's (for AIRS,
`water_vapor_column_delta_d_850_250hpa`, `gridding_weight_850_250hpa_sum`).
Its level stores have a `level` dimension after time, holding the fixed
pressures in Pa, surface first. Its surface stores are statistics only.
For AIRS v1:

| group | statistics | sums |
| --- | --- | --- |
| column (850-250 hPa) | δD, spread, effective number, count, mean H2O partial column, coverage, mean footprint area | Σ *a*, Σ *w*, Σ *w* δ, Σ *w* δ², Σ *w*², Σ *w* *A*, Σ *w* *W* |
| level (16 levels) | δD, a priori δD, kernel diagonal, H2O mole fraction, count | Σ *a*, Σ *w*, Σ *w* δ, Σ *w* δ², Σ *w* δa, Σ *w* *K*, Σ *a* *q* |
| surface | δD, a priori δD, kernel diagonal, H2O mole fraction, count, pressure | none stored |

The store variables are listed in the product document.

Every sum of [Section 6](#6-cell-values) is stored, in float64, so
[Section 8](#8-combining-cells-and-days) can be applied directly to the
stores; the statistics are float32. The mean H2O column is Σ *w* / Σ *a*
divided by 10⁶ when *w* is in mol and *a* in km². The footprint-to-cell
ratio is `footprint_area` over the `cell_area` coordinate.

- **Empty cells:** a cell no footprint touched has missing statistics, sums
  of 0 and a count of 0. A sum over no footprints is 0, so sums still add
  over days and cells.
- **Time:** each period is labelled by its first day, and `time_bounds`
  gives its first day and the day after its last.
- **Coordinates:** rows run north to south. A lat/lon grid's dimensions are
  `lat` and `lon`; an EASE grid's are its projected `y` and `x` (metres),
  with `lat` along `y` and `lon` along `x`. Both carry cell edges
  (`lat_bounds`, `lon_bounds`) and `cell_area` (km²).
- **Provenance:** each store records the Level 2 tag and snapshots it was
  made from, the selection, and the inputs.

## 11. Notation

| symbol | meaning | unit |
| --- | --- | --- |
| *f*, *c* | a footprint, a grid cell | |
| δ_f | footprint δD | 1e-3 |
| σ_f | footprint δD random uncertainty | 1e-3 |
| *H*_f | footprint H2O column | mol m-2 |
| *a*_fc | area footprint *f* shares with cell *c* | km² |
| *A*_f | footprint's whole area | km² |
| *A*_c | cell area | km² |
| *w*_fc | weight, *a*_fc *H*_f | mol (km² × 10⁶ × mol m-2) |
| *W*_f | footprint's total weight, Σ_c *w*_fc | mol |
| *N* | count of contributing footprints | |
| *R* | a set of cells | |
| *p* | pressure of a level; of the surface level in the surface group | Pa |
| *q* | H2O dry-air mole fraction at a level | 1e-6 |
| δa | a priori δD at a level | 1e-3 |
| *K* | diagonal of the averaging kernel of ln(HDO/H2O) at a level | |
| *g*, *M* | standard gravity, molar mass of dry air (partial columns) | m s⁻², kg mol⁻¹ |

For a profile sensor, δ_f and *H*_f are those of the group being gridded:
the column's, or a level's (its δD and the H2O partial column of its
layer).

## 12. References

- Brodzik, M. J., Billingsley, B., Haran, T., Raup, B., and Savoie, M. H.
  (2012). EASE-Grid 2.0: Incremental but significant improvements for
  Earth-gridded data sets. *ISPRS International Journal of
  Geo-Information*, 1, 32-45. <https://doi.org/10.3390/ijgi1010032>
- Brodzik, M. J., Billingsley, B., Haran, T., Raup, B., and Savoie, M. H.
  (2014). Correction: Brodzik, M. J., et al. EASE-Grid 2.0: Incremental
  but significant improvements for Earth-gridded data sets. *ISPRS
  International Journal of Geo-Information*, 3, 1154-1156.
  <https://doi.org/10.3390/ijgi3031154>
- Snyder, J. P. (1987). *Map Projections: A Working Manual*. USGS
  Professional Paper 1395. <https://doi.org/10.3133/pp1395>
- Sutherland, I. E., and Hodgman, G. W. (1974). Reentrant polygon
  clipping. *Communications of the ACM*, 17, 32-42.
  <https://doi.org/10.1145/360767.360802>
