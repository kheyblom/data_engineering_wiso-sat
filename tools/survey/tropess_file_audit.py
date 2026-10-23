"""Audit every AIRS v1 TROPESS day: the Standard and Summary files, read whole.

Written 2026-10-23 before the TROPESS reader (``docs/products/tropess.md``,
production subset P8). A granule is one day: the Standard file and the
Summary file, merged (Product scheme). The files are ~142 GB in all, so it
runs as a batch job over a process pool.

Only the known collection folders are listed; ``*_target.nc`` copies (R5) and
L3 ``AIRS_TROPESS_gridded_*`` files (R6) are skipped. Per day it records, for
each file present:

- ``ShortName``, ``VersionID``, ``Platform``, ``Instrument`` and ``source``
  against the file name's ``R1pNN``, and a layout signature (every dataset's
  name, trailing shape, dtype and units), so format drift shows up;
- ``nobs``, rows whose time, lat or lon is fill or NaN, and lat/lon out of
  range;
- time: TAI93 less the leap seconds, against ``datetime_utc`` on every row
  (R3), whether time is whole seconds, and rows dated off the file's day;
- per dataset on ``target``: how many values are -999, -9999 or NaN;
- the vertical layout (R10): the levels above the lowest valid one hold the
  fixed grid, and ``x``, ``x_h2o``, ``xa`` and ``altitude`` share
  ``pressure``'s fill;

and for Standard:

- R22: row 0's ``x`` equals ``x_test``;
- DOF, the day/night and land flags, and per-level fill of
  ``observation_error_h2o`` (R15);

and for Summary:

- the 850-250 hPa means recomputed from its profiles (Q2b), and where
  ``dd_col_p_error`` is -9999 (R17), by level count and flag;

and where both exist, the merge: every Summary row is one Standard row, in
order; the matched rows are exactly those with DOF >= 1.1; every shared
variable is identical on them (except ``x`` row 0, R22); ``target_id``
agrees; and ``dd_col_p_error`` against (1000 + dD) sqrt(M S M^T).

Run from the repo root:

    .venv/bin/python -I tools/survey/tropess_file_audit.py <output.jsonl> [--limit N]

It writes one JSON line per day and prints a summary; ``--summarize``
re-reads an existing output.
"""

import collections
import hashlib
import json
import multiprocessing
import os
import re
import sys
import time

import h5py
import numpy as np
import pandas as pd

AIRS = '/glade/derecho/scratch/kheyblom/data/wisosat/raw/AIRS'
# per stream: the Standard folders and the Summary folders; a folder ending
# in '.1' holds one subfolder per year
FOLDERS = {
    'RS': (['TRPSDL2HDOAIRSORS.1'], ['TRPSYL2HDOAIRSORS_1-20240806_185241']),
    'FS': (['TRPSDL2HDOAIRSFS_1-20240912_174250', 'TRPSDL2HDOAIRSFS.1'], ['TRPSYL2HDOAIRSFS.1']),
}
FILE_RE = re.compile(r'^TROPESS_AIRS-Aqua_L2_(Standard|Summary)_HDO_(\d{8})_MUSES_(R1p\d+)_(RS|FS)_(F\dp\d+)(_J\d)?\.nc$')
SHORT_NAMES = {('RS', 'Standard'): 'TRPSDL2HDOAIRSORS', ('RS', 'Summary'): 'TRPSYL2HDOAIRSORS',
               ('FS', 'Standard'): 'TRPSDL2HDOAIRSFS', ('FS', 'Summary'): 'TRPSYL2HDOAIRSFS'}
FILLS = (-999, -9999)
SMOW = 3.11e-4  # TROPESS's, from dd_col_p's source attribute
# UTC dates of the leap seconds after the TAI93 epoch (1993-01-01)
LEAP_DATES = ['1993-07-01', '1994-07-01', '1996-01-01', '1997-07-01', '1999-01-01',
              '2006-01-01', '2009-01-01', '2012-07-01', '2015-07-01', '2017-01-01']
