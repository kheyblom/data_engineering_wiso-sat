"""Stage the gridding fixture: a few real TROPOMI orbits as tagged L2 stores.

    uv run python validation/stage_fixture.py

Copies orbits 14067-14069 (2020-06-30 21:51 to 2020-07-01 ~03:00 UTC, about
2.5 M rows; orbit 14068 crosses midnight, so the fixture holds a day edge
and a month edge) out of the finalized TROPOMI L2 stores, at their tag,
into small icechunk stores of the same layout under ``FIXTURE_L2``: the
same arrays, dtypes, attributes and granule index (rebased), chunked small,
and tagged ``FIXTURE_TAG``. Only the stores gridding reads are staged:
geolocation, the three inputs and the ``clear_or_low_cloud`` inputs.

Delete ``FIXTURE_L2`` to restage; the script refuses to overwrite.
Light: run it on a login node (~1-2 min).
"""
import os
import sys

import icechunk  # type: ignore
import numpy as np
import zarr  # type: ignore

from products import tropomi
from utils import config
from utils.l2 import L2

PRODUCTION = {
    'product': 'tropomi', 'version': '8.1',
    'l2': {'directory': '/glade/derecho/scratch/kheyblom/data/wisosat/zarr/tropomi/l2',
           'filename': 'wisosat.{product}.{version}.inst.native_swath.{store}.zarr',
           'tag': 'v8.1-verified-20261018'},
}
FIXTURE_L2 = '/glade/derecho/scratch/kheyblom/data/wisosat/fixture/gridding/zarr/tropomi/l2'
FIXTURE_TAG = 'fixture-20261110'
ORBITS = ('14067', '14068', '14069')
CHUNK = 262_144
STORES = ['geolocation', 'water_vapor_column_delta_d', 'water_vapor_column_delta_d_standard_error',
          'water_vapor_column_h2o', *tropomi.selection_stores({'quality_level': 'clear_or_low_cloud'})]
STORES = list(dict.fromkeys(STORES))

icechunk.set_logs_filter('error')


def main():
    if os.path.exists(FIXTURE_L2):
        sys.exit(f'{FIXTURE_L2} exists; delete it to restage')
    source = L2(PRODUCTION)
    geo = source.group('geolocation')
    ids = geo['granule_id'][:]
    rows = np.flatnonzero(np.isin(ids, np.array(ORBITS, dtype=ids.dtype)))
    if rows.size != len(ORBITS):
        sys.exit(f'expected {len(ORBITS)} orbits, found {rows.size}')
    starts = geo['granule_obs_start'][rows]
    counts = geo['granule_obs_count'][rows]
    window = slice(int(starts[0]), int(starts[-1] + counts[-1]))
    if not np.array_equal(starts[1:], starts[:-1] + counts[:-1]):
        sys.exit('the orbits are not contiguous along obs')
    print(f'orbits {ORBITS}: obs {window.start:,}..{window.stop:,} ({window.stop - window.start:,} rows)')
    for store in STORES:
        group = source.group(store)
        repository = icechunk.Repository.create(icechunk.local_filesystem_storage(
            config.l2_store_path({**PRODUCTION, 'l2': {**PRODUCTION['l2'], 'directory': FIXTURE_L2}}, store)))
        session = repository.writable_session('main')
        root = zarr.open_group(session.store, mode='w')
        root.attrs.update({**dict(group.attrs), 'fixture': (
            f'TEST FIXTURE for data_engineering_wiso-sat/gridding: orbits {", ".join(ORBITS)} copied from '
            f'{PRODUCTION["l2"]["directory"]} at tag {PRODUCTION["l2"]["tag"]}. Not data.')})
        for name, array in group.arrays():
            if array.metadata.dimension_names[0] == 'granule':
                values = array[rows]
                if name == 'granule_obs_start':
                    values = values - window.start
                chunks = (len(rows),)
            else:
                values = array[window]
                chunks = (CHUNK, *array.shape[1:])
            new = root.create_array(name, shape=values.shape, dtype=str if values.dtype.kind in 'OTU' else values.dtype,
                                    chunks=chunks, fill_value=array.fill_value,
                                    dimension_names=array.metadata.dimension_names, attributes=dict(array.attrs))
            new[...] = values
        session.commit(f'stage the gridding fixture from {PRODUCTION["l2"]["tag"]}')
        repository.create_tag(FIXTURE_TAG, repository.lookup_branch('main'))
        print(f'  {store}: staged and tagged {FIXTURE_TAG}')


if __name__ == '__main__':
    main()
