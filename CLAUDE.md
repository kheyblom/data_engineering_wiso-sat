# CLAUDE.md

Guidance for Claude Code when working in `data_engineering_wiso-sat`.

## Project

Prepares the WISO-SAT water-isotope retrievals from several satellite
products for the data lake, in two halves (restructured 2026-11-10):

| half | what it does | instructions | handoff |
| --- | --- | --- | --- |
| [`l2/`](l2/) | converts each product's **Level 2** files into icechunk-backed zarr stores on the native swath | [l2/CLAUDE.md](l2/CLAUDE.md) | [l2/STATE.md](l2/STATE.md) |
| [`gridding/`](gridding/) | grids the finalized L2 stores | [gridding/CLAUDE.md](gridding/CLAUDE.md) | [gridding/STATE.md](gridding/STATE.md) |

Shared at the root: `docs/`, `notebooks/` and [TASKS.md](TASKS.md), the
task list for both halves.

- In a new session, read the STATE.md of the half you are working on: it is
  that half's handoff, so keep it current.
- Notes for each sensor are in `docs/products/`: `tropomi`, `sciamachy`,
  `gosat` (GOSAT and GOSAT-2), `tropess` (AIRS and CrIS), `iasi`, `tes`.
  Read only the one you need. Each sensor's doc holds everything known about
  it, for both halves, including a **Known data issues** table (ID, evidence,
  status: handled / open / record only). Add new findings there, gridding
  ones too (TROPOMI T23), and say which half handles each. The doc also
  points to the product's references (papers, user guides, local full-text
  copies): look there before searching the web for one. The cross-product
  unit survey, the value checks and the WISO-SAT paper cross-check are in
  [docs/l2-survey.md](docs/l2-survey.md).
- The WISO-SAT paper (Sarkar et al. 2026) is in full text in
  `docs/sarkar-2026-wiso-sat.md`, beside its PDF. Both are local only (the PDF
  is gitignored, the .md is in `.git/info/exclude`; licence CC BY-NC-ND).
  Search or read it by section; go to the PDF for figures.
- Remote: `git@github.com:kheyblom/data_engineering_wiso-sat.git` (SSH),
  branch `main`. Commit as work lands, with imperative messages that say what
  changed and why.
- `notebooks/` holds gitignored exploratory notebooks.

## How the halves connect

- **Gridding talks to L2 only through the stores** (user decision
  2026-11-10): their `obs` axis, granule index and attributes. It never
  imports `l2/` code and never writes an L2 store.
- **Each half has its own environment** (user decision 2026-11-10):
  `<half>/pyproject.toml`, `<half>/uv.lock`, `<half>/.venv`. Run `uv run`
  from inside the half; the root has no project. Both halves have a package
  named `utils` and one named `products`, which is safe only because each
  environment installs its own. A lock change in one half never calls for
  the other's tests.
- **Notebooks** pick an environment by kernel: one Jupyter kernel per half.
  Exploring stores and grids normally uses the gridding kernel.
- **L2 builds check only `l2/` for a clean tree** (user decision
  2026-11-10), so uncommitted gridding or docs work never blocks one.

## Products in scope

Raw root: `/glade/derecho/scratch/kheyblom/data/wisosat/raw/`. Each line is
one product: one observation axis, one geolocation store, one set of variable
stores. The status is the L2 status; gridding's is in `gridding/STATE.md`.

| product | raw subpath | granule | L2 status |
| --- | --- | --- | --- |
| TROPOMI (SRON HDO L2, processor 8.1) | `TROPOMI/tropomi.grid.surfsara.nl/hdo/YYYY/MM/DD/<orbit>/` | orbit | production finalized: 19 stores 2026-10-18, tag `v8.1-verified-20261018` (findings 9-10); the 6 model-comparison stores 2026-10-22, tag `v8.1-verified-20261022` (finding 12) |
| SCIAMACHY (SRON SICOR L2) | `SCIAMACHY/HDO_SICORv10/YYYYMM/` | orbit file | production finalized 2026-10-22, tag `v8.1-verified-20261022` (22 stores; `docs/products/sciamachy.md`; l2/TESTING.md findings 13-14) |
| GOSAT, GOSAT-2 (IUP FOCAL v3.0.1), DED and H2O merged per day | `GOSAT*/IUP-GHG-L2-{DED,H2O}-GOSAT-FOCAL-YYYY-v3.0.1/v3.0.1/YYYY/` | day (2 files) | GOSAT: production finalized 2026-10-19, tag `v3.0.1-verified-20261019` (12 stores; geolocation rebuilt without `pressure`, which has its own store). GOSAT-2: production finalized 2026-10-22, tag `v3.0.1-verified-20261022` (12 stores; `source: gosat`) |
| AIRS (TROPESS v1; one product per stream, RS and FS, Summary merged into Standard per day) | `AIRS/TRPS?L2HDOAIRS*` (`l2/config/airs_rs/`, `l2/config/airs_fs/`; `source: tropess`) | day (2 files) | v1 production finalized 2026-10-23, tag `v1-verified-20261023` (19 stores per stream; `docs/products/tropess.md`; l2/TESTING.md AIRS v1 run log); v2 finalized 2026-10-28 (row below) |
| CrIS (TROPESS; SNPP RS Summary-only, SNPP FS, JPSS1 FS) | `CRIS/TRPS?L2HDOCRS*` (`l2/config/cris_snpp_rs/`, `l2/config/cris_snpp_fs/`, `l2/config/cris_jpss1_fs/`; `source: tropess`) | day (1-2 files) | production finalized 2026-10-26, tag `v1-verified-20261026` (12, 19 and 19 stores; `tropess.md` C1-C8; l2/TESTING.md CrIS v1 run log) |
| AIRS and CrIS-JPSS1 v2 (TROPESS collection 2, Full only) | `AIRS/TRPSFL2HDOAIRSFS.2/`, `CRIS/TRPSFL2HDOCRS1FS.2/` (`l2/config/airs_fs_v2/`, `l2/config/cris_jpss1_fs_v2/`; `source: tropess_v2`) | day (1 file) | production finalized 2026-10-28, tag `v2-verified-20261028` (22 stores each; `tropess.md` V1-V9; l2/TESTING.md Tier 2f and TROPESS v2 run log); later days appended as downloaded |
| IASI (KIT MUSICA L2pp) | `IASI/IASI_L2/YYYY/` | half-day file | next candidate (store version I7 to decide first) |
| TES (L2 HDO Nadir Lite v006) | `TES/TL2HDOLN_6-*/` | monthly file | next candidate (slices and matrix stores now exist for its stacked state) |

