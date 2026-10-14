# CLAUDE.md

Guidance for Claude Code when working in `data_engineering_wiso-sat`.

## Project

One codebase that converts the WISO-SAT **Level 2** water-isotope retrievals
from several satellite products into icechunk-backed zarr stores for the data
lake. Each product has its own config(s) and nomenclature key; everything
downstream of reading a source file is shared. Design around TROPOMI first,
then extend to the other products (decided 2026-10-14).

- Read [STATE.md](STATE.md) first in a new session: it is the handoff, so keep
  it current. The task list is [TASKS.md](TASKS.md).
- Notes for the product being worked on are in
  `docs/products/<product>.md`; read only the one you need. The cross-product
  unit survey, the value checks and the WISO-SAT paper cross-check are in
  [docs/l2-survey.md](docs/l2-survey.md).
- Environment: uv (`pyproject.toml`, `uv.lock`, `.venv` at the repo root). Run
  with `uv run python ...`.
- Remote: `git@github.com:kheyblom/data_engineering_wiso-sat.git` (SSH),
  branch `main`. Commit as work lands, with imperative messages that say what
  changed and why.
- `tropomi/` and `airs/` hold only gitignored exploratory notebooks.

## Products in scope

Raw root: `/glade/derecho/scratch/kheyblom/data/wiso-sat/raw/`. Each line is
one product: one observation axis, one geolocation store, one set of variable
stores.

| product | raw subpath | granule | status |
| --- | --- | --- | --- |
| TROPOMI (SRON HDO L2, 0003) | `TROPOMI/tropomi.grid.surfsara.nl/hdo/YYYY/MM/DD/<orbit>/` | orbit | designing |
| SCIAMACHY (SRON SICOR L2) | `SCIAMACHY/HDO_SICORv10/YYYYMM/` | orbit file | later |
| GOSAT, GOSAT-2 (IUP FOCAL v3.0.1), DED and H2O separately | `GOSAT*/IUP-GHG-L2-{DED,H2O}-GOSAT-FOCAL-YYYY-v3.0.1/v3.0.1/YYYY/` | daily file | later |
| AIRS (TROPESS RS; TROPESS FS) | `AIRS/TRPSYL2HDOAIRSORS_*`, `AIRS/TRPSDL2HDOAIRSFS_*` | daily file | later |
| CrIS (SNPP RS; JPSS1 FS) | `CRIS/TRPSYL2HDOCRSRS_*`, `CRIS/TRPSDL2HDOCRS1FS_*` | daily file | later |
| IASI (KIT MUSICA L2pp) | `IASI/IASI_L2/YYYY/` | half-day file | later |
| TES (L2 HDO Nadir Lite v006) | `TES/TL2HDOLN_6-*/` | monthly file | later |

- **Out of scope:**
  - L3 / gridded files: `AIRS_TROPESS_gridded_*`, the IASI data bag
    `10.35097-495`, `TROPOMI/TROPOMI_averaged_files`, GOSAT-2
    `monthly_1deg`/`.mat`.
  - MIPAS, in `SCIAMACHY/H2O` and `SCIAMACHY/HDO`: it is not in WISO-SAT.
- Coverage gaps are flagged and not chased: TES 2011-2015 and AIRS
  2020-04 .. 2021-01 are absent from disk.

## Planned layout (task 4; nothing built yet)

```
wiso_sat_zarr.py, verify_wiso_sat_zarr.py, finalize_wiso_sat_zarr.py, submit_wiso_sat_zarr.sh
products/<product>.py         # reader: list granules, open one as a standard obs-indexed Dataset
utils/                        # granule index, geolocation, write/resume, nomenclature, units, logging
config/<product>/*.yaml
nomenclature-key_<source>.md  # one per product, machine read
validation/                   # per-product fixtures; one end-to-end test runs them all
```

**Agreed conditions for the shared design:**
1. **Don't generalise early.** After TROPOMI's reader and fixture pass, and
   *before* any TROPOMI production run, write a second, deliberately different
   reader (GOSAT is the cheapest, TES the strongest test) at fixture level only.
   Share only what a second product actually needs.
