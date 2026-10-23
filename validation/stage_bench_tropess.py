"""Stage the AIRS RS and FS bench trees: one real month each, by symlink.

The bench reads real days at production settings, so it links each of the
month's files into a tree of its own, at the same path relative to the raw
root, rather than copying them. The production config's listing chooses the
files, and the bench config's raw root is the target, so the two cannot
drift:

- **RS 2020-03:** the record's last month (31 days, R1p6), ending on the
  Summary-only day 2020-03-31.
- **FS 2024-04:** the R1p22 to R1p23 change on 04-25 and the Summary-only
  day 2024-04-03; 30 days, ~1.8 GB.

The verifier fails a declared fill value that never occurs, so this also
reports, for each fill the production config declares, whether the month
holds it: the bench config declares only those that occur.

Run from the repo root (symlinks, and reads the declared variables of the
month's files, ~2 GB at most):

    uv run python validation/stage_bench_tropess.py
"""

from __future__ import annotations

import argparse
import os

import h5py
import numpy as np

import products.tropess as reader
from products.tropess import list_granules
from utils.path_utils import listing_options, load_config

# product -> (production config, bench config, month)
BENCHES = {
    'airs_rs': ('config/airs_rs/config_zarr.yaml', 'config/airs_rs/config_zarr_bench.yaml', '202003'),
    'airs_fs': ('config/airs_fs/config_zarr.yaml', 'config/airs_fs/config_zarr_bench.yaml', '202404'),
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
        month (str): YYYYMM.
    """
    settings = load_config(production)
    raw = settings['directories']['raw']
    target = load_config(bench)['directories']['raw'] if os.path.exists(bench) else None
    granules = [granule for granule in list_granules(raw, **listing_options(settings, reader))
                if granule.id.startswith(month)]
    paths = [path for granule in granules for path in granule.paths]
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
    for source, found in fills_present(paths, settings['source_fill_values']).items():
        print(f'  fill {source}: {found or "none"}')


def main():
    parser = argparse.ArgumentParser(description='stage the airs rs and fs bench trees.')
    parser.add_argument('--products', type=str, default=','.join(BENCHES),
                        help=f'Comma separated subset of {sorted(BENCHES)}. Default: both.')
    args = parser.parse_args()
    for product in args.products.split(','):
        stage(*BENCHES[product])
    print('done')


if __name__ == '__main__':
    main()
