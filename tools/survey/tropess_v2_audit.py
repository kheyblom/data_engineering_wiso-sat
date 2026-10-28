"""Audit every TROPESS v2 Full day (AIRS and CrIS-JPSS1), before the v2 reader.

Written 2026-10-28 after decision 5 (``docs/products/tropess.md``, "v2:
answers (user, 2026-10-28) and first probes"): v2 is built from the Full
files only, one product per platform, on 17 levels (R42), with ``altitude``
read from Full at the retrieval pressures (R43). One-day probes and a scan of
every 10th day (TESTING.md finding 17) found the layout; this checks every
Full file, read whole except the int8-packed blocks and the
``characterization`` group, which no store uses. A task is one day of one
product. Per file it records:

- ``ShortName``, ``VersionID`` (2), ``Platform``, ``Instrument`` and
  ``source`` against the file name's ``R1pNN``; ``ProductionDateTime``; a
  layout signature; every dataset's ``standard_name``, ``long_name``,
  ``units`` and ``_FillValue`` (R33 and R38 were attribute changes);
- rows, rows whose time, lat or lon is fill or NaN, lat/lon out of range,
  ``target_id`` uniqueness;
- time: whole seconds, TAI93 less the leap seconds against ``datetime_utc``
  on every row (R3), rows dated off the file's day, and the order (steps
  back, their size; R32 for AIRS, R40 for CrIS);
- per stored source: values that are -999, -9999 or NaN;
- R42: no value outside levels 0-16 in any stored retrieval-grid array
  (both axes of the kernels); ``pressure_ret`` and ``air_density`` 17-33
  equal to 0-16; ``air_density`` 34-66 all fill;
- the vertical layout (R10): the fixed grid above the lowest valid level,
  holes, and profiles whose fill differs from ``pressure_ret``'s;
  ``observation_error_h2o`` written below the surface (R15);
- R43's fix: every written ``pressure_ret`` level found exactly in the row's
  ``pressure_fm``, and ``altitude`` written there;
- R22: row 0's ``x`` against ``x_test`` (in v2 it should not be it);
- ``quality`` values, ``dofs`` equal to ``signal_dof``, DOF by quality;
- ``h2o_h2o_averaging_kernel`` equal to ``averaging_kernel_h2o``;
- the flags (R36: a file whose ``land_flag`` is 1 on every row);
- the 850-250 hPa means recomputed from the profiles (``250 <= p < 850``,
  R30), and ``dd_col_p_error`` -9999 counts (R17);

and across files, reading only time, lat and lon of the neighbours (plus
the repeated rows):

- R37: rows sharing time, lat and lon with the file one and two days
  before, and which stored sources differ on them;
- the v1/v2 seam: the first two v2 days against the last two v1 Standard
  days.

Run from the repo root, as a batch job (it reads every v2 Full file, ~105 GB):

    .venv/bin/python -I tools/survey/tropess_v2_audit.py <output.jsonl> [--workers N] [--limit N]

It writes one JSON line per day and prints a summary; ``--summarize``
re-reads an existing output.
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
import pandas as pd

RAW = '/glade/derecho/scratch/kheyblom/data/wisosat/raw'
PRODUCTS = {
    'airs': {'folder': 'AIRS/TRPSFL2HDOAIRSFS.2', 'token': 'AIRS-Aqua', 'platform': 'Aqua', 'instrument': 'AIRS',
             'short_name': 'TRPSFL2HDOAIRSFS', 'v1_standard': 'AIRS/TRPSDL2HDOAIRSFS.1'},
    'cris_jpss1': {'folder': 'CRIS/TRPSFL2HDOCRS1FS.2', 'token': 'CrIS-JPSS1', 'platform': 'JPSS-1',
                   'instrument': 'CrIS', 'short_name': 'TRPSFL2HDOCRS1FS', 'v1_standard': 'CRIS/TRPSDL2HDOCRS1FS.1'},
}
FILE_RE = re.compile(r'^TROPESS_(?P<token>AIRS-Aqua|CrIS-JPSS1)_L2_(?P<kind>Full|Standard)_HDO_'
                     r'(?P<day>\d{8})_MUSES_(?P<algorithm>R1p\d+)_FS_(?P<format>F\dp\d+)(?P<joint>_J\d)?\.nc$')
VARIABLE_ATTRS = ('standard_name', 'long_name', 'units', '_FillValue')
FILLS = (-999, -9999)
SMOW = 3.11e-4  # TROPESS's, from dd_col_p's source attribute (v1)
LEVELS = 17
# UTC dates of the leap seconds after the TAI93 epoch (1993-01-01)
LEAP_DATES = ['1993-07-01', '1994-07-01', '1996-01-01', '1997-07-01', '1999-01-01',
              '2006-01-01', '2009-01-01', '2012-07-01', '2015-07-01', '2017-01-01']
EPOCH = pd.Timestamp('1993-01-01')
LEAP_TAI = np.array([(pd.Timestamp(d) - EPOCH).total_seconds() + i + 1 for i, d in enumerate(LEAP_DATES)])
# the stored sources (decision 5): per target, on the retrieval grid, and kernels
SCALARS = ('time', 'latitude', 'longitude', 'dd_col_p', 'dd_col_p_error', 'x_h2o_col_p', 'x_h2o_col_p_error',
           'dd_004', 'quality', 'dofs', 'observation_ops/signal_dof', 'geophysical/average_cloud_eod',
           'geophysical/cloud_top_pressure', 'geophysical/surface_temperature', 'geophysical/land_flag',
           'geophysical/day_night_flag')
PROFILES = ('x', 'x_h2o', 'observation_ops/xa', 'observation_ops/observation_error_h2o')
COPIES = ('pressure_ret', 'retrieval/air_density')
KERNELS = ('observation_ops/averaging_kernel', 'observation_ops/averaging_kernel_h2o', 'hdo_hdo_averaging_kernel',
           'hdo_h2o_averaging_kernel', 'h2o_hdo_averaging_kernel', 'h2o_h2o_averaging_kernel')
FORWARD = ('pressure_fm', 'altitude')
FILL_LIKE_PRESSURE = ('x', 'x_h2o', 'observation_ops/xa')


def text(value):
    if isinstance(value, np.ndarray) and value.size == 1:
        value = value.reshape(-1)[0]
    return value.decode() if isinstance(value, bytes) else str(value)


def unwritten(values):
    """True where a value is -999, -9999 or NaN."""
    out = np.isin(values, FILLS)
    return out | np.isnan(values) if values.dtype.kind == 'f' else out


def masked(values):
    values = values.astype('f8')
    values[np.isin(values, FILLS)] = np.nan
    return values


def utc_seconds(datetime_utc):
    frame = pd.DataFrame(datetime_utc, columns=['year', 'month', 'day', 'hour', 'minute', 'second'])
    return (pd.to_datetime(frame) - EPOCH).dt.total_seconds().to_numpy()


def files_of(folder, kind, token):
    """{day: path} of one collection folder (one subfolder per year)."""
    out = {}
    base = f'{RAW}/{folder}'
    for sub in sorted(d for d in os.listdir(base) if d.isdigit()):
        for name in os.listdir(f'{base}/{sub}'):
            match = FILE_RE.match(name)
            if match and match['kind'] == kind and match['token'] == token:
                if match['day'] in out:
                    raise SystemExit(f'two {kind} files for {token} {match["day"]}')
                out[match['day']] = f'{base}/{sub}/{name}'
    return out


def listing(products):
    """Every day of each product, with its Full file and its neighbours' (one and two days before)."""
    days = []
    for product in products:
        spec = PRODUCTS[product]
        found = files_of(spec['folder'], 'Full', spec['token'])
        v1 = files_of(spec['v1_standard'], 'Standard', spec['token'])
        ordered = sorted(found)
        for i, day in enumerate(ordered):
            entry = {'product': product, 'day': day, 'path': found[day], 'before': {}}
            for lag in (1, 2):
                prior = (datetime.date.fromisoformat(f'{day[:4]}-{day[4:6]}-{day[6:]}')
                         - datetime.timedelta(days=lag)).strftime('%Y%m%d')
                if prior in found:
                    entry['before'][prior] = found[prior]
                elif i < 2 and prior in v1:
                    entry['before'][prior] = v1[prior]  # the v1/v2 seam
            days.append(entry)
    return days


