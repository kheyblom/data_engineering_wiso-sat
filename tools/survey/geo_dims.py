"""Header-only: obs counts per file, and geolocation/vertical variable shapes.

Usage: geo_dims.py OBS_DIM FILE [FILE ...]
"""
import re
import sys

import h5netcdf

GEO = re.compile(r'(^|_|/)(lat|lon|latitude|longitude|time|pressure|altitude|height)',
                 re.IGNORECASE)


def walk(group, path, out):
    for name, var in group.variables.items():
        if GEO.search(f'{path}{name}'):
            out.append(f'{path}{name} {var.dimensions} {var.dtype}')
    for name, sub in group.groups.items():
        walk(sub, f'{path}{name}/', out)


def find_dim(handle, name):
    if name in handle.dimensions:
        return handle.dimensions[name].size
    for sub in handle.groups.values():
        size = find_dim(sub, name)
        if size is not None:
            return size
    return None


obs_dim, files = sys.argv[1], sys.argv[2:]
sizes = []
for index, filename in enumerate(files):
    with h5netcdf.File(filename, 'r') as handle:
        sizes.append(find_dim(handle, obs_dim))
        if index == 0:
            geo = []
            walk(handle, '', geo)
print(f'{obs_dim}: per-file {sizes}  mean {sum(sizes) / len(sizes):,.0f}')
for line in geo:
    print(f'  {line}')