- **Out of scope:**
  - Upstream L3 / gridded files: `AIRS_TROPESS_gridded_*`, the IASI data bag
    `10.35097-495`, `TROPOMI/TROPOMI_averaged_files`, GOSAT-2
    `monthly_1deg`/`.mat`. Gridding grids our own L2 stores; it does not
    ingest these.
  - MIPAS, in `SCIAMACHY/H2O` and `SCIAMACHY/HDO`: it is not in WISO-SAT.
- Coverage gaps are flagged and not chased: TES 2011-2015 and AIRS
  2020-04 .. 2021-01 are absent from disk.

## Governing rules

- **Style guide and authoritative nomenclature:**
  `/glade/u/home/kheyblom/work/style_guides/`
  (`style-guide_data-engineering_raw-to-datalake.md`, `nomenclature_data.md`).
  Its General rules govern both halves; its "Level 2 satellite retrieval
  data" section governs `l2/`, and its "Gridded data" section `gridding/`.
  Any deviation needs the user's approval, and an exception approved for one
  product or collection is never carried to another without it.
- **Units and attributes:**
  - Canonical units: δD in `1e-3`; columns in `mol m-2` (x 1e4 / N_A from
    molec cm-2); mole fractions in `1e-6`, dry-air basis.
  - Never set `standard_name`; a source one is retained unchanged.
- **Nomenclature rows come first.** Every variable, unit and frequency needs an
  exact row in `nomenclature_data.md` before it is used. L2 maps onto it in
  `l2/nomenclature-key_<source>.md`, which its code parses; never restate the
  mapping in Python.
- **Project rules (2026-10-14, kept out of the style guide by the user):**
  - **Verification covers every observation, not a sample.**
  - **Dry-air and total-air mole fractions are different variables** with
    different canonical names; never convert between them. Every in-scope
    mole fraction is dry-air.
  - **Log-space `1` variables are never scaled:** TROPESS
    `observation_error_h2o` and IASI `musica_wvp`.
- **HPC:** follow `~/.claude/CLAUDE.md`. Scope every traversal to an exact
  product subpath and bound its depth; on the Lustre tree use `lfs find`
  (it has `--maxdepth`, no mindepth). Show the user any batch job before
  submitting it. The allocation is finite, so go tiny fixture, then bench,
  then production.

## Carried over from data_engineering_gleam / _mswep

Read those repos' `CLAUDE.md` and `TESTING.md` before designing. These were
established by measurement there and apply to both halves:

- Python capped `<3.14` in every environment (numpy segfault in xarray CF
  masking on 3.14).
- HDF5 is not thread safe: read files in processes, never threads.
- Everything derived from YAML config; no hardcoded paths, variables or
  chunks.
- Each store built from its source and verified against it independently.
- The verifier is read-only. `finalize_*` is the only mutator:
  - `--attrs`, then `--tag`, then `--gc`; that order is load-bearing;
  - dry-run `--gc` first;
  - `--attrs` cannot drop variable attributes.
- A store carries `history`, `date_created`, and a `verification` attribute
  only once the verifier has actually run on it.
- Tag names: `<version>-verified-YYYYMMDD`, after GLEAM.
- Batch jobs:
  - resolve `PBS_ACCOUNT` in the wrapper;
  - count cpus with `os.sched_getaffinity(0)`;
  - set `OMP_NUM_THREADS=1` and `TMPDIR` on scratch;
  - chain with `afterany`, never two writers on one branch.

What each half adds or leaves out is in its own CLAUDE.md.

## Conventions

Single quotes, f-strings in log messages, Google-style docstrings
(Args / Returns / Raises), comments that explain *why*. Module docstrings carry
the context needed to read the file.
