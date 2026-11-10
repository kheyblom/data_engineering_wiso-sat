"""Stage the miniature GOSAT and GOSAT-2 raw trees the pipeline test runs against.

FOCAL files are ~0.2 MB a day, so each fixture is real files copied whole, in
the real directory layout. Every day's DED and H2O files overlap only partly,
so the fixtures exercise the merge, absent observations and the integer absent
fill.

- **GOSAT:** 2015-09-12, -13, -15 and -16; 2015-09-14 is a real upstream gap,
  so the build's missing-day check sees one.
- **GOSAT-2:** 2019-02-18, -19, -21 and -22; 2019-02-20 is a real upstream gap.
  It is read through the GOSAT reader (``source: gosat``).

The real GOSAT-2 2019 folder holds L3 files beside the L2 ones, which the
reader must skip. Each fixture's first year folder gets empty files of those
names (the real ``GOSAT2_monthly_1deg.nc`` is 373 MB).

Run from the repo root (copies ~3 MB):

    uv run python validation/stage_gosat.py

Idempotent: a file that is already staged is left alone unless --restage.
"""

from __future__ import annotations

import argparse
import os
import shutil

from products.gosat import list_granules
from utils.path_utils import load_config

# product -> (production config, fixture config, days)
FIXTURES = {
    'gosat': (
        'config/gosat/config_zarr.yaml', 'config/gosat/config_zarr_fixture.yaml',
        ('20150912', '20150913', '20150915', '20150916'),
    ),
    'gosat2': (
        'config/gosat2/config_zarr.yaml', 'config/gosat2/config_zarr_fixture.yaml',
        ('20190218', '20190219', '20190221', '20190222'),
    ),
}

# the L3 files in the real GOSAT-2 2019 folder
STRAY_FILES = ('GOSAT2_monthly_1deg.nc', 'HDO_5x5_monthly.mat')


def stage(production, fixture, days, restage):
    """Copy one fixture's days from the production raw tree.

    Args:
        production (str): The production config, for the raw root.
        fixture (str): The fixture config, for the fixture's raw root.
        days (tuple): Granule ids to copy.
        restage (bool): Overwrite files already staged.
    """
    raw = load_config(production)['directories']['raw']
    target = load_config(fixture)['directories']['raw']
    granules = {granule.id: granule for granule in list_granules(raw)}
    for day in days:
        for path in granules[day].paths:
            destination = os.path.join(target, os.path.relpath(path, raw))
            if os.path.exists(destination) and not restage:
                print(f'kept    {destination}')
                continue
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copyfile(path, destination)
            print(f'staged  {destination}')

    for kind_path in granules[days[0]].paths:
        year_dir = os.path.dirname(os.path.join(target, os.path.relpath(kind_path, raw)))
        for name in STRAY_FILES:
            stray = os.path.join(year_dir, name)
            if not os.path.exists(stray):
                open(stray, 'w').close()


def main():
    parser = argparse.ArgumentParser(description='stage the gosat and gosat2 pipeline test fixtures.')
    parser.add_argument('--restage', action='store_true', help='Overwrite staged files.')
    parser.add_argument('--products', type=str, default=','.join(FIXTURES),
                        help=f'Comma separated subset of {sorted(FIXTURES)}. Default: both.')
    args = parser.parse_args()

    for product in args.products.split(','):
        production, fixture, days = FIXTURES[product]
        stage(production, fixture, days, args.restage)
    print('done')


if __name__ == '__main__':
    main()