EPOCH = pd.Timestamp('1993-01-01')
# each leap second's TAI93 instant: its UTC seconds since the epoch plus the
# leap seconds already inserted, including itself
LEAP_TAI = np.array([(pd.Timestamp(d) - EPOCH).total_seconds() + i + 1 for i, d in enumerate(LEAP_DATES)])
# the shared per-target variables compared between Standard and Summary
SHARED = ('time', 'latitude', 'longitude', 'datetime_utc', 'year_fraction', 'x', 'x_h2o', 'pressure', 'altitude',
          'geolocation/airs_atrack', 'geolocation/airs_xtrack', 'geolocation/airs_granule',
          'geolocation/airs_view_ang', 'geophysical/land_flag', 'geophysical/day_night_flag')
PROFILE_FILL_LIKE_PRESSURE = ('x', 'x_h2o', 'observation_ops/xa', 'altitude')


def text(value):
    if isinstance(value, np.ndarray) and value.size == 1:
        value = value.reshape(-1)[0]
    return value.decode() if isinstance(value, bytes) else str(value)


def masked(values):
    values = values.astype('f8')
    values[np.isin(values, FILLS)] = np.nan
    return values


def listing():
    """Every day of each stream, with its Standard and Summary paths."""
    days = []
    for stream, (standard, summary) in FOLDERS.items():
        found = collections.defaultdict(lambda: collections.defaultdict(list))
        for kind, folders in (('Standard', standard), ('Summary', summary)):
            for folder in folders:
                base = f'{AIRS}/{folder}'
                subdirs = sorted(d for d in os.listdir(base) if d.isdigit()) if folder.endswith('.1') else ['']
                for sub in subdirs:
                    where = f'{base}/{sub}'.rstrip('/')
                    for name in os.listdir(where):
                        match = FILE_RE.match(name)
                        if match and match.group(1) == kind:
                            found[match.group(2)][kind].append(f'{where}/{name}')
        for day in sorted(found):
            days.append({'stream': stream, 'day': day, **{k: sorted(v) for k, v in found[day].items()}})
    return days


def utc_seconds(datetime_utc):
    """``datetime_utc`` rows (year .. second) as UTC seconds since 1993-01-01."""
    frame = pd.DataFrame(datetime_utc, columns=['year', 'month', 'day', 'hour', 'minute', 'second'])
    return (pd.to_datetime(frame) - EPOCH).dt.total_seconds().to_numpy()


def header(handle, path, stream, kind):
    """Global attributes and layout of one file, checked against its name."""
    match = FILE_RE.match(os.path.basename(path))
    out = {'file': path[len(AIRS) + 1:], 'size': os.stat(path).st_size,
           'algorithm': match.group(3), 'format': match.group(5) + (match.group(6) or '')}
    attrs = {k: text(handle.attrs[k]) for k in ('ShortName', 'VersionID', 'Platform', 'Instrument', 'source')
             if k in handle.attrs}
    out['attr_problems'] = [
        problem for problem, bad in (
            ('ShortName', attrs.get('ShortName') != SHORT_NAMES[(stream, kind)]),
            ('VersionID', attrs.get('VersionID') != '1'),
            ('Platform', attrs.get('Platform') != 'Aqua'),
            ('Instrument', attrs.get('Instrument') != 'AIRS'),
            ('source', attrs.get('source') != f'MUSES v1.{match.group(3)[3:]}'),
        ) if bad]
    layout = []
    handle.visititems(lambda name, item: layout.append(
        f'{name}|{item.shape[1:]}|{item.dtype}|{text(item.attrs.get("units", ""))}')
        if isinstance(item, h5py.Dataset) else None)
    out['layout'] = hashlib.sha1('\n'.join(sorted(layout)).encode()).hexdigest()[:12]
    return out


def per_target(handle, nobs):
    """Every dataset on the target dimension, read whole."""
    data = {}
    handle.visititems(lambda name, item: data.__setitem__(name, item[()])
                      if isinstance(item, h5py.Dataset) and item.ndim and item.shape[0] == nobs
                      and item.dtype.kind in 'fiu' else None)
    return data


