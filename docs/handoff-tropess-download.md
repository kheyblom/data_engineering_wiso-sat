# Handoff: download the missing TROPESS AIRS and CrIS HDO data

For a separate data-access session (2026-10-22). The user wants every AIRS
and CrIS TROPESS HDO granule that is not already on disk, so that
`data_engineering_wiso-sat` can build zarr stores from them. That repo does
not download; this is the only job here. When done, report back as in
"What to hand back".

**Background:** read
`/glade/work/kheyblom/data_engineering/data_engineering_wiso-sat/docs/products/tropess.md`,
section "Collections: stream, product type, platform". It defines stream
(RS/FS), product type (Summary/Standard/Full) and the version tokens, and
lists every collection with what is on disk.

## Rules

- **Never modify, move, rename or delete anything already in the raw tree.**
  - The four existing download folders stay as they are, including the extra
    files they hold (L3 `AIRS_TROPESS_gridded_*`, and `*_target.nc` copies).
  - Never edit a netCDF file (no `ncks`). File names stay exactly as
    distributed.
- **HPC rules:** `~/.claude/CLAUDE.md` applies.
  - ~237 GB in ~12,100 files is heavy work: not on a login node. Use a batch
    job (or whatever data-transfer route the user prefers).
  - **Show the user any job script and its cost before submitting.**
  - Keep parallel connections few (e.g. 4).
  - Check the quota on `/glade/derecho/scratch` first.
- **Credentials:** GES DISC needs an Earthdata Login with the GES DISC
  application authorized (usually via `~/.netrc` and cookies). Never print,
  log or commit credentials.

## Where files go

Raw root: `/glade/derecho/scratch/kheyblom/data/wisosat/raw/`

- **One new folder per collection,** named by its `ShortName.version` as
  GES DISC names it, under the instrument folder, with **one subfolder per
  year** as in the GES DISC path. This keeps each folder under ~2,000 files.

  ```
  raw/AIRS/TRPSDL2HDOAIRSORS.1/2002/TROPESS_AIRS-Aqua_L2_Standard_HDO_20020830_MUSES_R1p6_RS_F0p8_J0.nc
  raw/CRIS/TRPSDL2HDOCRS1FS.2/2026/...
  ```

- **For the two partly held collections** (marked "missing only" below),
  download into the new folder only the file names that are not already in
  the existing folder. Compare exact file names, not dates.
  - For CrIS-JPSS1 FS Standard v1 that includes 5 upstream files that replace
    older local files for the same dates under a newer algorithm (R1p24).
  - Download those too, and keep the old ones. The build decides which to use
    (`tropess.md` R18).

Existing folders (do not touch):

| folder | collection | files |
| --- | --- | --- |
| `raw/AIRS/TRPSYL2HDOAIRSORS_1-20240806_185241/` | AIRS RS Summary v1 | 6,361 (complete) |
| `raw/AIRS/TRPSDL2HDOAIRSFS_1-20240912_174250/` | AIRS FS Standard v1 | 1,251 `TROPESS_*.nc`, plus 173 `*_target.nc` local copies and L3 files |
| `raw/CRIS/TRPSYL2HDOCRSRS_1-20240923_230130/` | CrIS-SNPP RS Summary v1 | 1,865 (complete) |
| `raw/CRIS/TRPSDL2HDOCRS1FS_1-20240912_023602/` | CrIS-JPSS1 FS Standard v1 | 1,208 |

## What to download

From NASA CMR on 2026-10-22. Sizes are CMR's (MB per granule, summed). The v2
collections are live and will have grown; take everything available and
record the cutoff.

