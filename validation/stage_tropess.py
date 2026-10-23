"""Stage the miniature AIRS RS and FS raw trees the pipeline test runs against.

Each fixture is real TROPESS files in the real folder layout, chosen to
exercise what the AIRS reader does beyond the shared code
(``docs/products/tropess.md``):

- **RS, copied whole** (~6 MB a day): 2002-08-30 and -31, the two real days
  upstream has no Summary file for (one-sided, declared); 2002-09-01 and -03,
  both files. 2002-09-02 is left out, so the build's missing-day check sees a
  gap (a fixture gap, not an upstream one).
- **FS, cut** (a day is ~60 MB): each file is written with the first
  ``FS_ROWS`` Standard rows (the first half, and the Standard rows of the first
  Summary rows) and the Summary rows that match them, which keeps
  every invariant the reader checks: Summary is the Standard rows with
  DOF > 1.1, in order, and the first row (R22) is kept. 2022-06-17 and -18,
  both files; 2022-06-19, a real day upstream has no Standard file for; 06-20
  left out (a fixture gap); 06-21, both files, its Standard file written to a
  year folder of the later download's layout, so both layouts are read.
- **Strays** the reader must skip: an L3 file name and a local ``_target``
  copy name, as the real FS folder holds (R5, R6), written empty.

Run from the repo root (reads ~0.3 GB, light enough for a login node):

    uv run python validation/stage_tropess.py

Idempotent: a file that is already staged is left alone unless --restage.
"""

from __future__ import annotations

import argparse
import os
import shutil

import netCDF4
import numpy as np

import products.tropess as reader
from products.tropess import list_granules, match_rows
from utils.path_utils import listing_options, load_config

# product -> (production config, fixture config, days, cut)
FIXTURES = {
    'airs_rs': ('config/airs_rs/config_zarr.yaml', 'config/airs_rs/config_zarr_fixture.yaml',
                ('20020830', '20020831', '20020901', '20020903'), False),
    'airs_fs': ('config/airs_fs/config_zarr.yaml', 'config/airs_fs/config_zarr_fixture.yaml',
                ('20220617', '20220618', '20220619', '20220621'), True),
}
FS_ROWS = 400
# an FS day whose Standard file is staged in the later download's year layout
RELOCATED = ('20220621', 'TRPSDL2HDOAIRSFS.1', '2022')
STRAYS = ('AIRS_TROPESS_gridded_20220617_1deg.nc',
          'TROPESS_AIRS-Aqua_L2_Standard_HDO_20220617_MUSES_R1p17_FS_F0p4_target.nc')


def copy_group(src, dst, rows):
    """Copy a netCDF group, cutting every variable on ``target`` to some rows.

    Args:
        src (netCDF4.Group): The source group.
        dst (netCDF4.Group): The target group, empty.
        rows (numpy.ndarray | None): The ``target`` rows to keep; None keeps all.
    """
    src.set_auto_maskandscale(False)
    dst.setncatts({name: src.getncattr(name) for name in src.ncattrs()})
    for name, dim in src.dimensions.items():
        size = len(rows) if name == 'target' and rows is not None else dim.size
        dst.createDimension(name, size)
    for name, variable in src.variables.items():
        fill = variable.getncattr('_FillValue') if '_FillValue' in variable.ncattrs() else False
        out = dst.createVariable(name, variable.datatype, variable.dimensions, zlib=True,
                                 complevel=1, fill_value=fill)
        out.setncatts({key: variable.getncattr(key) for key in variable.ncattrs() if key != '_FillValue'})
        out.set_auto_maskandscale(False)
        values = variable[...]
        if rows is not None and variable.dimensions and variable.dimensions[0] == 'target':
            values = values[rows]
        out[...] = values
    for name, group in src.groups.items():
        copy_group(group, dst.createGroup(name), rows)


def cut_rows(paths):
    """The rows each file of a day keeps: the first Standard rows, and Summary's matches.

    Args:
        paths (tuple): The day's files, Standard first.

    Returns:
        list: Per file, an int array of rows.
    """
    handles = [netCDF4.Dataset(path) for path in paths]
    try:
        keys = [{source: np.asarray(handle[source][...]) for source in ('time', 'latitude', 'longitude')}
                for handle in handles]
    finally:
        for handle in handles:
            handle.close()
    half = FS_ROWS // 2
    if len(paths) == 1:
        return [np.arange(min(FS_ROWS, keys[0]['time'].size))]
    # the first rows (row 0 is the declared defect), and the Standard rows of
    # the first Summary rows: an FS file is in processing order, and its first
    # few hundred rows can all have DOF <= 1.1, so none would be in Summary
    matched = match_rows(keys[0], keys[1])
    standard = np.union1d(np.arange(min(half, keys[0]['time'].size)), matched[:half])
    summary = np.where(np.isin(matched, standard))[0]
    return [standard, summary]


def stage(production, fixture, days, cut, restage):
    """Write one fixture's days from the production raw tree.

    Args:
        production (str): The production config, for the raw root and listing.
        fixture (str): The fixture config, for the fixture's raw root.
        days (tuple): Granule ids to stage.
        cut (bool): Cut the files to ``FS_ROWS`` Standard rows.
        restage (bool): Overwrite files already staged.
    """
    settings = load_config(production)
    raw = settings['directories']['raw']
    target = load_config(fixture)['directories']['raw']
    granules = {granule.id: granule for granule in list_granules(raw, **listing_options(settings, reader))}
    for day in days:
        paths = granules[day].paths
        rows = cut_rows(paths) if cut else [None] * len(paths)
        for path, keep in zip(paths, rows):
            relative = os.path.relpath(path, raw)
            if RELOCATED[0] == day and '_Standard_' in path:
                relative = os.path.join(RELOCATED[1], RELOCATED[2], os.path.basename(path))
            destination = os.path.join(target, relative)
            if os.path.exists(destination) and not restage:
                print(f'kept    {destination}')
                continue
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            if keep is None:
                shutil.copyfile(path, destination)
            else:
                with netCDF4.Dataset(path) as src, netCDF4.Dataset(destination, 'w') as dst:
                    copy_group(src, dst, keep)
            print(f'staged  {destination}  {"whole" if keep is None else f"{len(keep)} rows"}')
    if cut:
        folder = os.path.dirname(os.path.join(target, os.path.relpath(granules[days[0]].paths[0], raw)))
        for name in STRAYS:
            stray = os.path.join(folder, name)
            if not os.path.exists(stray):
                open(stray, 'w').close()


def main():
    parser = argparse.ArgumentParser(description='stage the airs rs and fs pipeline test fixtures.')
    parser.add_argument('--restage', action='store_true', help='Overwrite staged files.')
    parser.add_argument('--products', type=str, default=','.join(FIXTURES),
                        help=f'Comma separated subset of {sorted(FIXTURES)}. Default: both.')
    args = parser.parse_args()
    for product in args.products.split(','):
        production, fixture, days, cut = FIXTURES[product]
        stage(production, fixture, days, cut, args.restage)
    print('done')


if __name__ == '__main__':
    main()