def header(handle, path, spec):
    match = FILE_RE.match(os.path.basename(path))
    out = {'file': path[len(RAW) + 1:], 'size': os.stat(path).st_size, 'algorithm': match['algorithm'],
           'format': match['format'] + (match['joint'] or '')}
    attrs = {k: text(handle.attrs[k]) for k in ('ShortName', 'VersionID', 'Platform', 'Instrument', 'source',
                                                'ProductionDateTime') if k in handle.attrs}
    out['production'] = attrs.get('ProductionDateTime')
    out['attr_problems'] = [
        problem for problem, bad in (
            ('ShortName', attrs.get('ShortName') != spec['short_name']),
            ('VersionID', attrs.get('VersionID') != '2'),
            ('Platform', attrs.get('Platform') != spec['platform']),
            ('Instrument', attrs.get('Instrument') != spec['instrument']),
            ('source', attrs.get('source') != f'MUSES v1.{match["algorithm"][3:]}'),
        ) if bad]
    layout, variable_attrs = [], {}

    def visit(name, item):
        if isinstance(item, h5py.Dataset):
            layout.append(f'{name}|{item.shape[1:]}|{item.dtype}|{text(item.attrs.get("units", ""))}')
            variable_attrs[name] = '|'.join(text(item.attrs[k]) if k in item.attrs else '-' for k in VARIABLE_ATTRS)

    handle.visititems(visit)
    out['layout'] = hashlib.sha1('\n'.join(sorted(layout)).encode()).hexdigest()[:12]
    out['variable_attrs'] = variable_attrs
    return out


