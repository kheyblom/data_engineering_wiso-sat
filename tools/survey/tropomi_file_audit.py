"""Audit every TROPOMI orbit file: does it open, and is everything the pipeline reads written?

Written 2026-10-16 after the re-download, when 109 small files turned out to be
shells (variables declared, no data written) and 2 to be truncated upstream.
The user asked for every file to be checked, not a sample.

Reads metadata only: per file, the root ``version`` attribute, the length of
``nobs``, and for each source the pipeline reads (the 16 store variables,
time/lat/lon, and the scanline/ground_pixel the verifier checks) whether any
data chunk was ever written. A dataset with no chunk reads back as nothing but
its fill value. Each check is a small random read in a ~1 GB file, which costs
~50 ms of Lustre latency, so the files are spread over a process pool and the
audit runs as a batch job, not on a login node.

Every file lands in exactly one category:

- ``ok``: opens, version 8.1, nobs a whole number of 215-pixel scanlines, and
  every source written;
- ``unreadable``: h5py cannot open it;
- ``wrong_version``: opens, but declares another processor version;
- ``shell``: ``time`` is unwritten, so the file holds no real observations;
- ``partial``: ``time`` is written, but at least one other source is not;
- ``bad_layout``: everything written, but nobs is not whole scanlines.

Empty orbit directories are counted separately. Run from the repo root:

    .venv/bin/python -I tools/survey/tropomi_file_audit.py <output.jsonl>

It writes one JSON line per file and prints the counts. With ``--summarize``
it only re-reads an existing output and prints the counts.
"""

import collections
import json
import multiprocessing
import os
import re
import sys
import time

import h5py

RAW = '/glade/derecho/scratch/kheyblom/data/wisosat/raw/TROPOMI/tropomi.grid.surfsara.nl/hdo'
FILE_RE = re.compile(r'^s5p_l2_hdo_(\d{4})_(\d{5})\.nc$')
VERSION = '8.1'
PIXELS = 215
SOURCES = (
    'instrument/time', 'instrument/latitude_center', 'instrument/longitude_center',
    'target_product/deltad', 'target_product/deltad_precision',
    'target_product/h2o_column', 'target_product/h2o_column_precision',
    'target_product/hdo_column', 'target_product/hdo_column_precision',
    'diagnostics/processing_quality_flags', 'diagnostics/iterations',
    'instrument/solar_zenith_angle', 'side_product/aerosol_optical_thickness',
    'side_product/aerosol_height', 'side_product/surface_albedo',
    'diagnostics/chi_squared', 'diagnostics/chi_squared_prefit',
    'diagnostics/number_of_spectral_points_in_retrieval',
    'diagnostics/number_of_spectral_points_in_prefit',
    'instrument/scanline', 'instrument/ground_pixel',
)


def digits(path):
    return sorted((entry for entry in os.listdir(path) if entry.isdigit()), key=int)


def walk():
    """Every orbit file, and every empty orbit directory, under RAW."""
    files, empty = [], []
    for year in digits(RAW):
        for month in digits(f'{RAW}/{year}'):
            for day in digits(f'{RAW}/{year}/{month}'):
                for orbit in digits(f'{RAW}/{year}/{month}/{day}'):
                    directory = f'{RAW}/{year}/{month}/{day}/{orbit}'
                    names = [name for name in os.listdir(directory) if FILE_RE.match(name)]
                    if not names:
                        empty.append(f'{year}/{month}/{day}/{orbit}')
                    files += [f'{directory}/{name}' for name in names]
    return files, empty


def audit(path):
    """Check one file's metadata; never raises."""
    record = {'file': path[len(RAW) + 1:], 'size': os.stat(path).st_size}
    try:
        with h5py.File(path, 'r') as handle:
            version = handle.attrs.get('version', b'')
            record['version'] = version.decode() if isinstance(version, bytes) else str(version)
            record['nobs'] = int(handle['instrument/time'].shape[0])
            record['unwritten'] = [s for s in SOURCES if handle[s].id.get_num_chunks() == 0]
    except Exception as error:
        record['error'] = f'{type(error).__name__}: {str(error)[:160]}'
    record['category'] = categorize(record)
    return record


def categorize(record):
    if 'error' in record:
        return 'unreadable'
    if record['version'] != VERSION:
        return 'wrong_version'
    if 'instrument/time' in record['unwritten']:
        return 'shell'
    if record['unwritten']:
        return 'partial'
    if record['nobs'] % PIXELS:
        return 'bad_layout'
    return 'ok'


def summarize(path, empty=None):
    records = [json.loads(line) for line in open(path)]
    counts = collections.Counter(r['category'] for r in records)
    print(f'{len(records)} files: {dict(sorted(counts.items()))}')
    if empty is not None:
        print(f'{len(empty)} empty orbit directories')
    partial = collections.Counter(tuple(r['unwritten']) for r in records if r['category'] == 'partial')
    for unwritten, count in partial.most_common():
        print(f'  partial x{count}: {len(unwritten)} unwritten: {list(unwritten)}')
    for r in records:
        if r['category'] in ('unreadable', 'wrong_version', 'bad_layout'):
            print(f'  {r["category"]}: {r["file"]} {r.get("error") or r.get("version") or r.get("nobs")}')
    by_year = collections.defaultdict(collections.Counter)
    for r in records:
        by_year[r['file'][:4]][r['category']] += 1
    for year, year_counts in sorted(by_year.items()):
        print(f'  {year}: {dict(sorted(year_counts.items()))}')


def main():
    if sys.argv[1] == '--summarize':
        summarize(sys.argv[2])
        return
    output = sys.argv[1]
    started = time.time()
    files, empty = walk()
    workers = len(os.sched_getaffinity(0))
    print(f'{len(files)} files, {len(empty)} empty orbit directories, {workers} workers', flush=True)
    with open(output, 'w') as handle, multiprocessing.Pool(workers) as pool:
        for count, record in enumerate(pool.imap_unordered(audit, files, chunksize=4), 1):
            handle.write(json.dumps(record) + '\n')
            if count % 2000 == 0:
                handle.flush()
                print(f'{count} files in {time.time() - started:.0f} s', flush=True)
    with open(output.replace('.jsonl', '_empty.json'), 'w') as handle:
        json.dump(empty, handle)
    print(f'done in {time.time() - started:.0f} s')
    summarize(output, empty)


if __name__ == '__main__':
    main()
