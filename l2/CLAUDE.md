# CLAUDE.md (l2/)

Guidance for Claude Code when working in `l2/`, the half of
`data_engineering_wiso-sat` that converts the WISO-SAT **Level 2** retrievals
into icechunk-backed zarr stores. The root [CLAUDE.md](../CLAUDE.md) holds the
products in scope and the rules both halves share; this file holds the L2
machinery.

- Read [STATE.md](STATE.md) first in a new session: it is the L2 handoff, so
  keep it current. Testing tiers and findings: [TESTING.md](TESTING.md).
- **Run everything from `l2/`.** It has its own environment
  (`pyproject.toml`, `uv.lock`, `.venv`); `uv run python ...` finds it from
  here. Config paths (`config/...`), `logs/` and the submit script all resolve
  from this folder.
- `tools/survey/` holds the header and value scripts behind
  `../docs/l2-survey.md`. They are light (headers, or one file's variables)
  and run as `.venv/bin/python -I tools/survey/<script>.py <files>`.
- One codebase for every product: each has its own config(s) and
  nomenclature key; everything downstream of reading a source file is shared.
  Designed around TROPOMI first, then extended (decided 2026-10-14).

## Layout (built 2026-10-14; moved into `l2/` 2026-11-10)

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

Finalization is one action per invocation, from `l2/` on a login node
(metadata only). Nothing is written without `--apply`. `--status` first: it
reports which steps each store still needs.
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
uv run python finalize_wisosat_zarr.py --config config/<product>/config_zarr.yaml --expire [--apply]
#   sharded stores only: drops the build snapshots, so --gc reclaims superseded shards
uv run python finalize_wisosat_zarr.py --config config/<product>/config_zarr.yaml --gc [--apply]
```

- **Never run two verifies of one config at once.** Both append to the
  same `logs/verify_<log_file>`, and finalize credits each run's verdict to
  the last `stores:` line before it, so interleaved runs can credit one run's
  pass to the other's stores. Chain verify jobs `afterany` (2026-10-21).
- **`logs/` is evidence.** It is gitignored, but finalize reads the verify
  logs in it to credit verification; never delete or move it.
- **Tag names:** `<version>-verified-YYYYMMDD`, after GLEAM. TROPOMI is
  `v8.1-verified-<date>`.
- **`--expire --apply` and `--gc --apply` are irreversible.** Expiry runs
  after `--attrs` and `--tag` (it refuses otherwise): it drops the build
  commits, whose log then lives on in `history`. Both end the undo window for
  `tools/rewind_stores.py`. Read its dry run first.

## Store naming and attributes

- Store names: `wisosat.<product>.<version>.inst.native_swath.<variable>.zarr`
  (decided 2026-10-14). The version is the processor version from the files'
  attributes (TROPOMI `v_8_1`), declared in config and checked on every
  granule. There is no product token.
- `cdm_data_type: Point`.
- Model-comparison variables (kernels, priors, covariances, pressure):
  - the grammar and layout rules are in `../docs/model-comparison-naming.md`;
  - each product's mapping is in its `../docs/products/<product>.md`;
  - `pressure` is its own variable store, in Pa, and vertical dims are
    `level` / `layer`.
- **Store attributes cite repo paths from the repository root**
  (`docs/products/tropess.md R22`, in config `reason` strings and reader
  comments). Leave those strings as they are: they are written into the
  stores, and the existing stores carry them.

## Design

- **A config's `source` picks the reader and key** (`products/<source>.py`,
  `nomenclature-key_<source>.md`); it defaults to `product`, which names the
  stores. GOSAT-2 sets `source: gosat` (user decision 2026-10-22). Where one
  reader serves several satellites it names a `PLATFORM_ATTR`, and the build
  and the verifier check every file's against the config's `platform`.
- **One config = one product; one run builds many stores.** The geolocation
  store is always built; `variables` lists canonical names, and quality flags
  are mandatory. Each granule is read once, in a `spawn` process pool, and
  appended to every store. Each store is its own repo and resumes from its own
  granule index.
- **Wide stores get a process of their own** (`own_process_stores`, user
  decision 2026-10-19; TESTING.md finding 12). Shipping TROPOMI's ~1.1 GB per
  orbit of 2-D sources from read workers to one writer cost more CPU than the
  reading. Each listed store runs the same pass in its own process, reading
  only its sources; the others keep the shared pass. The verifier scans the
  same groups over ranges of `verify_granules_per_task` granules in
  `verify_num_workers` processes, each returning only counts. `--stores`
  compares only the stores named; geolocation is opened for the index but
  its values are compared only when named.
- **The submit script leaves `MALLOC_TRIM_THRESHOLD_` unset** (finding 12): at
  0 it cost the 2-D build 22% of its CPU in kernel time.
- **Granule index:** six coordinates on a `granule` dimension in every store,
  appended in the same commit as the data.
- **Compression and shards are per array, in config** (user decisions
  2026-10-19). A config's `compression` block names a blosc setting, an
  optional `shard_obs` (a multiple of `chunks.obs`) and the arrays they apply
  to. Every other array keeps zarr's default zstd, unsharded, and the verifier
  checks each array against the config. TROPOMI uses it for its 50- and
  51-wide arrays: ~34% smaller, lossless, and ~7,800 shard files per array
  rather than ~249,000 chunk files. Each commit rewrites the last shard;
  `finalize --expire` reclaims the superseded copies.
- **Multi-file granules** (GOSAT: each day's DED and H2O files merged onto one
  obs axis):
  - the reader marks where a variable is absent, and shared code fills it
    (NaN, or the config's `absent_fill_values` for integers);
  - the verifier places each file's observations by matching the reader's
    `MATCH_SOURCES` against the stored geolocation, rather than repeating the
    merge.
- **The time unit is per product**, from the key's coordinate table
  (TROPOMI ms, GOSAT ns: the coarsest unit that holds the source exactly).
- **Added for TROPESS (2026-10-23):**
  - `version_product` appends a stream to the version slot (`v_1.rs`);
  - `time_order: source` keeps rows in file order where the files are not
    in time order (style-guide exception); the `layout` attribute states
    which. The time check then gives way to a repeat check (user decision
    2026-10-23): no observation may share time, lat and lon with another in
    its granule or the granule before, in the build (`check_repeats`, the
    seam read back from the store on a resume) and in the verifier. The time
    check caught SCIAMACHY S8 and S9, which the exception alone would have
    let through;
  - `declared_masked_values` masks a declared defect to NaN, confirmed from
    raw by the reader (`DECLARED_MASKS`, `declared_masks`) and the verifier;
  - `source_dtypes` casts an integer source losslessly (checked);
  - `expected_partial_granules` declares days that have only one of a
    granule's files; a reader's `LISTING_OPTIONS` passes config keys to
    `list_granules`, and its `INDEX_EXTRA` adds fields to the granule index.
- **Added for CrIS (2026-10-26):**
  - the TROPESS listing selects by `platform` (folders and file names), so
    SNPP and JPSS1 share a raw root; `granule_types: [Summary]` makes a
    Summary-only product; `superseded_files` names a replaced file (R18);
  - `repeated_footprints` (R37): the listing leaves out each footprint's
    older copies (`Granule.left_out`), fails unless the count equals
    `expected_left_out`, and the index gains `granule_rows_left_out`
    (`index_extra_fields(settings)`, so AIRS's index is unchanged). The
    verifier works the rule out again from raw. `check_repeats`,
    `stored_seam_keys` and the verifier look back `look_back` granules;
  - `declared_masked_values` with `where: every_row_of_listed_days` masks
    whole files (R36); an integer source stores its `absent_fill_values`
    entry there. The verifier also fails on an undeclared file that holds
    the value on every row (Q1);
  - `expected_missing_days` takes `[first, last]` ranges.
- **Added for TROPESS v2 (2026-10-28; `tropess.md` V9):**
  - a v2 reader and key of their own (`products/tropess_v2.py`,
    `nomenclature-key_tropess_v2.md`, `source: tropess_v2`), Full files only;
  - **source slices** in the key's `original_variable_name` (`x[:, 0:17]`),
    one canonical name per slice, after the reader's squeeze; the config's
    `source_remainders` declares what they leave out (`empty`, or `equal` to
    another range), slices plus remainders must cover the source, and the
    build (`utils/selections.py`) and the verifier (its own code) check
    every remainder. Shaped for TES's stacked HDO/H2O halves too;
  - `level_lookups`: a source read on another grid at each written value of
    a third (v2 `altitude` on `pressure_fm` at the retrieval pressures);
  - **matrix stores** (N18): a key's "Matrix Store Key" table makes several
    canonical arrays one store; the config lists the store, never its
    arrays as well;
  - `withheld_standard_names`: an approved exception keeping a source
    `standard_name` as `original_standard_name` where it would mislabel the
    store (v2 `air_molar_density`);
  - the verifier tallies a declared fill over the whole source as read,
    before any slice: the fill is the source's.
- **Declared, never detected:**
  - empty granule directories (`expected_empty_granules`) and corrupt files
    (`expected_unreadable_granules`) are skipped only if listed, as missing
    days must be (`expected_missing_days`; `expected_missing_months` for a
    reader whose `COVERAGE_FREQUENCY` is monthly, as SCIAMACHY's);
  - observations that repeat others (`declared_rows_left_out`, user decision
    2026-10-22): each names its rows, a reason and what they must match
    (`repeat_of` a block of the same file, or `same_location_as` another
    granule's rows). The reader (`DECLARED_ROWS`) and the verifier each
    confirm it from raw before leaving the rows out; other readers refuse
    one. SCIAMACHY's S9 entry is a one-time exception to keeping every
    observation;
  - CrIS footprints delivered in two daily files (R37, user decision
    2026-10-26) are stored once: the copy from the newest algorithm, then
    the latest `ProductionDateTime`. A declared rule, applied from raw by
    the build and the verifier; an approved exception for CrIS only
    (`../docs/cris-repeats-r37.md`);
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
- **Builds start only from a clean commit of `l2/`** (user decisions
  2026-10-18 and 2026-11-10; TESTING.md finding 11):
  - every build commit is stamped `@ <revision>` (the repo's HEAD), and
    `finalize` writes `history` from those stamps;
  - `wisosat_zarr.py` refuses to build if `git status -- l2/` shows anything,
    tracked or untracked, and `submit_wisosat_zarr.sh` refuses to submit a
    build. Uncommitted work in `gridding/`, `docs/` or the root does not
    block a build: none of it reaches one (`L2_ROOT` in `utils/zarr_utils.py`);
  - only fixture configs set `allow_dirty_tree`, which the test enforces;
  - commit before submitting, and keep `l2/` clean until each build job has
    started. A `l2/STATE.md` edit left uncommitted makes a queued build fail
    at start;
  - stores built from a dirty tree before this need `finalize --attrs
    --dirty-notes 'REV-dirty=what was uncommitted'`.
- **Test after any change to `l2/`'s shared code or its lock** (condition 2),
  from `l2/`: `uv run python validation/stage_<product>.py` once, then
  `TMPDIR=<scratch> uv run python validation/test_pipeline.py` (~15 min for
  all 11 fixtures, login node). `utils` and `products` are installed editable
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

## Carried over from data_engineering_gleam / _mswep, L2-specific

The shared principles are in the root CLAUDE.md. For L2:

- Resume works through icechunk commits. Writes here are numpy, not dask, so
  builds leave no unreachable snapshots; `garbage_collect` cleans any that a
  killed run leaves.
- Delete a fixture store before re-running it: builds resume, so a complete
  store is a silent no-op.
- **Does not carry over:** the spatial/temporal store pair and the
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