def common_checks(data, day):
    """Checks every file gets: rows, time, ranges, fill, vertical layout."""
    out = {}
    t, lat, lon = data['time'], data['latitude'], data['longitude']
    bad = np.isin(t, FILLS) | np.isnan(t) | np.isin(lat, FILLS) | np.isnan(lat) | np.isin(lon, FILLS) | np.isnan(lon)
    out['rows_not_observed'] = int(bad.sum())
    ok = ~bad
    out['lat_out'] = int((np.abs(lat[ok]) > 90).sum())
    out['lon_out'] = int((np.abs(lon[ok]) > 180).sum())
    out['time_not_whole_seconds'] = int((t[ok] != np.round(t[ok])).sum())
    leaps = np.searchsorted(LEAP_TAI, t, side='right')
    utc = t - leaps
    reference = utc_seconds(data['datetime_utc'])
    out['time_vs_datetime_utc_mismatch'] = int((np.abs(utc - reference)[ok] > 0).sum())
    out['leap_seconds'] = sorted(set(int(v) for v in leaps[ok]))
    stamps = EPOCH + pd.to_timedelta(utc[ok], unit='s')
    out['rows_off_day'] = int((stamps.strftime('%Y%m%d') != day).sum())
    out['first'], out['last'] = str(stamps.min()), str(stamps.max())
    fills = {}
    for name, values in data.items():
        if values.dtype.kind == 'f':
            entry = {'-999': int((values == -999).sum()), '-9999': int((values == -9999).sum()),
                     'nan': int(np.isnan(values).sum())}
        else:
            entry = {'-999': int((values == -999).sum()), '-9999': int((values == -9999).sum())}
        entry = {k: v for k, v in entry.items() if v}
        if entry:
            fills[name] = entry
    out['fills'] = fills
    p = masked(data['pressure'])
    valid = ~np.isnan(p)
    lowest = np.argmax(valid, axis=1)
    above = valid & (np.arange(p.shape[1])[None, :] > lowest[:, None])
    grid = np.nanmedian(np.where(above, p, np.nan), axis=0)
    out['grid'] = [round(float(v), 2) for v in grid]
    out['grid_mismatch_rows'] = int((above & ~np.isclose(p, grid[None, :], rtol=1e-5)).any(axis=1).sum())
    out['holes_above_lowest'] = int((~valid & (np.arange(p.shape[1])[None, :] > lowest[:, None])).any(axis=1).sum())
    out['fill_unlike_pressure'] = {
        name: int((np.isnan(masked(data[name])) != ~valid).any(axis=1).sum())
        for name in PROFILE_FILL_LIKE_PRESSURE if name in data}
    out['x_h2o_max'] = float(np.nanmax(masked(data['x_h2o'])))
    return out


def standard_checks(handle, data):
    out = {}
    x0, xt = handle['x'][0], handle['observation_ops/x_test'][()]
    out['r22_x0_is_x_test'] = bool(np.array_equal(x0, xt))
    dof = masked(data['observation_ops/signal_dof'])
    out['dof_min'] = float(np.nanmin(dof))
    out['dof_ge_1p1'] = int((dof >= 1.1).sum())
    for name in ('geophysical/day_night_flag', 'geophysical/land_flag'):
        values, counts = np.unique(data[name], return_counts=True)
        out[name.split('/')[1]] = {str(int(v)): int(c) for v, c in zip(values, counts)}
    out['obs_error_h2o_fill_by_level'] = np.isnan(masked(data['observation_ops/observation_error_h2o'])).sum(0).tolist()
    out['x_fill_by_level'] = np.isnan(masked(data['x'])).sum(0).tolist()
    kernel = data['observation_ops/averaging_kernel']
    out['kernel_rows_with_fill'] = int(np.isin(kernel, FILLS).any(axis=(1, 2)).sum())
    return out


