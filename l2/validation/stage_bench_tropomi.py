"""Stage the Tier 2 TROPOMI bench tree: one real month, by symlink.

The bench has to read real orbits at real size, so it links the day
directories of 2020-07 (395 orbits, no missing days) into a tree of its own,
rather than copying ~365 GB. The production config's raw root is the source,
and the bench config's is the target, so the two cannot drift.

Run from the repo root (31 symlinks; reads nothing):

    uv run python validation/stage_bench_tropomi.py
"""

from __future__ import annotations

import os

from utils.path_utils import load_config

PRODUCTION = 'config/tropomi/config_zarr.yaml'
BENCH = 'config/tropomi/config_zarr_bench.yaml'
MONTH = ('2020', '07')


def main():
    source = os.path.join(load_config(PRODUCTION)['directories']['raw'], *MONTH)
    target = os.path.join(load_config(BENCH)['directories']['raw'], *MONTH)
    os.makedirs(target, exist_ok=True)
    days = sorted(entry for entry in os.listdir(source) if entry.isdigit())
    for day in days:
        link = os.path.join(target, day)
        if not os.path.islink(link):
            os.symlink(os.path.join(source, day), link)
    print(f'linked {len(days)} days of {"-".join(MONTH)} into {target}')


if __name__ == '__main__':
    main()
