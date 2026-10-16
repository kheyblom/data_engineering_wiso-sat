"""Stage the miniature TROPOMI raw tree the pipeline test runs against.

A real orbit file is ~1 GB, and a test that needs a batch job stops being run.
This writes five real orbits cut to a window of whole scanlines each, keeping
everything the pipeline reads exactly as SRON wrote it: group layout, dimension
names, dtypes, variable and root attributes, and the undeclared netCDF default
fills. The test runs on a login node in about a minute.

Chosen deliberately (see config/tropomi/config_zarr_fixture.yaml):

- **Days 2020-06-16, 06-17 and 06-19.** 06-18 is a real upstream gap, so the
  build's missing-day check sees one.
- **Windows of different lengths**, so orbits differ in size and appends land
  mid-chunk.
- **Mid-orbit windows**, which hold valid retrievals, float and int fill, and
  the NaNs SRON writes in ``deltad_precision``. Staging fails if any of those is
  absent, because the fixture exists to exercise them.
- **Whole scanlines**, so the verifier's swath-layout check still applies.
- **A stray .DS_Store**, as the real tree has, which the reader must skip.
- **Three real defect files, copied whole** (``DEFECTS``) into 2020-06-16
  as stand-ins; their own dates are in 2019. They are a shell, a partial
  orbit and a file truncated upstream (see the fixture config). Their orbit
  numbers sort before the 2020 orbits, so time still never decreases.
- **An empty orbit directory** (``EMPTY_ORBIT``), standing in for the 353
  orbits that are empty upstream. The fixture config declares it in
  ``expected_empty_granules``; orbit 13872 really does have a file upstream,
  so this is a stand-in, not a measurement.

Only the variables the pipeline reads are copied: every source in the key, the
coordinate sources, and ``scanline``/``ground_pixel`` for the layout check.

Run from the repo root (reads ~0.4 GB, light enough for a login node):

    uv run python validation/stage_tropomi.py

Idempotent: an orbit that is already staged is left alone unless --restage.
"""

from __future__ import annotations

import argparse
import os
import shutil

import netCDF4
import numpy as np

from utils.nomenclature import coordinates, variables
from utils.path_utils import load_config

PRODUCTION = 'config/tropomi/config_zarr.yaml'
FIXTURE = 'config/tropomi/config_zarr_fixture.yaml'

# (day, orbit, first scanline, scanlines): around the middle of each orbit
WINDOWS = (
    ('2020/06/16', '13857', 2066, 40),
    ('2020/06/17', '13870', 2070, 31),
    ('2020/06/17', '13871', 2060, 47),
    ('2020/06/19', '13899', 2075, 23),
    ('2020/06/19', '13900', 2064, 36),
)
PIXELS = 215

# an orbit directory left empty on purpose; see the module docstring
EMPTY_ORBIT = ('2020/06/17', '13872')

# real defect files (source day, orbit), copied whole under DEFECT_DAY
DEFECTS = (('2019/01/06', '6380'), ('2019/06/06', '8532'), ('2019/04/17', '7821'))
DEFECT_DAY = '2020/06/16'

# read for the verifier's layout check, though no store holds them
EXTRA_SOURCES = ('instrument/scanline', 'instrument/ground_pixel')


def sources():
    """Every source path the fixture must carry.

    Returns:
        list: ``<group>/<variable>`` paths.
    """
    found = [entry.original for entry in variables('tropomi').values()]
    found += [entry.original for entry in coordinates('tropomi').values()]
    return sorted(set(found) | set(EXTRA_SOURCES))


def stage_orbit(source_path, target_path, first, count):
    """Write one orbit cut to a window of whole scanlines.

    Args:
        source_path (str): The real orbit file.
        target_path (str): Where to write the fixture file.
        first (int): First scanline of the window.
        count (int): Scanlines in the window.

    Returns:
        dict: What the window holds, for the checks in ``main``.
    """
    window = slice(first * PIXELS, (first + count) * PIXELS)
    found = {'valid': 0, 'float_fill': 0, 'int_fill': 0, 'nan': 0}
    with netCDF4.Dataset(source_path, 'r') as src, netCDF4.Dataset(target_path, 'w') as dst:
        src.set_auto_maskandscale(False)
        dst.setncatts({name: src.getncattr(name) for name in src.ncattrs()})
        for name, dim in src.dimensions.items():
            dst.createDimension(name, count * PIXELS if name == 'nobs' else dim.size)
        for source in sources():
            group, name = source.split('/')
            variable = src[group][name]
            target_group = dst.groups.get(group) or dst.createGroup(group)
            # fill_value=False: SRON declares no _FillValue, and the fixture
            # must not gain one the real files lack
            out = target_group.createVariable(
                name, variable.dtype, variable.dimensions, zlib=True, complevel=1,
                shuffle=True, fill_value=False,
            )
            out.setncatts({key: variable.getncattr(key) for key in variable.ncattrs()})
            out.set_auto_maskandscale(False)
            values = variable[window]
            out[...] = values
            if values.dtype.kind == 'f':
                found['float_fill'] += int((values == np.float32(9.96921e36)).sum())
                found['nan'] += int(np.isnan(values).sum())
            elif source != 'instrument/time':
                found['int_fill'] += int((values == -2147483647).sum())
        h2o = src['target_product/h2o_column'][window]
        found['valid'] = int((h2o < 1e30).sum())
    return found


def main():
    parser = argparse.ArgumentParser(description='stage the tropomi pipeline test fixture.')
    parser.add_argument('--restage', action='store_true', help='Overwrite staged orbits.')
    args = parser.parse_args()

    raw = load_config(PRODUCTION)['directories']['raw']
    target = load_config(FIXTURE)['directories']['raw']
    totals = {'valid': 0, 'float_fill': 0, 'int_fill': 0, 'nan': 0}
    for day, orbit, first, count in WINDOWS:
        orbit_dir = os.path.join(raw, day, orbit)
        names = [name for name in os.listdir(orbit_dir) if name.endswith('.nc')]
        source_path = os.path.join(orbit_dir, names[0])
        target_dir = os.path.join(target, day, orbit)
        target_path = os.path.join(target_dir, names[0])
        if os.path.exists(target_path) and not args.restage:
            print(f'kept    {target_path}')
            continue
        os.makedirs(target_dir, exist_ok=True)
        found = stage_orbit(source_path, target_path, first, count)
        for key, value in found.items():
            totals[key] += value
        print(f'staged  {target_path}  {count * PIXELS} obs  {found}')

    os.makedirs(os.path.join(target, *EMPTY_ORBIT), exist_ok=True)
    for day, orbit in DEFECTS:
        source_dir = os.path.join(raw, day, orbit)
        name = [entry for entry in os.listdir(source_dir) if entry.endswith('.nc')][0]
        destination = os.path.join(target, DEFECT_DAY, orbit, name)
        if not os.path.exists(destination) or args.restage:
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copyfile(os.path.join(source_dir, name), destination)
            print(f'staged  {destination}  (defect stand-in from {day})')

    # the real tree has these, and the reader must walk past them
    stray = os.path.join(target, '2020', '.DS_Store')
    if not os.path.exists(stray):
        open(stray, 'w').close()

    if any(totals.values()):
        missing = [key for key, value in totals.items() if not value]
        if missing:
            raise SystemExit(f'the staged windows hold no {missing}; pick other windows')
    print('done')


if __name__ == '__main__':
    main()
