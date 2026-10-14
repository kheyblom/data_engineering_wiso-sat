"""Stage the miniature GOSAT raw tree the pipeline test runs against.

FOCAL files are ~0.2 MB a day, so the fixture is real files copied whole, in
the real directory layout: both kinds for 2015-09-12, -13, -15 and -16.
2015-09-14 is a real upstream gap, so the build's missing-day check sees one.
Every day's DED and H2O files overlap only partly, so the fixture exercises
the merge, absent observations and the integer absent fill.

A stray L3-style file is added, as the GOSAT-2 tree has, which the reader must
skip.

Run from the repo root (copies ~2 MB):

    uv run python validation/stage_gosat.py

Idempotent: a file that is already staged is left alone unless --restage.
"""

from __future__ import annotations

import argparse
import os
import shutil

from products.gosat import list_granules
from utils.path_utils import load_config

PRODUCTION = 'config/gosat/config_zarr.yaml'
FIXTURE = 'config/gosat/config_zarr_fixture.yaml'

DAYS = ('20150912', '20150913', '20150915', '20150916')


def main():
    parser = argparse.ArgumentParser(description='stage the gosat pipeline test fixture.')
    parser.add_argument('--restage', action='store_true', help='Overwrite staged files.')
    args = parser.parse_args()

    raw = load_config(PRODUCTION)['directories']['raw']
    target = load_config(FIXTURE)['directories']['raw']
    granules = {granule.id: granule for granule in list_granules(raw)}
    for day in DAYS:
        for path in granules[day].paths:
            destination = os.path.join(target, os.path.relpath(path, raw))
            if os.path.exists(destination) and not args.restage:
                print(f'kept    {destination}')
                continue
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copyfile(path, destination)
            print(f'staged  {destination}')

    # the real GOSAT-2 tree holds L3 files beside the L2 ones
    year_dir = os.path.dirname(os.path.join(target, os.path.relpath(granules[DAYS[0]].paths[0], raw)))
    stray = os.path.join(year_dir, 'GOSAT2_monthly_1deg.nc')
    if not os.path.exists(stray):
        open(stray, 'w').close()
    print('done')


if __name__ == '__main__':
    main()