def fill_counts(values):
    entry = {'-999': int((values == -999).sum()), '-9999': int((values == -9999).sum())}
    if values.dtype.kind == 'f':
        entry['nan'] = int(np.isnan(values).sum())
    return {k: v for k, v in entry.items() if v}


def keys(handle):
    t = handle['time'][()]
    return np.stack([t, handle['latitude'][()].astype('f8'), handle['longitude'][()].astype('f8')], axis=1)


def key_view(a):
    return np.ascontiguousarray(a).view([('', a.dtype)] * a.shape[1]).ravel()


def file_checks(handle, day, instrument):
    """Every per-file check; returns the record and the stored sources read."""
    out, data = {}, {}
    n = int(handle['time'].shape[0])
    out['nobs'] = n
    for name in SCALARS + PROFILES + COPIES + FORWARD + ('datetime_utc',):
        data[name] = handle[name][()]
    geolocation = [f'geolocation/{instrument.lower()}_{s}' for s in ('granule', 'atrack', 'xtrack', 'fov')]
    for name in geolocation:
        if name in handle:
            data[name] = handle[name][()]
    tid = handle['target_id'][()]
    out['target_id_unique'] = int(len(np.unique(tid, axis=0)))

    t, lat, lon = data['time'], data['latitude'], data['longitude']
    bad = unwritten(t) | unwritten(lat) | unwritten(lon)
    out['rows_not_observed'] = int(bad.sum())
    ok = ~bad
    out['lat_out'] = int((np.abs(lat[ok]) > 90).sum())
    out['lon_out'] = int((np.abs(lon[ok]) > 180).sum())
    out['time_not_whole_seconds'] = int((t[ok] != np.round(t[ok])).sum())
    leaps = np.searchsorted(LEAP_TAI, t, side='right')
    utc = t - leaps
    out['time_vs_datetime_utc_mismatch'] = int((np.abs(utc - utc_seconds(data['datetime_utc']))[ok] > 0).sum())
    out['leap_seconds'] = sorted(set(int(v) for v in leaps[ok]))
    stamps = EPOCH + pd.to_timedelta(utc[ok], unit='s')
    dates = stamps.strftime('%Y%m%d')
    out['rows_before_day'] = int((dates < day).sum())
    out['rows_after_day'] = int((dates > day).sum())
    out['first'], out['last'] = str(stamps.min()), str(stamps.max())
    steps = np.diff(t[ok])
    out['steps_back'] = int((steps < 0).sum())
    out['steps_back_over_120s'] = int((steps < -120).sum())
    out['largest_step_back_s'] = float(-steps.min()) if (steps < 0).any() else 0.0
    keyset = key_view(keys(handle))
    out['duplicate_keys'] = int(len(keyset) - len(np.unique(keyset)))

    out['fills'] = {name: c for name in SCALARS + PROFILES + COPIES if (c := fill_counts(data[name]))}

    # R42: nothing outside levels 0-16 in the stored retrieval-grid arrays
    beyond = {}
    for name in PROFILES:
        beyond[name] = int((~unwritten(data[name][:, LEVELS:])).sum())
    for name in COPIES:
        low, high = data[name][:, :LEVELS], data[name][:, LEVELS:2 * LEVELS]
        same = (unwritten(low) == unwritten(high)) & (unwritten(low) | (low == high))
        beyond[f'{name} 17-33 differs from 0-16 (rows)'] = int((~same.all(axis=1)).sum())
    beyond['retrieval/air_density 34-66 written'] = int((~unwritten(data['retrieval/air_density'][:, 2 * LEVELS:])).sum())
    kernel_rows_fill = {}
    for name in KERNELS:
        kernel = handle[name][()]
        w = ~unwritten(kernel)
        beyond[name] = int(w[:, LEVELS:, :].sum() + w[:, :LEVELS, LEVELS:].sum())
        data[name] = kernel[:, :LEVELS, :LEVELS]
    out['written_beyond_level_16'] = beyond
    same_kernel = (data['h2o_h2o_averaging_kernel'] == data['observation_ops/averaging_kernel_h2o']) | (
        unwritten(data['h2o_h2o_averaging_kernel']) & unwritten(data['observation_ops/averaging_kernel_h2o']))
    out['h2o_h2o_vs_averaging_kernel_h2o_rows_differ'] = int((~same_kernel.all(axis=(1, 2))).sum())

    # the vertical layout (R10, R15)
    p = masked(data['pressure_ret'][:, :LEVELS])
    valid = ~np.isnan(p)
    lowest = np.argmax(valid, axis=1)
    above = valid & (np.arange(LEVELS)[None, :] > lowest[:, None])
    grid = np.nanmedian(np.where(above, p, np.nan), axis=0)
    out['grid'] = [round(float(v), 2) for v in grid]
    out['grid_mismatch_rows'] = int((above & ~np.isclose(p, grid[None, :], rtol=1e-5)).any(axis=1).sum())
    out['holes_above_lowest'] = int((~valid & (np.arange(LEVELS)[None, :] > lowest[:, None])).any(axis=1).sum())
    out['rows_without_pressure'] = int((~valid.any(axis=1)).sum())
    out['fill_unlike_pressure'] = {name: int((unwritten(data[name][:, :LEVELS]) != ~valid).any(axis=1).sum())
                                   for name in FILL_LIKE_PRESSURE}
    out['air_density_fill_unlike_pressure'] = int(
        (unwritten(data['retrieval/air_density'][:, :LEVELS]) != ~valid).any(axis=1).sum())
    obs_err = data['observation_ops/observation_error_h2o'][:, :LEVELS]
    out['obs_error_h2o_written_below_surface'] = int((~unwritten(obs_err) & ~valid).sum())
    out['obs_error_h2o_fill_above_surface'] = int((unwritten(obs_err) & valid).sum())
    kernel_valid = ~unwritten(data['observation_ops/averaging_kernel'])
    out['kernel_fill_unlike_pressure_rows'] = int(
        (kernel_valid != (valid[:, :, None] & valid[:, None, :])).any(axis=(1, 2)).sum())
    out['x_h2o_max'] = float(np.nanmax(masked(data['x_h2o'][:, :LEVELS])))

    # R43's fix: altitude read from the forward-model grid at the retrieval pressures
    pf = data['pressure_fm']
    hit = (data['pressure_ret'][:, :LEVELS, None] == pf[:, None, :]) & valid[:, :, None]
    out['retrieval_pressure_not_in_fm'] = int((valid & ~hit.any(axis=2)).sum())
    out['retrieval_pressure_in_fm_twice'] = int((hit.sum(axis=2) > 1).sum())
    index = np.argmax(hit, axis=2)
    altitude = np.take_along_axis(data['altitude'], index, axis=1)
    out['altitude_fill_at_retrieval_pressure'] = int((valid & unwritten(altitude)).sum())
    out['altitude_at_lowest_level'] = {str(k): int(v) for k, v in zip(*np.unique(
        np.round(altitude[np.arange(n), lowest][valid.any(axis=1)]).astype(int) == 0, return_counts=True))}

    # R22
    x0, xt = data['x'][0, :LEVELS], handle['observation_ops/x_test'][()][:LEVELS]
    out['r22_x0_is_x_test'] = bool(np.array_equal(x0, xt))
    out['r22_x0_is_x_test_compacted'] = bool(np.array_equal(x0[~unwritten(x0)], xt[~unwritten(xt)]))

    # quality and DOF
    q, dof = data['quality'], masked(data['observation_ops/signal_dof'])
    out['quality'] = {str(int(v)): int(c) for v, c in zip(*np.unique(q, return_counts=True))}
    out['dofs_differs_from_signal_dof'] = int((~((data['dofs'] == data['observation_ops/signal_dof'])
                                                 | (unwritten(data['dofs']) & unwritten(data['observation_ops/signal_dof'])))).sum())
    out['dof_by_quality'] = {str(int(v)): [float(np.nanmin(dof[q == v])), float(np.nanmax(dof[q == v]))]
                             for v in np.unique(q) if (q == v).any() and not np.isnan(dof[q == v]).all()}
    out['quality1_dof_below_1p1'] = int(((q == 1) & (dof < np.float32(1.1))).sum())

    for name in ('geophysical/day_night_flag', 'geophysical/land_flag'):
        out[name.split('/')[1]] = {str(int(v)): int(c) for v, c in zip(*np.unique(data[name], return_counts=True))}

    # 850-250 hPa means from the profiles (R30: 250 <= p < 850)
    x, h = masked(data['x'][:, :LEVELS]), masked(data['x_h2o'][:, :LEVELS])
    sel = (p >= 250) & (p < 850)
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
    out['dd_col_p_error_fill'] = fill_counts(data['dd_col_p_error'])
    return out, data


