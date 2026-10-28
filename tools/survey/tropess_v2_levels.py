"""Scan every TROPESS v2 file's vertical levels, and the cross-type checks behind R41-R43.

Written 2026-10-28 for the user's question on v2's 34-wide level dimension
(``docs/products/tropess.md``, "v2: answers ... and first probes", R42). One
day's probes found every retrieval-grid array written only on levels 0-16 of
the 34, with three exceptions: Full ``pressure_ret`` repeats the grid in
17-33, ``air_density`` holds two identical copies, and Standard ``altitude``
holds other targets' altitudes (R43). This checks every file of every v2
collection (AIRS and CrIS-JPSS1; Summary, Standard and Full). A task is one
instrument-day, all three types read whole. It records:

- per file: rows, algorithm and format, and for every dataset with a 34- or
  67-wide axis, how many rows have a written value (not -999, -9999 or NaN)
  at each index of that axis, and for each 34-wide axis how many rows have
  a value in 17-33 that differs from its copy in 0-16;
- across types (Summary, Standard, Full of one day):
  - R41: Standard's rows are Full's rows with ``quality == 1``, in order;
    Summary's rows are Standard's;
  - Summary equals Standard's levels 0-16 in every shared profile;
  - R43: Standard ``altitude`` flattened to (2n, 17) has Summary's altitude
    of targets 0..n-1 in its first n rows, and what the rest holds;
  - Full ``air_density`` 0-33 equals Standard's times N_A, and 34-66 is fill.

The int8-packed blocks (1-D byte arrays) are not read. Run from the repo
root, as a batch job (it reads every v2 file, ~117 GB):

    .venv/bin/python -I tools/survey/tropess_v2_levels.py <output.jsonl> [--limit N]

It writes one JSON line per instrument-day and prints a summary;
``--summarize`` re-reads an existing output.
"""

import collections
import json
import multiprocessing
import os
import re
import sys
import time

import h5py
import numpy as np

RAW = '/glade/derecho/scratch/kheyblom/data/wisosat/raw'
# per instrument: the v2 collection folder of each type (one subfolder per year)
FOLDERS = {
    'AIRS': {'Summary': 'AIRS/TRPSYL2HDOAIRSFS.2', 'Standard': 'AIRS/TRPSDL2HDOAIRSFS.2',
             'Full': 'AIRS/TRPSFL2HDOAIRSFS.2'},
    'CrIS': {'Summary': 'CRIS/TRPSYL2HDOCRS1FS.2', 'Standard': 'CRIS/TRPSDL2HDOCRS1FS.2',
             'Full': 'CRIS/TRPSFL2HDOCRS1FS.2'},
}
FILE_RE = re.compile(r'^TROPESS_(?P<token>AIRS-Aqua|CrIS-JPSS1)_L2_(?P<kind>Summary|Standard|Full)_HDO_'
                     r'(?P<day>\d{8})_MUSES_(?P<algorithm>R1p\d+)_FS_(?P<format>F\dp\d+)(?P<joint>_J\d)?\.nc$')
KINDS = ('Summary', 'Standard', 'Full')
FILLS = (-999, -9999)
WIDE = (34, 67)
NA = 6.02214076e23
# Summary profiles compared with Standard's levels 0-16
PROFILES = ('x', 'x_h2o', 'pressure')


def written(values):
    """True where a value is written: not -999, -9999 or NaN."""
    if values.dtype.kind == 'f':
        return ~(np.isin(values, FILLS) | np.isnan(values))
    return ~np.isin(values, FILLS)


def same(a, b):
    """Rows of a and b equal, fill (any of -999, -9999, NaN) counting as equal."""
    wa, wb = written(a), written(b)
    eq = (wa == wb) & (~wa | (a == b))
    return eq.reshape(len(eq), -1).all(axis=1)


def listing():
    """Every instrument-day, with the path of each type present."""
    days = collections.defaultdict(dict)
    for instrument, folders in FOLDERS.items():
        for kind, folder in folders.items():
            base = f'{RAW}/{folder}'
            for sub in sorted(d for d in os.listdir(base) if d.isdigit()):
                for name in os.listdir(f'{base}/{sub}'):
                    match = FILE_RE.match(name)
                    if match and match['kind'] == kind:
                        if kind in days[(instrument, match['day'])]:
                            raise SystemExit(f'two {kind} files for {instrument} {match["day"]}')
                        days[(instrument, match['day'])][kind] = f'{base}/{sub}/{name}'
    return [{'instrument': i, 'day': d, **paths} for (i, d), paths in sorted(days.items())]


