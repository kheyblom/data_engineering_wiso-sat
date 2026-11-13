"""AIRS v1 selection counts on every row: the D5 rule and D7's day/night split.

Evidence for AIRS gridding decisions D5 and D7 (`airs-gridding-decisions.md`,
2026-11-13), from the finalized L2 stores at v1-verified-20261023:
- DOF > 1.1 against `dd_col_p` being written (no row has `dd_col_p` with
  DOF <= 1.1; RS 1,939 and FS 54,510 rows have DOF > 1.1 and no `dd_col_p`;
  RS 1,588 and FS 53,455 have `dd_col_p` and no DOF);
- rows kept by D5's `summary` rule (DOF > 1.1, or DOF missing and `dd_col_p`
  written): RS 11,065,071, FS 19,126,176;
- those rows by `day_night_flag` (RS 5,066,094 flag 1, 5,998,972 flag 0, 5 fill;
  FS 18,423,705 / 668,400 / 34,071).
Also confirms that the Summary-only day RS 2020-03-31 has every profile filled.

From gridding/: uv run python tools/survey/airs_selection_counts.py (~1 GB read).
"""
import icechunk
import numpy as np
import zarr

icechunk.set_logs_filter('error')
BASE = ('/glade/derecho/scratch/kheyblom/data/wisosat/zarr/airs/l2/'
        'wisosat.airs.v_1.{}.inst.native_swath.{}.zarr')
TAG = 'v1-verified-20261023'
BLOCK = 4_194_304
DOF = 'water_vapor_hdo_h2o_ratio_degrees_of_freedom_for_signal'
DD = 'water_vapor_delta_d_850_250hpa'
PROFILES = ('water_vapor_hdo_h2o_ratio', 'water_vapor_h2o_mole_fraction_dry_air', 'pressure')


def group(stream, store):
    repo = icechunk.Repository.open(icechunk.local_filesystem_storage(BASE.format(stream, store)))
    return zarr.open_group(repo.readonly_session(tag=TAG).store, mode='r')


for stream in ('rs', 'fs'):
    dof, dd = group(stream, DOF)[DOF], group(stream, DD)[DD]
    flag = group(stream, 'day_night_flag')['day_night_flag']
    counts = dict.fromkeys(('rows', 'dof_and_dd', 'dof_no_dd', 'dd_no_dof', 'dd_dof_le', 'kept'), 0)
    by_flag = {}
    for i in range(0, dof.shape[0], BLOCK):
        d, w = dof[i:i + BLOCK], np.isfinite(dd[i:i + BLOCK])
        above = d > np.float32(1.1)
        keep = above | (~np.isfinite(d) & w)
        counts['rows'] += d.size
        counts['dof_and_dd'] += int((above & w).sum())
        counts['dof_no_dd'] += int((above & ~w).sum())
        counts['dd_no_dof'] += int((w & ~np.isfinite(d)).sum())
        counts['dd_dof_le'] += int((w & np.isfinite(d) & ~above).sum())
        counts['kept'] += int(keep.sum())
        values, n = np.unique(flag[i:i + BLOCK][keep], return_counts=True)
        for v, k in zip(values.tolist(), n.tolist()):
            by_flag[v] = by_flag.get(v, 0) + k
    print(stream, counts, 'kept rows by day_night_flag', by_flag)

# the RS Summary-only day: profiles filled, DOF missing
geo = group('rs', 'geolocation')
index = {name: geo[name][:] for name in ('granule_time_start', 'granule_time_end', 'granule_obs_start', 'granule_obs_count')}
day0 = (np.datetime64('2020-03-31') - np.datetime64('1900-01-01')).astype('timedelta64[s]').astype(float)
k = int(np.flatnonzero((index['granule_time_start'] >= day0) & (index['granule_time_start'] < day0 + 86400))[0])
rows = slice(int(index['granule_obs_start'][k]), int(index['granule_obs_start'][k] + index['granule_obs_count'][k]))
for store in (*PROFILES, DOF):
    a = group('rs', store)[store][rows]
    print(f'rs 2020-03-31 {store}: rows with a value {np.isfinite(a.reshape(a.shape[0], -1)).any(axis=1).sum()} of {a.shape[0]}')
