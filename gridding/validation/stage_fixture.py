"""Stage the gridding fixtures: a few real granules as tagged L2 stores.

    uv run python validation/stage_fixture.py

Each fixture is a contiguous run of granules copied from the production L2
stores at their tags into a fixture directory, with the granule index
rebased, and tagged with a fixture tag. Only the stores gridding reads are
staged.

- **TROPOMI** (the column method): orbits 14067-14069 of 2020-06-30 and
  07-01, ~2.5 M rows; orbit 14068 crosses midnight, so the fixture holds a
  day edge.
- **AIRS v1 RS** (the profile method): the days 2014-04-04 .. 04-08, 5,605
  rows. 04-05 and 04-06 hold 12 and 13 retrievals, too few to fit the orbit
  phase, so the footprint model carries it from a neighbouring day
  (``utils/airs_fov.py``); 04-07 has 130. The four footprint stores carry a
  tag of their own, as in production (``l2.store_tags``).

A fixture that is already staged is left alone: delete its directory to
restage it. Light: run it on a login node (~1-2 min).
"""
import os
import sys

import icechunk  # type: ignore
import numpy as np
import zarr  # type: ignore

from products import tropess, tropomi
from utils import config
from utils.l2 import L2

FIXTURE_ROOT = '/glade/derecho/scratch/kheyblom/data/wisosat/fixture/gridding/zarr'
L2_FILENAME = 'wisosat.{product}.{version}.inst.native_swath.{store}.zarr'
AIRS_FOOTPRINT = ['granule_number_level_1b', 'scanline_index', 'ground_pixel_index', 'sensor_view_angle']
# per fixture: the production stores and tags, the granules, the stores staged, the obs chunk,
# and the fixture tag of each store (default first)
FIXTURES = {
    'tropomi': {
        'production': {
            'product': 'tropomi', 'version': '8.1',
            'l2': {'directory': '/glade/derecho/scratch/kheyblom/data/wisosat/zarr/tropomi/l2',
                   'filename': L2_FILENAME, 'tag': 'v8.1-verified-20261018'},
        },
        'granules': ('14067', '14068', '14069'),
        'stores': ['geolocation', 'water_vapor_column_delta_d', 'water_vapor_column_delta_d_standard_error',
                   'water_vapor_column_h2o', *tropomi.selection_stores({'quality_level': 'clear_or_low_cloud'})],
        'chunk': 262_144,
        'tag': 'fixture-20261110',
        'store_tags': {},
    },
    'airs': {
        'production': {
            'product': 'airs', 'version': '1', 'version_product': 'rs',
            'l2': {'directory': '/glade/derecho/scratch/kheyblom/data/wisosat/zarr/airs/l2',
                   'filename': L2_FILENAME, 'tag': 'v1-verified-20261023',
                   'store_tags': {store: 'v1-verified-20261113' for store in AIRS_FOOTPRINT}},
        },
        'granules': ('20140404', '20140405', '20140406', '20140407', '20140408'),
        'stores': ['geolocation', 'water_vapor_hdo_h2o_ratio', 'water_vapor_h2o_mole_fraction_dry_air', 'pressure',
                   'water_vapor_hdo_h2o_ratio_apriori', 'water_vapor_hdo_h2o_ratio_averaging_kernel_log',
                   *AIRS_FOOTPRINT, *tropess.selection_stores({'quality_level': 'summary_daytime'})],
        # small, so the kernel (obs, level, level_2) is read over several chunks
        'chunk': 2_048,
        'tag': 'fixture-20261113',
        'store_tags': {store: 'fixture-20261113-footprint' for store in AIRS_FOOTPRINT},
    },
}

icechunk.set_logs_filter('error')


def stage(name, spec):
    """Copy one fixture's granules from production into its fixture directory, tagged."""
    production = spec['production']
    target = os.path.join(FIXTURE_ROOT, name, 'l2')
    if os.path.exists(target):
        print(f'{name}: {target} exists; delete it to restage')
        return
    source = L2(production)
    geo = source.group('geolocation')
    ids = geo['granule_id'][:]
    rows = np.flatnonzero(np.isin(ids, np.array(spec['granules'], dtype=ids.dtype)))
    if rows.size != len(spec['granules']):
        sys.exit(f'{name}: expected {len(spec["granules"])} granules, found {rows.size}')
    starts = geo['granule_obs_start'][rows]
    counts = geo['granule_obs_count'][rows]
    window = slice(int(starts[0]), int(starts[-1] + counts[-1]))
    if not np.array_equal(starts[1:], starts[:-1] + counts[:-1]):
        sys.exit(f'{name}: the granules are not contiguous along obs')
    print(f'{name}: granules {spec["granules"]}: obs {window.start:,}..{window.stop:,} '
          f'({window.stop - window.start:,} rows)')
    staged = {**production, 'l2': {**production['l2'], 'directory': target}}
    for store in list(dict.fromkeys(spec['stores'])):
        group = source.group(store)
        repository = icechunk.Repository.create(icechunk.local_filesystem_storage(config.l2_store_path(staged, store)))
        session = repository.writable_session('main')
        root = zarr.open_group(session.store, mode='w')
        root.attrs.update({**dict(group.attrs), 'fixture': (
            f'TEST FIXTURE for data_engineering_wiso-sat/gridding: granules {", ".join(spec["granules"])} copied '
            f'from {production["l2"]["directory"]} at tag {source.tag_of(store)}. Not data.')})
        for array_name, array in group.arrays():
            if array.metadata.dimension_names[0] == 'granule':
                values = array[rows]
                if array_name == 'granule_obs_start':
                    values = values - window.start
                chunks = (len(rows),)
            else:
                values = array[window]
                chunks = (spec['chunk'], *array.shape[1:])
            new = root.create_array(array_name, shape=values.shape,
                                    dtype=str if values.dtype.kind in 'OTU' else values.dtype,
                                    chunks=chunks, fill_value=array.fill_value,
                                    dimension_names=array.metadata.dimension_names, attributes=dict(array.attrs))
            new[...] = values
        session.commit(f'stage the gridding fixture from {source.tag_of(store)}')
        tag = spec['store_tags'].get(store, spec['tag'])
        repository.create_tag(tag, repository.lookup_branch('main'))
        print(f'  {store}: staged and tagged {tag}')


def main():
    for name, spec in FIXTURES.items():
        stage(name, spec)


if __name__ == '__main__':
    main()