| instrument | collection (`ShortName.version`) | CMR concept id | what | granules | ~size |
| --- | --- | --- | --- | --- | --- |
| AIRS | `TRPSDL2HDOAIRSORS.1` (RS Standard) | `C4169241979-GES_DISC` | all | 6,362 | 36.1 GB |
| AIRS | `TRPSYL2HDOAIRSFS.1` (FS Summary) | `C2247040242-GES_DISC` | all | 1,814 | 4.2 GB |
| AIRS | `TRPSYL2HDOAIRSFS.2` (FS Summary) | `C4173958791-GES_DISC` | all | 30+ | 0.1 GB |
| AIRS | `TRPSDL2HDOAIRSFS.1` (FS Standard) | `C2041965054-GES_DISC` | **missing only** | 564 | 30.8 GB |
| AIRS | `TRPSDL2HDOAIRSFS.2` (FS Standard) | `C4170965861-GES_DISC` | all | 30+ | 1.5 GB |
| AIRS | `TRPSFL2HDOAIRSFS.2` (FS Full) | `C4173720378-GES_DISC` | all | 30+ | 18.8 GB |
| CrIS-SNPP | `TRPSYL2HDOCRSFS.1` (FS Summary) | `C2247040372-GES_DISC` | all | 110 | 0.3 GB |
| CrIS-SNPP | `TRPSDL2HDOCRSFS.1` (FS Standard) | `C2041965312-GES_DISC` | all | 110 | 5.6 GB |
| CrIS-SNPP | `TRPSDL2HDOCRSAUS.1` (special collection, Australian fires) | `C2041965187-GES_DISC` | all | 91 | 0.8 GB |
| CrIS-JPSS1 | `TRPSYL2HDOCRS1FS.1` (FS Summary) | `C2247040357-GES_DISC` | all | 1,887 | 5.8 GB |
| CrIS-JPSS1 | `TRPSYL2HDOCRS1FS.2` (FS Summary) | `C4173959024-GES_DISC` | all | 138+ | 0.8 GB |
| CrIS-JPSS1 | `TRPSDL2HDOCRS1FS.1` (FS Standard) | `C2088007557-GES_DISC` | **missing only** | 684 | 36.5 GB |
| CrIS-JPSS1 | `TRPSDL2HDOCRS1FS.2` (FS Standard) | `C4170967256-GES_DISC` | all | 138+ | 9.7 GB |
| CrIS-JPSS1 | `TRPSFL2HDOCRS1FS.2` (FS Full) | `C4173720392-GES_DISC` | all | 137+ | 85.8 GB |

Totals: AIRS ~8,830 files and ~92 GB; CrIS ~3,295 files and ~145 GB.

- The two complete collections on disk (AIRS RS Summary, CrIS-SNPP RS Summary)
  need nothing; their file names match CMR exactly.
- Expected "missing only" contents:
  - **AIRS FS Standard v1:** 2023-07-21, 2023-10-19, and every day from
    2024-09-05 to 2026-05-31.
  - **CrIS-JPSS1 FS Standard v1:** 46 dates inside 2021-04-01 .. 2024-09-05,
    the 5 replacements, and the days after 2024-09-05.
- One file per date in every collection (checked 2026-10-22). Report it if
  that changes.

## How

- **Enumerate from CMR** rather than building URLs:

  ```
  https://cmr.earthdata.nasa.gov/search/granules.umm_json?collection_concept_id=<id>&page_size=2000&page_num=<n>&sort_key=start_date
  ```

  Each item's `umm.RelatedUrls` entry of type `GET DATA` is the HTTPS link.
  For example:

  ```
  https://data.gesdisc.earthdata.nasa.gov/data/TROPESS_Standard/TRPSDL2HDOAIRSFS.1/2026/TROPESS_AIRS-Aqua_L2_Standard_HDO_20260531_MUSES_R1p24_FS_F0p9_J1.nc
  ```

  `umm.DataGranule.ArchiveAndDistributionInformation[0].Size` is the size in
  MB.
- **Integrity:** CMR gives no checksums ("Name: Not provided"). For each file:
  - its size must be within rounding of CMR's;
  - it must open with h5py and have a readable `time` dataset;
  - its root `ShortName` and `VersionID` must match the collection.

  Re-fetch failures; report any that persist.
- **Manifest:** per collection, one CSV in its folder: file name, bytes, CMR
  size (MB), CMR `updated`, download time (UTC), URL. Also record the CMR
  query time, which is the cutoff for the live v2 collections.

## What to hand back

To the `data_engineering_wiso-sat` session, which updates `tropess.md` and
`STATE.md` from it:

- each new folder's path, with files downloaded vs CMR count, and the cutoff
  date for v2;
- the manifest paths;
- failures, gaps, and anything that differs from the table above: counts,
  new collections, dates with two files, or replaced granules.
