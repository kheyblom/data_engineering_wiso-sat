"""Header-only scan: print water / HDO / delta-D variables with their units."""
import re
import sys

import h5netcdf

PATTERN = re.compile(
    r'h2o|hdo|water|delta|dd\b|^dd|ratio|vapo|iwv|tcwv|wv|xh2o|column|vmr|isotop',
    re.IGNORECASE,
)
SKIP = {'DIMENSION_LIST', 'REFERENCE_LIST', 'CLASS', 'NAME', '_Netcdf4Dimid',
        '_Netcdf4Coordinates'}


def text(value):
    if isinstance(value, bytes):
        return value.decode(errors='replace')
    return str(value)


def walk(group, path=''):
    for name, var in group.variables.items():
        attrs = {k: text(v)[:110] for k, v in var.attrs.items() if k not in SKIP}
        blob = ' '.join([name] + [attrs.get(k, '') for k in
                                  ('long_name', 'standard_name', 'description')])
        if PATTERN.search(blob):
            keep = {k: attrs[k] for k in ('units', 'Units', 'long_name',
                                          'standard_name', 'description',
                                          'comment', 'definition')
                    if k in attrs}
            print(f'  {path}{name} {var.dimensions} {var.dtype}  {keep}')
    for name, sub in group.groups.items():
        walk(sub, f'{path}{name}/')


for filename in sys.argv[1:]:
    print(f'=== {filename.rsplit("/", 1)[-1]}')
    try:
        with h5netcdf.File(filename, 'r', decode_vlen_strings=True) as handle:
            for key in ('title', 'version', 'product_version', 'institution',
                        'source', 'ProductLevel'):
                if key in handle.attrs:
                    print(f'  @{key}: {text(handle.attrs[key])[:120]}')
            walk(handle)
    except Exception as error:  # noqa: BLE001 -- report and move on
        print(f'  ERROR {type(error).__name__}: {error}')