2. **Test every product after shared changes.** Every product keeps a tiny
   fixture, and the shared end-to-end test runs all of them after any change
   to shared code.
3. **Scale knobs live in config.** Batching, caches and memory settings are
   per-product config, not code, so small products stay simple despite
   TROPOMI's scale.

## Governing rules

- **Style guide and authoritative nomenclature:**
  `/glade/u/home/kheyblom/work/style_guides/`
  (`style-guide_data-engineering_raw-to-datalake.md`, `nomenclature_data.md`).
  Its "Level 2 satellite retrieval data" section and the General rules govern
  here:
  - one store per variable over the whole record;
  - every observation kept, never filtered;
  - one `geolocation` store per product (`time`, `lat`, `lon`, plus the
    pressure grid for profile products);
  - an identical `obs` axis and granule index in every store of a product.

  Any deviation needs the user's approval.
- **Naming, units and attributes:**
  - Store names: `<source>.<version>.<product>.inst.native_swath.<variable>.zarr`.
  - Canonical units: δD in `1e-3`; columns in `mol m-2` (x 1e4 / N_A from
    molec cm-2); mole fractions in `1e-6`, dry-air basis.
  - Never set `standard_name`; a source one is retained unchanged.
    `cdm_data_type: Point`.
- **Nomenclature rows come first.** Every variable, unit and frequency needs an
  exact row in `nomenclature_data.md` before it is used. Map onto it in the
  product's `nomenclature-key_<source>.md`, which the code parses; never
  restate the mapping in Python.
- **Project rules (2026-10-14, kept out of the style guide by the user):**
  - **Verification covers every observation, not a sample.**
  - **Dry-air and total-air mole fractions are different variables** with
    different canonical names; never convert between them. Every in-scope
    mole fraction is dry-air.
  - **Log-space `1` variables are never scaled:** TROPESS
    `observation_error_h2o` and IASI `musica_wvp`.
- **HPC:** follow `~/.claude/CLAUDE.md`. Scope every traversal to an exact
  product subpath and bound its depth; on this Lustre tree use `lfs find`
  (it has `--maxdepth`, no mindepth). Show the user any batch job before
  submitting it. The allocation is finite, so go tiny fixture, then bench,
  then production.

## Carried over from data_engineering_gleam / _mswep

Read those repos' `CLAUDE.md` and `TESTING.md` before designing. These were
established by measurement there and apply here:

- Python capped `<3.14` (numpy segfault in xarray CF masking on 3.14).
- No `parallel=True` in `open_mfdataset` (HDF5 crashes when threaded).
- Clear netCDF `.encoding` and rebuild it; the zarr backend rejects it.
- Everything derived from YAML config; no hardcoded paths, variables or
  chunks.
- Each store built from raw and verified against raw independently.
- The verifier is read-only. `finalize_*` is the only mutator:
  - `--attrs`, then `--tag`, then `--gc`; that order is load-bearing;
  - dry-run `--gc` first;
  - `--attrs` cannot drop variable attributes.
- A store carries `history`, `date_created`, and a `verification` attribute
  only once the verifier has actually run on it.
- Resume works through icechunk commits. Each `to_icechunk` write forks the
  session, so unreachable snapshots are normal; `garbage_collect` alone cleans
  them.
- Delete a fixture store before re-running it: builds resume, so a complete
  store is a silent no-op.
- Batch jobs:
  - resolve `PBS_ACCOUNT` in the wrapper;
  - count cpus with `os.sched_getaffinity(0)`;
  - set `OMP_NUM_THREADS=1` and `TMPDIR` on scratch;
  - chain with `afterany`, never two writers on one branch.

**Does not carry over:** the spatial/temporal store pair and the
`append`/`region` write strategies, both of which assume a lat/lon grid. L2
uses obs-only chunking, appends in granule order, and resumes from the
granule index.

## Conventions

Single quotes, f-strings in log messages, Google-style docstrings
(Args / Returns / Raises), comments that explain *why*. Module docstrings carry
the context needed to read the file.