def summary_checks(data):
    out = {}
    x, h, p = masked(data['x']), masked(data['x_h2o']), masked(data['pressure'])
    sel = (p >= 250) & (p <= 850)
    nlev = sel.sum(1)
    out['levels_850_250'] = {str(k): int(v) for k, v in zip(*np.unique(nlev, return_counts=True))}
    with np.errstate(invalid='ignore', divide='ignore'):
        dd = 1000 * (np.nanmean(np.where(sel, x, np.nan), 1) / SMOW - 1)
        xc = np.nanmean(np.where(sel, h, np.nan), 1) * 1e6
    stored_dd, stored_xc = masked(data['dd_col_p']), masked(data['x_h2o_col_p'])
    both = ~np.isnan(stored_dd) & ~np.isnan(dd)
    out['dd_col_p_max_diff'] = float(np.max(np.abs(dd - stored_dd)[both])) if both.any() else None
    both = ~np.isnan(stored_xc) & ~np.isnan(xc)
    out['x_h2o_col_p_max_rel'] = float(np.max(np.abs(xc / stored_xc - 1)[both])) if both.any() else None
    error_fill = data['dd_col_p_error'] == -9999
    out['dd_col_p_error_fill'] = int(error_fill.sum())
    out['dd_col_p_error_fill_by_levels'] = {str(k): int((error_fill & (nlev == k)).sum()) for k in np.unique(nlev)}
    for name in ('geophysical/day_night_flag', 'geophysical/land_flag'):
        if name in data:
            out[f'dd_col_p_error_fill_by_{name.split("/")[1]}'] = {
                str(int(v)): int((error_fill & (data[name] == v)).sum()) for v in np.unique(data[name])}
    return out


def merge_checks(standard, summary, std_handle):
    """Summary against Standard: same rows (DOF >= 1.1), in order, same values."""
    out = {}
    key = lambda d: np.stack([d['time'], d['latitude'].astype('f8'), d['longitude'].astype('f8')], axis=1)
    ks, ky = key(standard), key(summary)
    view = lambda a: np.ascontiguousarray(a).view([('', a.dtype)] * a.shape[1]).ravel()
    vs, vy = view(ks), view(ky)
    order = np.argsort(vs, kind='stable')
    pos = np.searchsorted(vs[order], vy)
    pos = np.clip(pos, 0, len(order) - 1)
    found = vs[order][pos] == vy
    index = np.where(found, order[pos], -1)
    out['summary_rows_unmatched'] = int((~found).sum())
    out['standard_keys_duplicated'] = int(len(vs) - len(np.unique(vs)))
    matched = index[found]
    out['order_kept'] = bool(np.all(np.diff(matched) > 0))
    dof = masked(standard['observation_ops/signal_dof'])
    member = np.zeros(len(dof), bool)
    member[matched] = True
    out['rule_mismatch'] = int((member != (dof >= 1.1)).sum())
    differs = []
    for name in SHARED:
        if name in standard and name in summary:
            a, b = standard[name][matched], summary[name][found]
            if name == 'x' and len(matched) and matched[0] == 0:
                a, b = a[1:], b[1:]
            if not np.array_equal(a.astype('f8'), b.astype('f8'), equal_nan=True):
                differs.append(name)
    out['shared_differ'] = differs
    if 'target_id' in standard and 'target_id' in summary:
        out['target_id_differ'] = int((standard['target_id'][matched] != summary['target_id'][found]).sum())
    # dd_col_p_error = (1000 + dD) sqrt(M S M^T), M the equal-weight mean over 850-250 hPa
    p = masked(standard['pressure'])[matched]
    sel = (p >= 250) & (p <= 850)
    weights = sel / np.maximum(sel.sum(1, keepdims=True), 1)
    cov = masked(std_handle['observation_ops/observation_error'][()])[matched]
    variance = np.einsum('ni,nij,nj->n', weights, np.nan_to_num(cov), weights)
    stored = summary['dd_col_p_error'][found].astype('f8')
    written = ~np.isin(stored, FILLS)
    dd = masked(summary['dd_col_p'][found])
    with np.errstate(invalid='ignore'):
        rebuilt = (1000 + dd) * np.sqrt(variance)
    good = written & (variance > 0) & ~np.isnan(dd)
    out['dd_col_p_error_max_rel'] = float(np.max(np.abs(rebuilt[good] / stored[good] - 1))) if good.any() else None
    out['dd_col_p_error_fill_negative_variance'] = int((~written & (variance < 0)).sum())
    out['dd_col_p_error_fill_nonnegative_variance'] = int((~written & (variance >= 0)).sum())
    return out