def repeats(handle, data, before):
    """R37 and the seam: rows sharing time, lat and lon with each earlier file, and what differs on them."""
    out = {}
    mine = key_view(keys(handle))
    for day, path in sorted(before.items()):
        with h5py.File(path, 'r') as other:
            theirs = key_view(keys(other))
            common, i_mine, i_theirs = np.intersect1d(mine, theirs, return_indices=True)
            entry = {'file': path[len(RAW) + 1:], 'shared': int(len(common)),
                     'production': text(other.attrs.get('ProductionDateTime', ''))}
            if len(common) and 'Full' in os.path.basename(path):
                # h5py reads rows in increasing order
                order = np.argsort(i_theirs)
                rows_mine, rows_theirs = i_mine[order], i_theirs[order]
                differs, identical = collections.Counter(), np.ones(len(common), bool)
                for name in SCALARS + PROFILES + KERNELS + ('altitude', 'pressure_ret', 'retrieval/air_density'):
                    a = data[name][rows_mine]
                    b = other[name][rows_theirs]
                    if b.ndim == 3:
                        b = b[:, :LEVELS, :LEVELS]
                    eq = (a == b) | (unwritten(a) & unwritten(b))
                    row_eq = eq.reshape(len(common), -1).all(axis=1)
                    identical &= row_eq
                    if not row_eq.all():
                        differs[name] = int((~row_eq).sum())
                entry['differs'] = dict(differs)
                entry['identical_rows'] = int(identical.sum())
            out[day] = entry
    return out


