"""Stage the AIRS and CrIS bench trees: one real month each, by symlink.

The bench reads real days at production settings, so it links each of the
month's files into a tree of its own, at the same path relative to the raw
root, rather than copying them. The production config's listing chooses the
files, and the bench config's raw root is the target, so the two cannot
drift:

- **RS 2020-03:** the record's last month (31 days, R1p6), ending on the
  Summary-only day 2020-03-31.
- **FS 2024-04:** the R1p22 to R1p23 change on 04-25 and the Summary-only
  day 2024-04-03; 30 days, ~1.8 GB.
- **CrIS-SNPP RS 2015-12** (2026-10-26): Summary only, 28 days to 12-29, with
  a missing day (12-05) and repeated footprints (R37).
- **CrIS-SNPP FS 2021-04:** R36 on every day, repeats; 30 days.
- **CrIS-JPSS1 FS 2021-05:** the R1p24 replacement of 05-21 (R18; its old
  file is linked too), R36 on every day but that one, repeats between R1p12
  and R1p24 files; 31 days.
- **AIRS v2 and CrIS-JPSS1 v2, 2026-06-01 .. 09** (2026-10-28; ``tropess.md``
  V8): nine days of Full files each, read with the v2 reader; CrIS's hold
  repeats (R37). A span is matched as a prefix of the day id.

The verifier fails a declared fill value that never occurs, so this also
reports, for each fill the production config declares, whether the month
holds it: the bench config declares only those that occur. Where the config
declares the repeat rule (R37), it also reports how many rows the rule leaves
out of the month alone, which the bench config declares.

Run from the repo root (symlinks, and reads the declared variables of the
month's files, ~2 GB at most):

    uv run python validation/stage_bench_tropess.py
"""

from __future__ import annotations

import argparse
import glob
import os

import h5py
import numpy as np

import products.tropess as reader
from utils.path_utils import listing_options, load_config, load_reader

# product -> (production config, bench config, month)
BENCHES = {
    'airs_rs': ('config/airs_rs/config_zarr.yaml', 'config/airs_rs/config_zarr_bench.yaml', '202003'),
    'airs_fs': ('config/airs_fs/config_zarr.yaml', 'config/airs_fs/config_zarr_bench.yaml', '202404'),
    'cris_snpp_rs': ('config/cris_snpp_rs/config_zarr.yaml', 'config/cris_snpp_rs/config_zarr_bench.yaml', '201512'),
    'cris_snpp_fs': ('config/cris_snpp_fs/config_zarr.yaml', 'config/cris_snpp_fs/config_zarr_bench.yaml', '202104'),
    'cris_jpss1_fs': ('config/cris_jpss1_fs/config_zarr.yaml', 'config/cris_jpss1_fs/config_zarr_bench.yaml', '202105'),
    'airs_fs_v2': ('config/airs_fs_v2/config_zarr.yaml', 'config/airs_fs_v2/config_zarr_bench.yaml', '2026060'),
    'cris_jpss1_fs_v2': ('config/cris_jpss1_fs_v2/config_zarr.yaml',
                         'config/cris_jpss1_fs_v2/config_zarr_bench.yaml', '2026060'),
}


def fills_present(paths, fills):
    """Which declared fill values occur in some files.

    Args:
        paths (list): Source files.
        fills (dict): Source path -> declared fill values, from config.

    Returns:
        dict: Source path -> the declared values that occur, each with its count.
    """
    counts = {source: dict.fromkeys(values, 0) for source, values in fills.items()}
    for path in paths:
        with h5py.File(path, 'r') as handle:
            for source, values in fills.items():
                if source not in handle:
                    continue
                data = handle[source][...]
                for value in values:
                    counts[source][value] += int(np.count_nonzero(data == value))
    return {source: {value: n for value, n in found.items() if n} for source, found in counts.items()}


def stage(production, bench, month):
    """Link one month's files into the bench tree and report its fills.

    Args:
        production (str): The production config, for the raw root and listing.
        bench (str): The bench config, for the bench raw root.
        month (str): YYYYMM, or any prefix of the day ids (``2026060``: 06-01 .. 09).
    """
    settings = load_config(production)
    module = load_reader(settings)
    raw = settings['directories']['raw']
    target = load_config(bench)['directories']['raw'] if os.path.exists(bench) else None
    # the repeat rule reads every production file; the month is applied below
    options = dict(listing_options(settings, module))
    rule = options.get('repeated_footprints')
    options['repeated_footprints'] = None
    granules = [granule for granule in module.list_granules(raw, **options) if granule.id.startswith(month)]
    paths = [path for granule in granules for path in granule.paths]
    # R18: a replaced file of the month is linked too, so the bench declares it
    superseded = {day: name for day, name in (settings.get('superseded_files') or {}).items()
                  if str(day).startswith(month)}
    for name in superseded.values():
        paths += glob.glob(os.path.join(raw, '*', name))
    if target is not None:
        for path in paths:
            link = os.path.join(target, os.path.relpath(path, raw))
            os.makedirs(os.path.dirname(link), exist_ok=True)
            if not os.path.islink(link):
                os.symlink(path, link)
        print(f'linked {len(paths)} files of {len(granules)} days ({month}) into {target}')
    else:
        print(f'{bench} does not exist yet: {len(paths)} files of {len(granules)} days, nothing linked')
    partial = sorted(granule.id for granule in granules if len(granule.paths) == 1)
    print(f'  one-sided days: {partial}')
    print(f'  replaced files (superseded_files): {superseded}')
    if rule:
        try:
            reader.select_repeats(granules, dict(rule, expected_left_out=None))
        except ValueError as error:
            print(f'  repeat rule over the month: {str(error).split(", but")[0]}')
    for source, found in fills_present(paths, settings['source_fill_values']).items():
        print(f'  fill {source}: {found or "none"}')


def main():
    parser = argparse.ArgumentParser(description='stage the airs and cris bench trees.')
    parser.add_argument('--products', type=str, default=','.join(BENCHES),
                        help=f'Comma separated subset of {sorted(BENCHES)}. Default: all.')
    args = parser.parse_args()
    for product in args.products.split(','):
        stage(*BENCHES[product])
    print('done')


if __name__ == '__main__':
    main()