def levels(handle):
    """Per dataset with a 34- or 67-wide axis: written rows per index, and copy mismatches."""
    nobs = handle['time'].shape[0]
    out = {}

    def visit(name, item):
        if not isinstance(item, h5py.Dataset) or item.dtype.kind not in 'fiu':
            return
        wide = [axis for axis, size in enumerate(item.shape) if axis and size in WIDE]
        if not wide or item.shape[0] != nobs:
            return
        values = item[()]
        mask = written(values)
        entry = {'shape': list(item.shape[1:])}
        for axis in wide:
            others = tuple(a for a in range(1, values.ndim) if a != axis)
            per_index = mask.any(axis=others) if others else mask
            entry[f'rows_written_axis{axis}'] = per_index.sum(axis=0).tolist()
            if item.shape[axis] == 34:
                low = np.take(values, range(17), axis=axis)
                high = np.take(values, range(17, 34), axis=axis)
                entry[f'rows_copy_differs_axis{axis}'] = int((~same(low, high)).sum())
        out[name] = entry

    handle.visititems(visit)
    return out


def keys(handle):
    return list(zip(handle['time'][()].tolist(), handle['latitude'][()].tolist(), handle['longitude'][()].tolist()))


def cross_checks(h):
    """R41, Summary vs Standard, R43 and air_density, for the types present."""
    out = {}
    if 'Standard' in h and 'Full' in h:
        std, full = h['Standard'], h['Full']
        position = {k: i for i, k in enumerate(keys(full))}
        index = np.array([position.get(k, -1) for k in keys(std)])
        quality = full['quality'][()]
        out['std_rows_not_in_full'] = int((index < 0).sum())
        out['std_in_full_order'] = bool(np.all(np.diff(index[index >= 0]) > 0))
        selected = np.zeros(len(quality), bool)
        selected[index[index >= 0]] = True
        out['full_quality1_not_in_std'] = int((selected != (quality == 1)).sum())
        out['full_rows'], out['full_quality1'] = int(len(quality)), int((quality == 1).sum())
        mine = std['retrieval/air_density'][()].astype('f8')
        theirs = full['retrieval/air_density'][()].astype('f8')[index]
        both = written(mine) & written(theirs[:, :34])
        rel = np.abs(theirs[:, :34][both] / NA - mine[both]) / np.maximum(np.abs(mine[both]), 1e-6)
        out['air_density_fill_pattern_differs'] = int((written(mine) != written(theirs[:, :34])).sum())
        out['air_density_max_rel'] = float(rel.max()) if rel.size else None
        out['full_air_density_34_66_written'] = int(written(full['retrieval/air_density'][()][:, 34:]).sum())
    if 'Summary' in h and 'Standard' in h:
        summ, std = h['Summary'], h['Standard']
        out['summary_rows_equal_std'] = keys(summ) == keys(std)
        if out['summary_rows_equal_std']:
            out['summary_differs_from_std_0_16'] = {
                name: int((~same(summ[name][()], std[name][()][:, :17])).sum()) for name in PROFILES}
            n = std['time'].shape[0]
            flat = std['altitude'][()].reshape(2 * n, 17)
            out['altitude_shift_rows_equal'] = int(same(flat[:n], summ['altitude'][()]).sum())
            out['altitude_own_rows_equal'] = int(same(std['altitude'][()][:, :17], summ['altitude'][()]).sum())
            rest = flat[n:]
            out['altitude_rest_rows'] = {'all_fill': int((~written(rest)).all(axis=1).sum()),
                                         'all_zero': int((rest == 0).all(axis=1).sum()),
                                         'other': int((~((~written(rest)).all(axis=1) | (rest == 0).all(axis=1))).sum())}
    return out


def audit(entry):
    """One instrument-day: each type read whole; never raises."""
    record = {'instrument': entry['instrument'], 'day': entry['day'], 'kinds': [k for k in KINDS if k in entry]}
    handles = {}
    try:
        for kind in record['kinds']:
            path = entry[kind]
            handles[kind] = h5py.File(path, 'r')
            match = FILE_RE.match(os.path.basename(path))
            record[kind] = {'file': path[len(RAW) + 1:], 'nobs': int(handles[kind]['time'].shape[0]),
                            'algorithm': match['algorithm'], 'format': match['format'] + (match['joint'] or ''),
                            'levels': levels(handles[kind])}
        record['cross'] = cross_checks(handles)
    except Exception as error:
        record['error'] = f'{type(error).__name__}: {str(error)[:200]}'
    finally:
        for handle in handles.values():
            handle.close()
    return record