def audit(entry):
    """One day of one product; never raises."""
    spec = PRODUCTS[entry['product']]
    record = {'product': entry['product'], 'day': entry['day']}
    try:
        with h5py.File(entry['path'], 'r') as handle:
            record['header'] = header(handle, entry['path'], spec)
            checks, data = file_checks(handle, entry['day'], spec['instrument'])
            record.update(checks)
            record['repeats'] = repeats(handle, data, entry['before'])
    except Exception as error:
        record['error'] = f'{type(error).__name__}: {str(error)[:300]}'
    return record


def attribute_changes(records):
    seen = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in records:
        if 'header' in r:
            for name, value in r['header']['variable_attrs'].items():
                seen[name][value].append(r['day'])
    return {name: {value: (min(d), max(d), len(d)) for value, d in values.items()}
            for name, values in sorted(seen.items()) if len(values) > 1}


def summarize(path):
    records = [json.loads(line) for line in open(path)]
    for product in dict.fromkeys(r['product'] for r in records):
        rs = sorted((r for r in records if r['product'] == product), key=lambda r: r['day'])
        ok = [r for r in rs if 'error' not in r]
        total = lambda field: sum(r.get(field, 0) or 0 for r in ok)
        print(f'=== {product}: {len(rs)} days, {rs[0]["day"]} .. {rs[-1]["day"]}; errors {len(rs) - len(ok)}; '
              f'obs {total("nobs"):,}')
        for r in rs:
            if 'error' in r:
                print(f'  ERROR {r["day"]}: {r["error"]}')
        all_days = pd.date_range(rs[0]['day'], rs[-1]['day']).strftime('%Y%m%d')
        print(f'  days missing within the span: {sorted(set(all_days) - {r["day"] for r in rs})}')
        print(f'  algorithms {dict(collections.Counter(r["header"]["algorithm"] + " " + r["header"]["format"] for r in ok))}; '
              f'layouts {len(set(r["header"]["layout"] for r in ok))}; attr problems '
              f'{dict(collections.Counter(p for r in ok for p in r["header"]["attr_problems"]))}')
        changes = attribute_changes(ok)
        print(f'  dataset attributes changing over the record ({"|".join(VARIABLE_ATTRS)}): {len(changes)}')
        for name, values in changes.items():
            for value, (first, last, count) in values.items():
                print(f'    {name}: {value!r} {first} .. {last} ({count} files)')
        for field in ('rows_not_observed', 'lat_out', 'lon_out', 'time_not_whole_seconds',
                      'time_vs_datetime_utc_mismatch', 'duplicate_keys', 'rows_before_day', 'rows_after_day',
                      'grid_mismatch_rows', 'holes_above_lowest', 'rows_without_pressure',
                      'air_density_fill_unlike_pressure', 'kernel_fill_unlike_pressure_rows',
                      'obs_error_h2o_written_below_surface', 'obs_error_h2o_fill_above_surface',
                      'retrieval_pressure_not_in_fm', 'retrieval_pressure_in_fm_twice',
                      'altitude_fill_at_retrieval_pressure', 'dofs_differs_from_signal_dof',
                      'quality1_dof_below_1p1', 'h2o_h2o_vs_averaging_kernel_h2o_rows_differ',
                      'steps_back', 'steps_back_over_120s'):
            hits = [(r['day'], r[field]) for r in ok if r.get(field)]
            print(f'  {field}: {len(hits)} files, {sum(h[1] for h in hits):,} {hits[:3]}')
        print(f'  target_id not unique: {[(r["day"], r["nobs"] - r["target_id_unique"]) for r in ok if r["target_id_unique"] != r["nobs"]][:5]}')
        print(f'  largest step back {max(r["largest_step_back_s"] for r in ok) / 3600:.1f} h; leap seconds '
              f'{sorted(set(v for r in ok for v in r["leap_seconds"]))}; grids '
              f'{collections.Counter(tuple(r["grid"][1:]) for r in ok).most_common(2)}')
        beyond = collections.Counter()
        unlike = collections.Counter()
        for r in ok:
            beyond.update(r['written_beyond_level_16'])
            unlike.update(r['fill_unlike_pressure'])
        print(f'  R42, written beyond level 16 (or copies differing): {dict(beyond)}')
        print(f'  profile fill unlike pressure (rows): {dict(unlike)}')
        print(f'  altitude 0 at the lowest level: {dict(sum((collections.Counter(r["altitude_at_lowest_level"]) for r in ok), collections.Counter()))}')
        print(f'  R22 x[0] == x_test: {sum(r["r22_x0_is_x_test"] for r in ok)}; compacted '
              f'{sum(r["r22_x0_is_x_test_compacted"] for r in ok)} of {len(ok)}')
        qual = sum((collections.Counter(r['quality']) for r in ok), collections.Counter())
        print(f'  quality {dict(qual)}; DOF range by quality: '
              f'{ {k: [min(r["dof_by_quality"][k][0] for r in ok if k in r["dof_by_quality"]), max(r["dof_by_quality"][k][1] for r in ok if k in r["dof_by_quality"])] for k in qual} }')
        for flag in ('day_night_flag', 'land_flag'):
            print(f'  {flag} {dict(sum((collections.Counter(r[flag]) for r in ok), collections.Counter()))}')
        print(f'  R36 files with land_flag 1 on every row: {[r["day"] for r in ok if set(r["land_flag"]) == {"1"}]}')
        fills = collections.defaultdict(collections.Counter)
        for r in ok:
            for name, entry in r['fills'].items():
                fills[name].update(entry)
        print('  fill by stored source (values):', {n: dict(c) for n, c in sorted(fills.items())})
        print(f'  850-250: dd_col_p max diff {max((r["dd_col_p_max_diff"] or 0) for r in ok):.4f}; x_h2o_col_p max rel '
              f'{max((r["x_h2o_col_p_max_rel"] or 0) for r in ok):.2e}; dd_col_p_error fill '
              f'{dict(sum((collections.Counter(r["dd_col_p_error_fill"]) for r in ok), collections.Counter()))}; '
              f'x_h2o max {max(r["x_h2o_max"] for r in ok):.3f}')
        print('  repeats with earlier files (R37; the v1/v2 seam on the first two days):')
        lag_totals = collections.Counter()
        differs = collections.Counter()
        identical, newer = 0, collections.Counter()
        for r in ok:
            for prior, entry in r['repeats'].items():
                lag = (pd.Timestamp(r['day']) - pd.Timestamp(prior)).days
                seam = 'Standard' in entry['file']
                lag_totals[f'lag {lag}{" v1 seam" if seam else ""}'] += entry['shared']
                if entry['shared'] and not seam:
                    differs.update(entry.get('differs', {}))
                    identical += entry.get('identical_rows', 0)
                    newer['later file newer' if r['header']['production'] > entry['production'] else 'later file older'] += 1
        print(f'    shared rows {dict(lag_totals)}; identical {identical:,}; sources differing (rows) {dict(differs)}; '
              f'production order of the pairs {dict(newer)}')


def main():
    if sys.argv[1] == '--summarize':
        summarize(sys.argv[2])
        return
    output = sys.argv[1]
    started = time.time()
    days = listing(list(PRODUCTS))
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
        days = [d for product in PRODUCTS for d in (lambda s: s[::max(1, len(s) // limit)][:limit])(
            [d for d in days if d['product'] == product])]
    workers = len(os.sched_getaffinity(0))
    if '--workers' in sys.argv:
        workers = min(workers, int(sys.argv[sys.argv.index('--workers') + 1]))
    print(f'{len(days)} days, {workers} workers', flush=True)
    with open(output, 'w') as handle, multiprocessing.Pool(workers) as pool:
        for count, record in enumerate(pool.imap_unordered(audit, days, chunksize=1), 1):
            handle.write(json.dumps(record) + '\n')
            if count % 20 == 0:
                handle.flush()
                print(f'{count} days in {time.time() - started:.0f} s', flush=True)
    print(f'done in {time.time() - started:.0f} s')
    summarize(output)


if __name__ == '__main__':
    main()
