"""Audit every SCIAMACHY orbit file: does it open, what does it hold, and where is fill?

Written 2026-10-22 before the SCIAMACHY reader (issue S2 in
``docs/products/sciamachy.md``). TROPOMI's audit found shells and partial
files by unwritten chunks; SCIAMACHY's datasets are contiguous, so that test
does not apply and this audit reads every value instead. The files are ~4 MB
(173 GB in all), so it runs as a batch job over a process pool.

Only the ``YYYYMM`` month folders are walked. The raw tree also holds hidden
``.ArchiveServiceTemp.sb-*`` folders, left by an interrupted transfer, whose
files duplicate the month folders' (found 2026-10-22).

Per file it records:

- ``version``, ``title``, ``nobs``, and a layout signature (every dataset's
  name, trailing shape, dtype and units), so format drift shows up;
- the first and last decoded time, whether time is non-decreasing, and
  whether the file's month matches its folder;
- per dataset on ``nobs``: how many values are the netCDF default fill
  (float 9.96921e36, int -2147483647), NaN, or unallocated storage;
- rows whose time, lat or lon is fill (candidates to leave out);
- lat/lon outside their ranges, and the counts of each quality flag value.

Every file lands in one category: ``unreadable``, ``wrong_version``,
``empty`` (nobs 0), ``partial`` (some row's time, lat or lon is fill) or
``ok``. Run from the repo root:

    .venv/bin/python -I tools/survey/sciamachy_file_audit.py <output.jsonl> [--limit N]

It writes one JSON line per file and prints a summary; ``--summarize``
re-reads an existing output, and ``--redo-unreadable`` re-audits only the
files an existing output records as unreadable, in place.
"""

import collections
import datetime
import hashlib
import json
import multiprocessing
import os
import re
import sys
import time

import h5py
import numpy as np

RAW = '/glade/derecho/scratch/kheyblom/data/wisosat/raw/SCIAMACHY/HDO_SICORv10'
MONTH_RE = re.compile(r'^\d{6}$')
FILE_RE = re.compile(r'^sci_l2_h2o_hdo_0110_(\d{5})\.nc$')
VERSION = '8.1'
FLOAT_FILL = np.float32(9.96921e36)
INT_FILL = -2147483647
FLAG = 'diagnostics/processing_quality_flags'


def text(value):
    return value.decode() if isinstance(value, bytes) else str(value)


def walk():
    """Every orbit file in the month folders, in orbit order."""
    files = []
    for month in sorted(entry for entry in os.listdir(RAW) if MONTH_RE.match(entry)):
        files += [f'{RAW}/{month}/{name}' for name in os.listdir(f'{RAW}/{month}') if FILE_RE.match(name)]
    return sorted(files, key=lambda path: path[-8:-3])


def decode(row):
    # the millisecond field reaches 1000 in 759 files, meaning the next whole
    # second (found by the first audit run, 2026-10-22), so it is added, not set
    year, month, day, hour, minute, second, millisecond = (int(v) for v in row)
    return (datetime.datetime(year, month, day, hour, minute, second)
            + datetime.timedelta(milliseconds=millisecond))


def audit(path):
    """Read one file whole and count what it holds; never raises."""
    record = {'file': path[len(RAW) + 1:], 'size': os.stat(path).st_size}
    try:
        with h5py.File(path, 'r') as handle:
            record['version'] = text(handle.attrs.get('version', b''))
            record['title'] = text(handle.attrs.get('title', b''))
            nobs = record['nobs'] = int(handle['instrument/time'].shape[0])
            layout, fills = [], {}

            def scan(name, item):
                if not isinstance(item, h5py.Dataset):
                    return
                layout.append(f'{name}|{item.shape[1:]}|{item.dtype}|{text(item.attrs.get("units", ""))}')
                if item.ndim == 0 or item.shape[0] != nobs or '/' not in name:
                    return
                values = item[()]
                entry = {}
                if item.id.get_storage_size() == 0 and values.size:
                    entry['unallocated'] = 1
                if values.dtype.kind == 'f':
                    entry['fill'] = int((values == FLOAT_FILL).sum())
                    entry['nan'] = int(np.isnan(values).sum())
                elif values.dtype.kind == 'i':
                    entry['fill'] = int((values == INT_FILL).sum())
                entry = {k: v for k, v in entry.items() if v}
                if entry:
                    fills[name] = entry

            handle.visititems(scan)
            record['layout'] = hashlib.sha1('\n'.join(sorted(layout)).encode()).hexdigest()[:12]
            record['fills'] = fills
            if nobs:
                times = handle['instrument/time'][()]
                lat = handle['instrument/latitude_center'][()]
                lon = handle['instrument/longitude_center'][()]
                bad_time = (times == INT_FILL).any(axis=1)
                bad = bad_time | (lat == FLOAT_FILL) | np.isnan(lat) | (lon == FLOAT_FILL) | np.isnan(lon)
                record['rows_not_observed'] = int(bad.sum())
                good = times[~bad_time]
                if len(good):
                    decoded = [decode(row) for row in good]
                    record['first'] = decoded[0].isoformat()
                    record['last'] = decoded[-1].isoformat()
                    record['time_sorted'] = all(a <= b for a, b in zip(decoded, decoded[1:]))
                    folder = record['file'][:6]
                    record['month_mismatch'] = sum(f'{d.year}{d.month:02d}' != folder for d in decoded)
                ok = ~bad
                record['lat_out'] = int((np.abs(lat[ok]) > 90).sum())
                record['lon_out'] = int((np.abs(lon[ok]) > 180).sum())
                flags, counts = np.unique(handle[FLAG][()], return_counts=True)
                record['flags'] = {str(int(f)): int(c) for f, c in zip(flags, counts)}
    except Exception as error:
        record['error'] = f'{type(error).__name__}: {str(error)[:160]}'
    record['category'] = categorize(record)
    return record


