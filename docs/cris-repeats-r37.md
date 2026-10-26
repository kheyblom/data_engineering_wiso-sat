# R37: CrIS rows repeated across days — outline for a decision

Written 2026-10-26 for the user's review, in place with `#@CLAUDE` comments
(as `docs/model-comparison-naming.md` was). Nothing is built until the user
decides. Evidence: TESTING.md finding 16, `tropess.md` R37; the probes ran on
the login node and are described under "How it was measured".

## What happens

A TROPESS CrIS file is a **processing day, not an observation day**. A JPSS1
FS "day" file typically holds rows from ~11 h before its date to ~34 h after
it (at most the full 48 h either side); SNPP FS is the same; SNPP RS files
mostly sit on their day, but 1,254 of 1,865 start early. So consecutive
files' time windows overlap heavily, and a small share of footprints is
delivered in two files.

A **repeat** is a row with exactly the time, latitude and longitude of a row
in an earlier file. Every repeat checked also has the same CrIS granule,
along-track, cross-track and field-of-view indices: it is the same
footprint, observed once.

| product | repeated rows (vs the day before) | vs two days before | share of rows | days with any |
| --- | --- | --- | --- | --- |
| SNPP RS (Summary only) | 620 | 0 | 0.02% | 417 of 1,865 |
| SNPP FS Standard | 8,057 | 0 | 0.28% | 106 of 110 |
| JPSS1 FS Standard | 136,702 | 21 | 0.29% | 1,476 by 2025-06-18 (not counted after) |

- **No file repeats a row within itself**, in any product.
- **The Summary rows follow their Standard rows** (Summary is the DOF > 1.1
  subset of each file): SNPP FS 2,797 and JPSS1 72,574 (+19) Summary rows are
  repeats. Under the merge they are not separate decisions.
- **Positions:** repeats lie anywhere in both files (from either end p50
  ~1,500-4,700 rows), in short runs (1,816 sampled JPSS1 repeats form 772
  runs), not one block at a seam. Their times spread over both days.
- **Through the whole record:** JPSS1 has 8,000-29,000 a year from 2021 to
  2026-05.

## How the two copies compare

Every per-target dataset compared (sampled pairs: SNPP RS every day with a
repeat; SNPP FS every 10th-20th day; JPSS1 every 80th-160th):

| class | SNPP RS | SNPP FS | JPSS1 FS |
| --- | --- | --- | --- |
| **A. identical in every dataset** | 42 of 620 (7%) | 684 of 833 (82%) | 441 of 1,003 (44%) |
| **B. same retrieval, errors differ** | — | 145 (17%) | 551 (55%) |
| **C. different retrieval** (`x` etc. differ) | 578 (93%) | 4 (0.5%) | 11 (1%); all 138 at one algorithm change |

- **Class B, JPSS1:** the only difference is `observation_error_h2o` at
  levels **below the surface** (where `x` is fill; R15). Those values have
  no meaning, so the copies agree on everything meaningful, but they are
  not bit-identical as stored, since that variable is stored with its
  below-surface values.
- **Class B, SNPP FS (R1p11, R1p12):** `observation_error` and
  `observation_error_h2o` differ **at every level**, by ~5-20% on
  `observation_error_h2o`, while `x`, the kernel, DOF and prior are
  bit-identical. Two error estimates for one retrieval; which is right is
  not knowable from the files.
- **Class C:** the footprint was retrieved twice. In SNPP RS `x` differs by
  p50 0.04%, p90 0.6%, max 6%; in JPSS1 up to ~24%. At algorithm changes
  (e.g. R1pN in one file, R1pN+1 in the next) every repeat is class C.
- Neither copy's error row appears at any other row of either file: these
  are not misaligned rows.

## What the build does today

`check_repeats` (the stand-in for the time-order check under
`time_order: source`, R32) fails on any observation that shares time, lat and
lon with one of its own granule or **the granule before**. The first CrIS
build would stop on 2015-12-03 (SNPP RS) or 2021-04-02 (JPSS1). It would not
see the 21 JPSS1 rows that repeat a row two days back.

## The options

All three keep rows in source order, keep the granule index's
`granule_source_rows` as each file's own count, and are confirmed from raw by
both the build and the verifier (as every rule here is).

### 1. Keep every row

The stores hold what the files hold, so ~0.3% of footprints appear twice.

