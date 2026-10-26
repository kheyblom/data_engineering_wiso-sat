# Raw data coverage by sensor

The first and last dates of the Level 2 files on disk under
`/glade/derecho/scratch/kheyblom/data/wisosat/raw/`, checked 2026-10-26.
These are what is downloaded, not what has been built: a sensor's stores may
cover less (see each product's doc in `docs/products/`).

Dates come from file names (GOSAT, TROPESS, IASI, TES) or folder names
(TROPOMI `YYYY/MM/DD`). SCIAMACHY's file names carry only orbit numbers, so
its dates are the decoded `instrument/time` of the first and last files. TES
files are monthly, so its dates are months. A span is first to last file;
it does not mean every day in between has a file.

## Summary

| sensor | start | end | granule | notes |
| --- | --- | --- | --- | --- |
| AIRS (TROPESS) | 2002-08-30 | 2026-06-30 | day | RS to 2020-03-31, then a gap; FS from 2021-02-01 |
| SCIAMACHY (SRON SICOR) | 2003-01-11 | 2012-04-08 | orbit | 112 `YYYYMM` folders, 200301 .. 201204 |
| TES (L2 HDO Nadir Lite v006) | 2004-09 | 2010-12 | month | 75 files (2005 has 11 months); 2011-2015 absent (E5) |
| GOSAT (IUP FOCAL v3.0.1) | 2009-04-23 | 2021-12-31 | day | 4,498 days, each with DED and H2O files |
| IASI (KIT MUSICA L2pp) | 2014-10-01 | 2020-12-31 | half day | 4,568 files, morning and evening |
| CrIS-SNPP (TROPESS) | 2015-12-01 | 2021-05-21 | day | RS Summary only, then FS 2021-02-01 .. 2021-05-21 |
| TROPOMI (SRON HDO, proc. 8.1) | 2017-11-08 | 2025-11-29 | orbit | first orbit 00373, last 42131 |
| GOSAT-2 (IUP FOCAL v3.0.1) | 2019-02-05 | 2021-12-31 | day | 1,010 days, each with DED and H2O files |
| CrIS-JPSS1 (TROPESS) | 2021-04-01 | 2026-10-17 | day | the v2 collections run from 2026-06-01 |

## TROPESS collections

AIRS and CrIS come in several collections per stream and version. A
collection's dates are its first and last file.

| sensor | collection | type | start | end |
| --- | --- | --- | --- | --- |
| AIRS | `TRPSYL2HDOAIRSORS_1-20240806_185241` | RS Summary | 2002-09-01 | 2020-03-31 |
| AIRS | `TRPSDL2HDOAIRSORS.1` | RS Standard | 2002-08-30 | 2020-03-30 |
| AIRS | `TRPSYL2HDOAIRSFS.1` | FS Summary | 2021-02-01 | 2026-05-31 |
| AIRS | `TRPSDL2HDOAIRSFS_1-20240912_174250` | FS Standard | 2021-02-01 | 2024-09-04 |
| AIRS | `TRPSDL2HDOAIRSFS.1` | FS Standard | 2023-07-21 | 2026-05-31 |
| AIRS | `TRPSYL2HDOAIRSFS.2` | FS Summary, v2 | 2026-06-01 | 2026-06-30 |
| AIRS | `TRPSDL2HDOAIRSFS.2` | FS Standard, v2 | 2026-06-01 | 2026-06-30 |
| AIRS | `TRPSFL2HDOAIRSFS.2` | FS Full, v2 | 2026-06-01 | 2026-06-30 |
| CrIS-SNPP | `TRPSYL2HDOCRSRS_1-20240923_230130` | RS Summary | 2015-12-01 | 2021-05-21 |
| CrIS-SNPP | `TRPSYL2HDOCRSFS.1` | FS Summary | 2021-02-01 | 2021-05-21 |
| CrIS-SNPP | `TRPSDL2HDOCRSFS.1` | FS Standard | 2021-02-01 | 2021-05-21 |
| CrIS-SNPP | `TRPSDL2HDOCRSAUS.1` | Standard, special collection (`SC_AUS`) | 2019-11-01 | 2020-01-31 |
| CrIS-JPSS1 | `TRPSYL2HDOCRS1FS.1` | FS Summary | 2021-04-01 | 2026-05-31 |
| CrIS-JPSS1 | `TRPSDL2HDOCRS1FS_1-20240912_023602` | FS Standard | 2021-04-01 | 2024-09-05 |
| CrIS-JPSS1 | `TRPSDL2HDOCRS1FS.1` | FS Standard | 2021-05-21 | 2026-05-31 |
| CrIS-JPSS1 | `TRPSYL2HDOCRS1FS.2` | FS Summary, v2 | 2026-06-01 | 2026-10-17 |
| CrIS-JPSS1 | `TRPSDL2HDOCRS1FS.2` | FS Standard, v2 | 2026-06-01 | 2026-10-17 |
| CrIS-JPSS1 | `TRPSFL2HDOCRS1FS.2` | FS Full, v2 | 2026-06-01 | 2026-10-15 |

- The AIRS gap, 2020-04 .. 2021-01, is not on disk (flagged, not chased).
- The v1 production configs end at 2026-05-31; the `.2` collections (v2,
  R1p25) are later downloads. The v2 CrIS ends here are a day later than
  `docs/products/tropess.md` records (2026-10-16 there).
- `TRPSDL2HDOCRSAUS.1` is a three-month special collection outside the CrIS
  configs.

## Not counted

Out of scope and left out of the dates above: L3 / gridded files
(`AIRS_TROPESS_gridded_*` in the AIRS FS folder, the IASI data bag
`10.35097-495`, `GOSAT2_monthly_1deg.nc`), and MIPAS in `SCIAMACHY/H2O` and
`SCIAMACHY/HDO`.