def categorize(record):
    if 'error' in record:
        return 'unreadable'
    if record['version'] != VERSION:
        return 'wrong_version'
    if record['nobs'] == 0:
        return 'empty'
    if record['rows_not_observed']:
        return 'partial'
    return 'ok'


def summarize(path):
    records = [json.loads(line) for line in open(path)]
    counts = collections.Counter(r['category'] for r in records)
    print(f'{len(records)} files: {dict(sorted(counts.items()))}')
    print(f'nobs total {sum(r.get("nobs", 0) for r in records):,}; '
          f'rows not observed {sum(r.get("rows_not_observed", 0) for r in records):,}')
    for r in records:
        if r['category'] in ('unreadable', 'wrong_version', 'empty'):
            print(f'  {r["category"]}: {r["file"]} {r.get("error") or r.get("version") or r["size"]}')
    layouts = collections.Counter(r.get('layout') for r in records if 'layout' in r)
    print(f'layouts: {dict(layouts)}; titles: {dict(collections.Counter(r.get("title") for r in records))}')
    for key in ('time_sorted',):
        print(f'{key} false: {[r["file"] for r in records if r.get(key) is False][:20]}')
    for key in ('month_mismatch', 'lat_out', 'lon_out'):
        hits = [(r['file'], r[key]) for r in records if r.get(key)]
        print(f'{key}: {len(hits)} files {hits[:10]}')
    # observations shared between consecutive orbits: the next file starts before this one ends
    timed = sorted((r for r in records if 'first' in r), key=lambda r: r['file'][-8:-3])
    overlaps = [(a['file'], b['file'], a['last'], b['first'])
                for a, b in zip(timed, timed[1:]) if b['first'] <= a['last']]
    print(f'time overlaps between consecutive orbits: {len(overlaps)} {overlaps[:10]}')
    print(f'record {timed[0]["first"] if timed else None} .. {timed[-1]["last"] if timed else None}')
    totals = collections.defaultdict(collections.Counter)
    files_with = collections.Counter()
    for r in records:
        for name, entry in r.get('fills', {}).items():
            totals[name].update(entry)
            files_with[name] += 1
    nobs = sum(r.get('nobs', 0) for r in records)
    print('fill / NaN by dataset (values; files):')
    for name in sorted(totals):
        print(f'  {name}: {dict(totals[name])}; {files_with[name]} files (nobs total {nobs:,})')
    flags = collections.Counter()
    for r in records:
        flags.update(r.get('flags', {}))
    print(f'quality flags: {dict(sorted(flags.items(), key=lambda kv: int(kv[0])))}')
    by_year = collections.defaultdict(collections.Counter)
    for r in records:
        by_year[r['file'][:4]][r['category']] += 1
    for year, year_counts in sorted(by_year.items()):
        print(f'  {year}: {dict(sorted(year_counts.items()))}')


def main():
    if sys.argv[1] == '--summarize':
        summarize(sys.argv[2])
        return
    if sys.argv[1] == '--redo-unreadable':
        path = sys.argv[2]
        records = [json.loads(line) for line in open(path)]
        records = [audit(f'{RAW}/{r["file"]}') if r['category'] == 'unreadable' else r for r in records]
        with open(path, 'w') as handle:
            handle.writelines(json.dumps(r) + '\n' for r in records)
        summarize(path)
        return
    output = sys.argv[1]
    started = time.time()
    files = walk()
    if '--limit' in sys.argv:
        # an even spread over the record, for a timing probe
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
        files = files[::max(1, len(files) // limit)][:limit]
    workers = len(os.sched_getaffinity(0))
    print(f'{len(files)} files, {workers} workers', flush=True)
    with open(output, 'w') as handle, multiprocessing.Pool(workers) as pool:
        for count, record in enumerate(pool.imap_unordered(audit, files, chunksize=8), 1):
            handle.write(json.dumps(record) + '\n')
            if count % 2000 == 0:
                handle.flush()
                print(f'{count} files in {time.time() - started:.0f} s', flush=True)
    print(f'done in {time.time() - started:.0f} s')
    summarize(output)


if __name__ == '__main__':
    main()
