"""Stage the miniature SCIAMACHY raw tree the pipeline test runs against.

SCIAMACHY orbit files are small (0.7-4 MB here), so these are real files
copied whole, not cut: every byte is as SRON wrote it. The test runs on a login
node in under a minute.

Chosen deliberately (see config/sciamachy/config_zarr_fixture.yaml):

- **Orbits 45262, 45263 and 45264** (2010-10), the overlap declared in the
  config (S9) and the orbit after it.
- **Orbit 15838** (2005-03), triplicated (S8), staged in 2010-10 as a
  stand-in. Its orbit number sorts first and its time is earlier, so time
  still never decreases.
- **Orbit 45824** (2010-12), whose flagged rows hold fill in every source
  that declares one.
- **2010-11 left out**, so the monthly coverage check sees a declared gap.
- **A hidden transfer folder holding a duplicate, and a .DS_Store**, as the
  real tree has (S5), which the reader must not walk.

Run from the repo root (reads ~11 MB):

    uv run python validation/stage_sciamachy.py

Idempotent: a file already staged is left alone unless --restage.
"""

from __future__ import annotations

import argparse
import os
import shutil

from utils.path_utils import load_config

PRODUCTION = 'config/sciamachy/config_zarr.yaml'
FIXTURE = 'config/sciamachy/config_zarr_fixture.yaml'

# (source month, orbit, staged month)
FILES = (
    ('201010', '45262', '201010'),
    ('201010', '45263', '201010'),
    ('201010', '45264', '201010'),
    ('200503', '15838', '201010'),
    ('201012', '45824', '201012'),
)
NAME = 'sci_l2_h2o_hdo_0110_{orbit}.nc'

# what the reader must skip: a transfer leftover holding a duplicate, as in
# the real tree (S5)
HIDDEN = '.ArchiveServiceTemp.sb-fixture'


def main():
    parser = argparse.ArgumentParser(description='stage the sciamachy pipeline test fixture.')
    parser.add_argument('--restage', action='store_true', help='Overwrite staged files.')
    args = parser.parse_args()

    raw = load_config(PRODUCTION)['directories']['raw']
    target = load_config(FIXTURE)['directories']['raw']
    for month, orbit, staged in FILES:
        name = NAME.format(orbit=orbit)
        destination = os.path.join(target, staged, name)
        if os.path.exists(destination) and not args.restage:
            print(f'kept    {destination}')
            continue
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copyfile(os.path.join(raw, month, name), destination)
        print(f'staged  {destination}{"  (stand-in from " + month + ")" if month != staged else ""}')

    hidden = os.path.join(target, HIDDEN)
    os.makedirs(hidden, exist_ok=True)
    duplicate = os.path.join(hidden, NAME.format(orbit='45264'))
    if not os.path.exists(duplicate):
        shutil.copyfile(os.path.join(target, '201010', NAME.format(orbit='45264')), duplicate)
    stray = os.path.join(target, '.DS_Store')
    if not os.path.exists(stray):
        open(stray, 'w').close()
    print('done')


if __name__ == '__main__':
    main()
