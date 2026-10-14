"""Magnitude check: percentiles of named variables after declared-fill masking.

Usage: value_check.py FILE VAR [VAR ...]   (VAR may be group/var)
A VAR suffixed with '@good' is also reported restricted to the observations
passing a quality mask given by --good group/var==value.
"""
import argparse

import h5netcdf
import numpy as np

SENTINEL_LOW = -900.0  # report leftovers at or below this as suspect fill
SENTINEL_HIGH = 1e30


def text(value):
    return value.decode(errors='replace') if isinstance(value, bytes) else str(value)


def decoded(var):
    data = var[...].astype('f8')
    notes = []
    for key in ('_FillValue', 'missing_value', 'FillValue'):
        if key in var.attrs:
            fill = np.atleast_1d(var.attrs[key]).astype('f8')
            data[np.isin(data, fill)] = np.nan
            notes.append(f'{key}={fill.tolist()}')
    scale = var.attrs.get('scale_factor')
    offset = var.attrs.get('add_offset')
    if scale is not None or offset is not None:
        data = data * (scale if scale is not None else 1) + (offset if offset is not None else 0)
        notes.append(f'scale={scale} offset={offset}')
    return data, notes


def summary(data):
    finite = data[np.isfinite(data)]
    suspect = finite[(finite <= SENTINEL_LOW) | (finite >= SENTINEL_HIGH)]
    clean = finite[(finite > SENTINEL_LOW) & (finite < SENTINEL_HIGH)]
    if clean.size == 0:
        return f'n={finite.size} no clean values; suspect={np.unique(suspect)[:5]}'
    p = np.percentile(clean, [1, 50, 99])
    out = (f'n={clean.size:>10,} p1={p[0]: .4g} p50={p[1]: .4g} p99={p[2]: .4g} '
           f'min={clean.min(): .4g} max={clean.max(): .4g}')
    if suspect.size:
        values, counts = np.unique(suspect, return_counts=True)
        top = sorted(zip(counts, values))[-3:]
        out += f' | SUSPECT {suspect.size:,}: ' + ', '.join(f'{v:.6g}x{c}' for c, v in top)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file')
    parser.add_argument('variables', nargs='+')
    parser.add_argument('--good', help='group/var==value quality mask')
    args = parser.parse_args()
    with h5netcdf.File(args.file, 'r') as handle:
        good = None
        if args.good:
            name, value = args.good.split('==')
            good = handle[name][...] == float(value)
        print(f'=== {args.file.rsplit("/", 1)[-1]}')
        for spec in args.variables:
            name = spec.removesuffix('@good')
            var = handle[name]
            units = text(var.attrs.get('units', var.attrs.get('Units', '<none>')))
            data, notes = decoded(var)
            print(f'  {name} {var.shape} units={units!r} {" ".join(notes)}')
            print(f'      all : {summary(data)}')
            if spec.endswith('@good') and good is not None:
                mask = good.reshape(good.shape + (1,) * (data.ndim - good.ndim))
                print(f'      good: {summary(np.where(mask, data, np.nan))}')


main()
