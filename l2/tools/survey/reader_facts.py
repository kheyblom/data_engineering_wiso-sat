"""Header-only facts a product reader needs: groups, dims, time and fill encodings."""
import sys

import h5netcdf

FILL_KEYS = ('_FillValue', 'missing_value', 'FillValue', 'MissingValue')


def text(value):
    return value.decode(errors='replace') if isinstance(value, bytes) else str(value)


def walk(group, path, out):
    dims = {k: v.size for k, v in group.dimensions.items()}
    out.append(f'  group /{path} dims={dims} nvars={len(group.variables)}')
    fills = set()
    for name, var in group.variables.items():
        attrs = var.attrs
        for key in FILL_KEYS:
            if key in attrs:
                fills.add(f'{key}={text(attrs[key])[:20]}')
        if name.lower() in ('time', 'yyyymmdd', 'time_string', 'ut_hour') or 'time' == name.lower()[-4:]:
            unit = text(attrs.get('units', attrs.get('Units', '<none>')))
            out.append(f'    time-like {path}{name} {var.dimensions} {var.dtype} units={unit!r}'
                       f' calendar={text(attrs.get("calendar", "-"))}')
    if fills:
        out.append(f'    fill attrs seen: {sorted(fills)}')
    for name, sub in group.groups.items():
        walk(sub, f'{path}{name}/', out)


for filename in sys.argv[1:]:
    print(f'=== {filename.rsplit("/", 1)[-1]}')
    with h5netcdf.File(filename, 'r') as handle:
        print('  root attrs:', {k: text(v)[:60] for k, v in list(handle.attrs.items())[:12]})
        out = []
        walk(handle, '', out)
        print('\n'.join(out))
