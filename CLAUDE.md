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
- Notes for the product being worked on are in `docs/products/`: `tropomi`,
  `sciamachy`, `gosat` (GOSAT and GOSAT-2), `tropess` (AIRS and CrIS), `iasi`,
  `tes`. Read only the one you need. Each sensor's doc holds everything known
  about it, including a **Known data issues** table (ID, evidence, status:
  handled / open / record only). Add new findings there. The cross-product
  unit survey, the value checks and the WISO-SAT paper cross-check are in
  [docs/l2-survey.md](docs/l2-survey.md).
- Environment: uv (`pyproject.toml`, `uv.lock`, `.venv` at the repo root). Run
  with `uv run python ...`.
- Remote: `git@github.com:kheyblom/data_engineering_wiso-sat.git` (SSH),
  branch `main`. Commit as work lands, with imperative messages that say what
  changed and why.
- `notebooks/` holds gitignored exploratory notebooks. `tools/survey/` holds
  the header and value scripts behind `docs/l2-survey.md`. They are light
  (headers, or one file's variables) and run as
  `.venv/bin/python -I tools/survey/<script>.py <files>`.

## Products in scope

Raw root: `/glade/derecho/scratch/kheyblom/data/wisosat/raw/`. Each line is
one product: one observation axis, one geolocation store, one set of variable
stores.

| product | raw subpath | granule | status |
| --- | --- | --- | --- |
| TROPOMI (SRON HDO L2, processor 8.1) | `TROPOMI/tropomi.grid.surfsara.nl/hdo/YYYY/MM/DD/<orbit>/` | orbit | production finalized 2026-10-18, tag `v8.1-verified-20261018` (findings 9-10) |
| SCIAMACHY (SRON SICOR L2) | `SCIAMACHY/HDO_SICORv10/YYYYMM/` | orbit file | later |
| GOSAT, GOSAT-2 (IUP FOCAL v3.0.1), DED and H2O merged per day | `GOSAT*/IUP-GHG-L2-{DED,H2O}-GOSAT-FOCAL-YYYY-v3.0.1/v3.0.1/YYYY/` | day (2 files) | GOSAT built and verified 2026-10-19 (11 stores); finalize pending |
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

## Layout (built 2026-10-14)

```
wisosat_zarr.py               # build: one pass over the granules writes every store of a config
verify_wisosat_zarr.py        # read-only; every observation, h5py vs the build's netCDF4
finalize_wisosat_zarr.py      # --status, then --attrs, --tag, --gc (dry run without --apply)
submit_wisosat_zarr.sh        # CONFIG=... [VERIFY=1] ./submit_wisosat_zarr.sh; show the user first
tools/rewind_stores.py        # reset every store of a config to its first N granules (dry run without --apply)
products/<product>.py         # reader: list_granules, read_granule(granule, sources, time, rule), decode_time, check_granule
utils/                        # granules (shared types), nomenclature, path_utils, zarr_utils
config/<product>/config_zarr*.yaml
nomenclature-key_<product>.md # machine read: variable, coordinate and frequency tables
validation/stage_<product>.py, validation/test_pipeline.py
```

Finalization is one action per invocation, from the repo root on a login
node (metadata only). Nothing is written without `--apply`. `--status` first:
it reports which steps each store still needs.
- **Claude runs the steps; the user signs off on each one** (user decision
  2026-10-19). Run the dry run, show what it reports, and run `--apply` only
  once the user approves that step.
- Never chain the steps in a wrapper (reverted `77e7f0d`).

```bash
uv run python finalize_wisosat_zarr.py --config config/<product>/config_zarr.yaml --status
uv run python finalize_wisosat_zarr.py --config config/<product>/config_zarr.yaml --attrs [--apply]
#   for stores whose build commits predate stamping or were built dirty:
#   [--build-revisions REV@INDEX,...] [--dirty-notes 'REV-dirty=what was uncommitted']
uv run python finalize_wisosat_zarr.py --config config/<product>/config_zarr.yaml --tag NAME [--apply]
uv run python finalize_wisosat_zarr.py --config config/<product>/config_zarr.yaml --gc [--apply]
```

- **Tag names:** `<version>-verified-YYYYMMDD`, after GLEAM. TROPOMI is
  `v8.1-verified-<date>`.
- **`--gc --apply` is irreversible.** It also ends the undo window for
  `tools/rewind_stores.py`. Read its dry run first.

- **One config = one product; one run builds many stores.** The geolocation
  store is always built; `variables` lists canonical names, and quality flags
  are mandatory. Each granule is read once, in a `spawn` process pool, and
  appended to every store. Each store is its own repo and resumes from its own
  granule index.
- **Granule index:** six coordinates on a `granule` dimension in every store,
  appended in the same commit as the data.
- **Multi-file granules** (GOSAT: each day's DED and H2O files merged onto one
  obs axis):
  - the reader marks where a variable is absent, and shared code fills it
    (NaN, or the config's `absent_fill_values` for integers);
  - the verifier places each file's observations by matching the reader's
    `MATCH_SOURCES` against the stored geolocation, rather than repeating the
    merge.
- **The time unit is per product**, from the key's coordinate table
  (TROPOMI ms, GOSAT ns: the coarsest unit that holds the source exactly).
- **Declared, never detected:**
  - empty granule directories (`expected_empty_granules`) and corrupt files
    (`expected_unreadable_granules`) are skipped only if listed, as missing
    days must be (`expected_missing_days`);
  - check a gap against the upstream listing before declaring it: half of
    TROPOMI's first empty orbits were download failures.
- **Rows that are not observations are left out, checked**, for every
  product (user decisions 2026-10-16 and 2026-10-17; TESTING.md findings 8
  and 10):
  - an observation is a row whose time, lat and lon are all written (not
    netCDF default fill, declared fill or NaN);
  - a row left out may hold values only in the sources the config lists in
    `allowed_on_rows_left_out` (TROPOMI: SZA); anything else fails the build;
  - every reader applies this through `RowRule`, `observed_rows` and
    `leaked_rows` in `utils/granules.py`. The verifier repeats it on its own
    from raw;
  - `granule_source_rows` in the index keeps each file's own row count.
- **Builds start only from a clean commit** (user decision 2026-10-18;
  TESTING.md finding 11):
  - every build commit is stamped `@ <revision>`, and `finalize` writes
    `history` from those stamps;
  - `wisosat_zarr.py` refuses to build if `git status` shows anything, tracked
    or untracked, and `submit_wisosat_zarr.sh` refuses to submit a build;
  - only fixture configs set `allow_dirty_tree`, which the test enforces;
  - commit before submitting, and keep the tree clean until each build job
    has started. A STATE.md edit left uncommitted makes a queued build fail
    at start;
  - stores built from a dirty tree before this need `finalize --attrs
    --dirty-notes 'REV-dirty=what was uncommitted'`.
- **Testing tiers and findings:** [TESTING.md](TESTING.md).
- **Test after any shared change** (condition 2), from the repo root:
  `uv run python validation/stage_<product>.py` once, then
  `TMPDIR=<scratch> uv run python validation/test_pipeline.py` (~25 s per
  product, login node). `utils` and `products` are installed editable
  (hatchling) so `validation/` can import them.

**Agreed conditions for the shared design:**
1. **Don't generalise early.** After TROPOMI's reader and fixture pass, and
   *before* any TROPOMI production run, write a second, deliberately different
   reader at fixture level only. GOSAT is the cheapest; TES is the strongest
   test. Not SCIAMACHY: it uses the same SRON file format as TROPOMI.
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
  - Store names: `wisosat.<product>.<version>.inst.native_swath.<variable>.zarr`
    (decided 2026-10-14). The version is the processor version from the files'
    attributes (TROPOMI `v_8_1`), declared in config and checked on every
    granule. There is no product token.
  - Canonical units: δD in `1e-3`; columns in `mol m-2` (x 1e4 / N_A from
    molec cm-2); mole fractions in `1e-6`, dry-air basis.
  - Model-comparison variables (kernels, priors, covariances, pressure):
    - the grammar and layout rules are in `docs/model-comparison-naming.md`;
    - each product's mapping is in its `docs/products/<product>.md`;
    - `pressure` is in Pa, and vertical dims are `level` / `layer`.
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
- HDF5 is not thread safe: read granules in processes, never threads.
- Everything derived from YAML config; no hardcoded paths, variables or
  chunks.
- Each store built from raw and verified against raw independently.
- The verifier is read-only. `finalize_*` is the only mutator:
  - `--attrs`, then `--tag`, then `--gc`; that order is load-bearing;
  - dry-run `--gc` first;
  - `--attrs` cannot drop variable attributes.
- A store carries `history`, `date_created`, and a `verification` attribute
  only once the verifier has actually run on it.
- Resume works through icechunk commits. Writes here are numpy, not dask, so
  builds leave no unreachable snapshots; `garbage_collect` cleans any that a
  killed run leaves.
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

**Learned here (2026-10-14):**
- An xarray append replaces the group's attributes with the appended
  dataset's, and `xr.merge` drops them. `write_append` carries them explicitly.
- A float `_FillValue` is stored as base64 in zarr v3 attributes; check the
  array's `fill_value` instead.
- Integer stores with a `_FillValue` decode to float64 under xarray's default
  masking. They are stored as int32.

## Conventions

Single quotes, f-strings in log messages, Google-style docstrings
(Args / Returns / Raises), comments that explain *why*. Module docstrings carry
the context needed to read the file.