def audit(entry):
    """One day: both files read whole; never raises."""
    record = {'stream': entry['stream'], 'day': entry['day'],
              'n_standard': len(entry.get('Standard', [])), 'n_summary': len(entry.get('Summary', []))}
    loaded = {}
    try:
        for kind in ('Standard', 'Summary'):
            if not entry.get(kind):
                continue
            path = entry[kind][0]
            handle = h5py.File(path, 'r')
            nobs = int(handle['time'].shape[0])
            info = header(handle, path, entry['stream'], kind)
            info['nobs'] = nobs
            data = per_target(handle, nobs)
            info.update(common_checks(data, entry['day']))
            info.update(standard_checks(handle, data) if kind == 'Standard' else summary_checks(data))
            record[kind] = info
            loaded[kind] = (handle, data)
        if len(loaded) == 2:
            record['merge'] = merge_checks(loaded['Standard'][1], loaded['Summary'][1], loaded['Standard'][0])
    except Exception as error:
        record['error'] = f'{type(error).__name__}: {str(error)[:200]}'
    finally:
        for handle, _ in loaded.values():
            handle.close()
    return record


def summarize(path):
    records = [json.loads(line) for line in open(path)]
    for stream in ('RS', 'FS'):
        rs = [r for r in records if r['stream'] == stream]
        if not rs:
            continue
        print(f'=== {stream}: {len(rs)} days; errors {sum("error" in r for r in rs)}; '
              f'two files of one type {[r["day"] for r in rs if r["n_standard"] > 1 or r["n_summary"] > 1]}')
        for r in rs:
            if 'error' in r:
                print(f'  ERROR {r["day"]}: {r["error"]}')
        for kind in ('Standard', 'Summary'):
            ks = [r[kind] for r in rs if kind in r]
            print(f'  {kind}: {len(ks)} files, {sum(k["nobs"] for k in ks):,} obs')
            if not ks:
                continue
            print(f'    layouts {len(set(k["layout"] for k in ks))}; attr problems '
                  f'{collections.Counter(p for k in ks for p in k["attr_problems"])}')
            for field in ('rows_not_observed', 'lat_out', 'lon_out', 'time_not_whole_seconds',
                          'time_vs_datetime_utc_mismatch', 'rows_off_day', 'grid_mismatch_rows', 'holes_above_lowest'):
                hits = [(k['file'][-50:], k[field]) for k in ks if k.get(field)]
                print(f'    {field}: {len(hits)} files, {sum(h[1] for h in hits):,} rows {hits[:3]}')
            unlike = collections.Counter()
            for k in ks:
                unlike.update(k['fill_unlike_pressure'])
            print(f'    profile fill unlike pressure (rows): {dict(unlike)}')
            print(f'    leap seconds seen: {sorted(set(v for k in ks for v in k["leap_seconds"]))}; '
                  f'grids: {collections.Counter(tuple(k["grid"][1:]) for k in ks).most_common(3)}')
            print(f'    x_h2o max over record {max(k["x_h2o_max"] for k in ks):.3f}')
            fills = collections.defaultdict(collections.Counter)
            for k in ks:
                for name, entry in k['fills'].items():
                    fills[name].update(entry)
            print('    fill by dataset (values):', {n: dict(c) for n, c in sorted(fills.items())})
            if kind == 'Standard':
                print(f'    R22 x[0] == x_test: {sum(k["r22_x0_is_x_test"] for k in ks)}/{len(ks)}; '
                      f'DOF min {min(k["dof_min"] for k in ks):.4f}; DOF >= 1.1 {sum(k["dof_ge_1p1"] for k in ks):,}; '
                      f'kernel rows with fill {sum(k["kernel_rows_with_fill"] for k in ks)}')
                dn, land = collections.Counter(), collections.Counter()
                for k in ks:
                    dn.update(k['day_night_flag']); land.update(k['land_flag'])
                print(f'    day_night_flag {dict(dn)}; land_flag {dict(land)}')
                by_alg = collections.defaultdict(lambda: np.zeros(17))
                for k in ks:
                    by_alg[k['algorithm'] + ' ' + k['format']] += np.array(k['obs_error_h2o_fill_by_level']) / k['nobs']
                counts = collections.Counter(k['algorithm'] + ' ' + k['format'] for k in ks)
                for alg, total in by_alg.items():
                    print(f'    obs_error_h2o fill % by level, {alg}: {np.round(100 * total / counts[alg], 1).tolist()}')
            else:
                print(f'    dd_col_p max diff {max((k["dd_col_p_max_diff"] or 0) for k in ks):.4f}; '
                      f'x_h2o_col_p max rel {max((k["x_h2o_col_p_max_rel"] or 0) for k in ks):.2e}')
                lev, fill_lev = collections.Counter(), collections.Counter()
                for k in ks:
                    lev.update(k['levels_850_250']); fill_lev.update(k['dd_col_p_error_fill_by_levels'])
                print(f'    levels in 850-250: {dict(lev)}; dd_col_p_error fill {sum(k["dd_col_p_error_fill"] for k in ks):,}, '
                      f'by levels {dict(fill_lev)}')
                for flag in ('day_night_flag', 'land_flag'):
                    c = collections.Counter()
                    for k in ks:
                        c.update(k.get(f'dd_col_p_error_fill_by_{flag}', {}))
                    print(f'    dd_col_p_error fill by {flag}: {dict(c)}')
        ms = [r['merge'] for r in rs if 'merge' in r] or [{
            'summary_rows_unmatched': 0, 'standard_keys_duplicated': 0, 'order_kept': True, 'rule_mismatch': 0,
            'shared_differ': [], 'dd_col_p_error_max_rel': None, 'dd_col_p_error_fill_negative_variance': 0,
            'dd_col_p_error_fill_nonnegative_variance': 0}]
        print(f'  merge: {len(ms)} days; unmatched Summary rows {sum(m["summary_rows_unmatched"] for m in ms)}; '
              f'duplicate Standard keys {sum(m["standard_keys_duplicated"] for m in ms)}; '
              f'order broken {sum(not m["order_kept"] for m in ms)}; DOF rule mismatches {sum(m["rule_mismatch"] for m in ms)}')
        print(f'    shared variables differing: {collections.Counter(n for m in ms for n in m["shared_differ"])}; '
              f'target_id differing {sum(m.get("target_id_differ", 0) for m in ms)}')
        print(f'    dd_col_p_error rebuilt max rel {max((m["dd_col_p_error_max_rel"] or 0) for m in ms):.2e}; fill with '
              f'negative variance {sum(m["dd_col_p_error_fill_negative_variance"] for m in ms)}, '
              f'non-negative {sum(m["dd_col_p_error_fill_nonnegative_variance"] for m in ms)}')
        print(f'  Standard-only days {[r["day"] for r in rs if r["n_summary"] == 0]}; '
              f'Summary-only days {[r["day"] for r in rs if r["n_standard"] == 0]}')


def main():
    if sys.argv[1] == '--summarize':
        summarize(sys.argv[2])
        return
    output = sys.argv[1]
    started = time.time()
    days = listing()
    if '--limit' in sys.argv:
        # an even spread over each stream, for a timing probe
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
        days = [d for stream in FOLDERS for d in (lambda s: s[::max(1, len(s) // limit)][:limit])(
            [d for d in days if d['stream'] == stream])]
    workers = len(os.sched_getaffinity(0))
    print(f'{len(days)} days, {workers} workers', flush=True)
    with open(output, 'w') as handle, multiprocessing.Pool(workers) as pool:
        for count, record in enumerate(pool.imap_unordered(audit, days, chunksize=4), 1):
            handle.write(json.dumps(record) + '\n')
            if count % 500 == 0:
                handle.flush()
                print(f'{count} days in {time.time() - started:.0f} s', flush=True)
    print(f'done in {time.time() - started:.0f} s')
    summarize(output)


if __name__ == '__main__':
    main()
