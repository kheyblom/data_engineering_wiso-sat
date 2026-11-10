"""Stage the Tier 2c SCIAMACHY bench tree: three real months, by symlink.

The bench has to read real orbits, so it links the month folders 2010-09 to
2010-11 (1,026 orbit files, ~4.3 GB) into a tree of its own rather than
copying them. 2010-10 holds the S9 overlap of orbits 45262 and 45263, so the
bench builds and verifies a declared row block at production scale. The
production config's raw root is the source, and the bench config's is the
target, so the two cannot drift.

Run from the repo root (3 symlinks; reads nothing):

    uv run python validation/stage_bench_sciamachy.py
"""

from __future__ import annotations

import os

from utils.path_utils import load_config

PRODUCTION = 'config/sciamachy/config_zarr.yaml'
BENCH = 'config/sciamachy/config_zarr_bench.yaml'
MONTHS = ('201009', '201010', '201011')


def main():
    source = load_config(PRODUCTION)['directories']['raw']
    target = load_config(BENCH)['directories']['raw']
    os.makedirs(target, exist_ok=True)
    for month in MONTHS:
        link = os.path.join(target, month)
        if not os.path.islink(link):
            os.symlink(os.path.join(source, month), link)
    print(f'linked {len(MONTHS)} months {MONTHS} into {target}')


if __name__ == '__main__':
    main()
