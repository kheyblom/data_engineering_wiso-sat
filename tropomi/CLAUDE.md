# CLAUDE.md

Guidance for Claude Code when working in `tropomi/`.

## Project

Convert TROPOMI HDO Level 2 retrievals (raw netCDF, one file per orbit) into
icechunk-backed zarr stores for the data lake: **one store per variable per
day**, for a configurable subset of variables.

- Task list: [TASKS.md](TASKS.md). Handoff / working state: [STATE.md](STATE.md)
  — read it first in a new session, and keep it current.
- Repo is `data_engineering_wiso-sat` (parent dir). `airs/` is a sibling
  dataset; the uv environment (`pyproject.toml`, `uv.lock`, `.venv`) is shared
  at the repo root. Run with `uv run python ...`.
- Remote: `git@github.com:kheyblom/data_engineering_wiso-sat.git` (SSH, same
  repo as the HTTPS URL in TASKS.md). Branch `main`. Commit as work lands;
  imperative messages that say what changed and why.

## Governing rules

- Style guide and authoritative nomenclature:
  `/glade/u/home/kheyblom/work/style_guides/` (`style-guide_data-engineering_raw-to-datalake.md`,
  `nomenclature_data.md`). Any deviation needs the user's approval.
- The guide has **no Level 2 rules yet** (task 3). Do not invent them — propose
  and agree them with the user, then add them to the guide.
- Every variable / unit / frequency needs an exact row in `nomenclature_data.md`
  before it is used; map onto it in `nomenclature-key_tropomi.md`, which the code
  parses (never restate the mapping in Python).
- HPC: follow `~/.claude/CLAUDE.md`. No recursive traversal above
  `.../raw/TROPOMI/tropomi.grid.surfsara.nl/hdo/<YYYY>/<MM>/<DD>`; heavy work goes
  to batch jobs, shown to the user for approval first. The allocation is finite:
  validate on a tiny fixture, then a bench, then production.

## Input data (measured 2026-10-13)

```
/glade/derecho/scratch/kheyblom/data/wiso-sat/raw/TROPOMI/tropomi.grid.surfsara.nl/
  hdo/<YYYY>/<MM>/<DD>/<orbit>/s5p_l2_hdo_<product_version>_<orbit:05d>.nc
  hdo/2017/11/08/373/s5p_l2_hdo_0003_00373.nc     (~1.1 GB each)
```

- Span 2017-11-08 .. 2024-05-30. Orbits per day vary (5-14 seen; not
  every orbit has a file). Product version `0003`.
- No root variables. Five groups: `target_product` (deltad, h2o/hdo columns,
  precisions, averaging kernels, a priori profiles), `instrument` (lat/lon
  centre + corners, time, geometry, pixel ids), `diagnostics` (incl.
  `quality_flag`), `meteo`, `side_product`. Open with `group=`.
- Everything is indexed by `nobs` (~1.2 M per orbit); 2-D variables add `nlayer`
  (50), `nlevel` (51), `ncorner` (4), `nwin` (1) or `ntime` (7, a broken-down
  timestamp in `instrument/time`).
- **No `_FillValue` attribute**; missing values are the netCDF default float
  fill `9.96921e36` (`NC_FILL_FLOAT`) and must be masked explicitly.
- Variables are uncompressed, one HDF5 chunk spanning the whole variable.

## Carried over from data_engineering_gleam / _mswep

Read those repos' `CLAUDE.md` / `TESTING.md` before designing; these are
established by measurement there and apply here:

- Python capped `<3.14` (numpy segfault in xarray CF masking on 3.14).
- No `parallel=True` in `open_mfdataset` (HDF5 crashes when threaded).
- Clear netCDF `.encoding` and rebuild it; the zarr backend rejects it.
- Everything derived from YAML config — no hardcoded paths, variables, chunks.
- Each store built from raw and verified against raw independently.
- Entry points: `<name>_zarr.py` (build), `verify_<name>_zarr.py` (read-only
  audit, never mutates), `finalize_<name>_zarr.py` (only mutator: `--attrs`,
  then `--tag`, then `--gc`; that order is load-bearing; dry-run `--gc` first).
  `utils/`, `config/`, `submit_*.sh`, `validation/` fixture tests.
- A store carries `history`, `date_created`, and a `verification` attribute
  only once the verifier has actually run on it.
- Resume via icechunk commits; each `to_icechunk` write forks the session, so
  unreachable snapshots are normal and `garbage_collect` alone cleans them.
- Delete a fixture store before re-running it (builds resume, so a complete
  store is a silent no-op).
- Batch jobs: resolve `PBS_ACCOUNT` in the wrapper, count cpus with
  `os.sched_getaffinity(0)`, `OMP_NUM_THREADS=1`, `TMPDIR` on scratch, chain
  with `afterany`, never two writers on one branch.

**Does not carry over:** the spatial/temporal store pair and the
`append`/`region` write strategies assume a lat/lon grid. L2 data is a
ragged observation list, so chunking, the per-day store unit, and verification
must be designed afresh (tasks 3-4).

## Conventions

Single quotes, f-strings in log messages, Google-style docstrings
(Args / Returns / Raises), comments explain *why*. Module docstrings carry the
context needed to read the file.