- **Code:**
  - a config key, e.g. `repeats_across_granules: allowed` with a reason, lets
    `check_repeats` pass repeats across granules for CrIS. Repeats within a
    granule still fail;
  - the check looks back a declared number of granules (2 for JPSS1) and
    requires every repeat to be the same footprint (CrIS indices equal), so a
    duplicated or misfiled file still fails;
  - the build records the count per granule in the index (`INDEX_EXTRA`,
    e.g. `granule_repeated_rows`); the verifier recounts from raw.
- **Metadata:** each store says repeats exist, how many, and that users who
  grid or average should de-duplicate on time, lat and lon (or use the
  index).
- **For:** no observation is selected, so no exception to the style guide;
  classes B and C keep both versions; the simplest code.
- **Against:** users who grid without de-duplicating count ~0.3% of
  footprints twice (SNPP RS: 0.02%). The repeat check's power across seams is
  narrowed for CrIS to "same footprint".

### 2. Leave out exact copies only (class A)

As SCIAMACHY S8 (identical copies left out, the first kept): a row bit-identical
in every stored source to one already stored is left out; classes B and C are
kept, as under option 1.

- **Code:** option 1's allowance for B and C, plus a leave-out rule. Under
  "declared, never detected", the copies would be declared per granule (a
  generated list of ~1,700 JPSS1 granules with their counts, in a file beside
  the config) and the build and verifier would confirm each count exactly.
- **For:** removes the plain duplicates; follows the S8 precedent.
- **Against:**
  - most JPSS1 copies (class B) are not bit-identical because of the
    below-surface `observation_error_h2o`, so only ~44% would go;
    widening "identical" to ignore below-surface values is a judgement about
    data meaning that the pipeline has avoided;
  - the store still has repeats, so users still need to de-duplicate;
  - the most code, and a large declared list.

### 3. Leave out every repeat (keep the first occurrence)

- **Code:** a declared rule per product, confirmed from raw: rows whose time,
  lat and lon match an earlier granule's (within the declared look-back) are
  left out, and the store's footprints are unique. `check_repeats` then runs
  unchanged, with the look-back widened to 2.
- **For:** every footprint once; users can grid directly.
- **Against:**
  - it selects observations: class C rows are different retrievals (93% of
    SNPP RS's repeats), and class B keeps only the first error estimate. This
    is S9's kind of exception, which was declared one-time, not a precedent;
  - "keep the first" is arbitrary at algorithm changes, where the later copy
    is the newer algorithm.

### Option 3 with the newest copy kept (asked by the user, 2026-10-26)

Measured over every repeat (look-back 3 files; none at 3), with each file's
algorithm and root `ProductionDateTime`:

| product | repeats | across an algorithm change | same algorithm |
| --- | --- | --- | --- |
| SNPP RS | 620 | 0 | 620 |
| SNPP FS | 8,057 | 0 | 8,057 |
| JPSS1 FS | 136,723 | 3,771 (later file newer 2,115; earlier file newer 1,656) | 132,952 |

- **The algorithm alone resolves 3,771 of 145,400 repeats (2.6%).** The
  algorithm changes at a repeat almost only where an R1p24 backfill file (R18)
  sits among R1p15 .. R1p23 days, so it alternates in both directions.
- **`ProductionDateTime` resolves the rest:** within one algorithm the two
  files never share a production time; the later-dated file was produced
  later for 131,855 JPSS1 rows (and every SNPP row), earlier for 1,097.
- **So "newest algorithm, then latest production" picks exactly one copy of
  every repeat**, and every footprint is stored once.
- **Build consequence:** the copy kept is often in the later file, so the
  build must look ahead up to two files before writing a granule (its keys
  and attributes only); the verifier repeats the selection from raw.

## Recommendation

**Option 1, keep every row**, with the same-footprint condition and the
per-granule count in the index. It is the only option that selects nothing,
the classes B and C mean no simple rule separates "copies" from "new
retrievals", and de-duplicating on time, lat and lon is one line for a user,
with the count in the metadata telling them when they need to.

If the user prefers unique footprints in the stores, option 3 is cleaner than
option 2: option 2 adds the most machinery and still leaves repeats.

## How it was measured (2026-10-26, login node, scripts not kept)

- The audit's per-file first and last row times (finding 16).
- Every consecutive pair of files of each product and type, time, lat and lon
  only, with a look-back of 3 files: the counts above (~8 min).
- A first pass that also compared seven variables, cut off at JPSS1
  2025-06-18 when the session ended; superseded by the two passes here.
- Sampled pairs, every per-target dataset compared, runs and CrIS indices:
  the class table (~4 min). Error-only rows were then checked for misaligned
  rows and for the levels that differ.