def summarize(path):
    records = [json.loads(line) for line in open(path)]
    for instrument in dict.fromkeys(r['instrument'] for r in records):
        rs = sorted((r for r in records if r['instrument'] == instrument), key=lambda r: r['day'])
        print(f'=== {instrument}: {len(rs)} days, {rs[0]["day"]} .. {rs[-1]["day"]}; '
              f'errors {sum("error" in r for r in rs)}')
        for r in rs:
            if 'error' in r:
                print(f'  ERROR {r["day"]}: {r["error"]}')
        for kind in KINDS:
            ks = [r[kind] for r in rs if kind in r]
            print(f'  {kind}: {len(ks)} files, {sum(k["nobs"] for k in ks):,} obs; '
                  f'algorithms {dict(collections.Counter(k["algorithm"] + " " + k["format"] for k in ks))}')
            merged = collections.defaultdict(lambda: collections.defaultdict(lambda: None))
            for k in ks:
                for name, entry in k['levels'].items():
                    for field, value in entry.items():
                        if field.startswith('rows_written'):
                            prev = merged[name][field]
                            merged[name][field] = value if prev is None else [a + b for a, b in zip(prev, value)]
                        elif field.startswith('rows_copy_differs'):
                            merged[name][field] = (merged[name][field] or 0) + value
                        else:
                            merged[name][field] = value
            for name, entry in sorted(merged.items()):
                parts = [f'shape {entry["shape"]}']
                for field, value in entry.items():
                    if field.startswith('rows_written'):
                        ever = [i for i, v in enumerate(value) if v]
                        span = f'{ever[0]}..{ever[-1]}' if ever else 'none'
                        upper = sum(value[17:34]) if len(value) >= 34 else None
                        parts.append(f'{field[13:]}: indices written {span} ({len(ever)}), '
                                     f'row-writes at 17-33 {upper}')
                    elif field.startswith('rows_copy_differs'):
                        parts.append(f'{field[18:]}: rows where 17-33 differs from 0-16 {value:,}')
                print(f'    {name}: ' + '; '.join(parts))
        cs = [r['cross'] for r in rs if 'cross' in r]
        total = lambda field: sum(c.get(field, 0) or 0 for c in cs)
        print(f'  R41: Standard rows not in Full {total("std_rows_not_in_full")}; days out of order '
              f'{sum(not c["std_in_full_order"] for c in cs if "std_in_full_order" in c)}; Full rows where '
              f'quality == 1 and being in Standard disagree {total("full_quality1_not_in_std")} '
              f'(Full {total("full_rows"):,} rows, quality 1 {total("full_quality1"):,})')
        print(f'  Summary rows == Standard rows: {sum(c.get("summary_rows_equal_std", False) for c in cs)} of '
              f'{sum("summary_rows_equal_std" in c for c in cs)} days; differing rows vs Standard 0-16: '
              f'{dict(sum((collections.Counter(c.get("summary_differs_from_std_0_16", {})) for c in cs), collections.Counter()))}')
        print(f'  R43: Standard altitude rows equal by the shift {total("altitude_shift_rows_equal"):,}; '
              f'by its own row {total("altitude_own_rows_equal"):,}; the rest '
              f'{dict(sum((collections.Counter(c.get("altitude_rest_rows", {})) for c in cs), collections.Counter()))}')
        print(f'  air_density: Full 0-33 vs Standard x N_A, fill pattern differs {total("air_density_fill_pattern_differs")}, '
              f'max rel {max((c.get("air_density_max_rel") or 0) for c in cs):.2e}; '
              f'Full 34-66 written {total("full_air_density_34_66_written")}')
        print(f'  days missing a type: {[(r["day"], r["kinds"]) for r in rs if len(r["kinds"]) < 3]}')


def main():
    if sys.argv[1] == '--summarize':
        summarize(sys.argv[2])
        return
    output = sys.argv[1]
    started = time.time()
    days = listing()
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
        days = [d for inst in FOLDERS for d in (lambda s: s[::max(1, len(s) // limit)][:limit])(
            [d for d in days if d['instrument'] == inst])]
    workers = len(os.sched_getaffinity(0))
    print(f'{len(days)} instrument-days, {workers} workers', flush=True)
    with open(output, 'w') as handle, multiprocessing.Pool(workers) as pool:
        for count, record in enumerate(pool.imap_unordered(audit, days, chunksize=1), 1):
            handle.write(json.dumps(record) + '\n')
            if count % 20 == 0:
                handle.flush()
                print(f'{count} instrument-days in {time.time() - started:.0f} s', flush=True)
    print(f'done in {time.time() - started:.0f} s')
    summarize(output)


if __name__ == '__main__':
    main()
