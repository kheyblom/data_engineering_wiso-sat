"""Make the temporal stores from the tagged spatial stores.

    uv run python rechunk_wisosat.py --config config/<product>/config_grid.yaml

Each spatial store, read only at ``temporal.source_tag`` (its tag after
finalize), becomes a temporal store of the same basename under
``temporal/``: the whole record in each chunk of a tile of cells
(``chunks.temporal``), for reading time series. This is a rechunk, not a
second gridding (user decision 2026-11-10): the values are the spatial
store's, bit for bit, and the verifier checks that on samples.

Region path, after GLEAM/MSWEP: a skeleton commit holds the full shape,
coordinates and attributes; then each block of ``temporal.block_rows`` rows
(a whole number of tiles, every column) is read from the spatial store
period by period into one buffer and written as one region commit. Resume
reads the block commit messages back, so a killed job redoes at most one
block per store. Rerunning a complete set is a no-op.
"""
import argparse
import logging
import os
import time

import dask.array  # type: ignore
import icechunk  # type: ignore
import numpy as np
import xarray as xr  # type: ignore
import zarr  # type: ignore

from utils import config, nomenclature, stores
from utils.grids import from_spec

LOG = logging.getLogger('rechunk_wisosat')
SOURCE_ATTRS_DROPPED = ('history', 'date_created', 'verification', 'layout', 'related_store')

icechunk.set_logs_filter('error')


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--config', required=True)
    return parser.parse_args()


def skeleton(settings, grid, quantity, source, source_path, tag, revision):
    """The temporal store's dataset: numpy coordinates and a lazy data variable of the right shape."""
    name = nomenclature.quantities()[quantity]['canonical_name']
    ds = xr.open_zarr(source, consolidated=False, decode_coords='all')
    data = ds[name]
    n_time = data.shape[0]
    chunks = stores.layout_chunks(settings, grid, 'temporal', n_time)
    lazy = dask.array.empty(data.shape, dtype=data.dtype, chunks=chunks)
    out = xr.Dataset({name: (data.dims, lazy, dict(data.attrs))},
                     coords={key: value.load() for key, value in ds.coords.items()})
    # the spatial variable's own 'coordinates' list (lat(y), lon(x) on EASE): xarray
    # does not rebuild it for a lazy skeleton, so carry it over explicitly
    listed = zarr.open_group(source, mode='r')[name].attrs.get('coordinates')
    if listed:
        out[name].encoding['coordinates'] = listed
    attrs = {key: value for key, value in ds.attrs.items() if key not in SOURCE_ATTRS_DROPPED}
    attrs.update({
        'layout': f'temporal: chunks (time, rows, cols) = {chunks}: the whole record per tile of cells, for time series',
        'related_store': source_path,
        'rechunked_from': f'{source_path} at tag {tag}, by rechunk_wisosat.py @ {revision}; values unchanged',
    })
    out.attrs = attrs
    return out, n_time


def rechunk_store(settings, grid, quantity, source_path, target_path, tag, revision):
    """One store: skeleton if new, then every missing block of rows."""
    name = nomenclature.quantities()[quantity]['canonical_name']
    source_repo = stores.open_repository(source_path)
    if tag not in source_repo.list_tags():
        raise RuntimeError(f'{source_path} has no tag {tag!r}; finalize the spatial stores first')
    source = source_repo.readonly_session(tag=tag).store
    source_array = zarr.open_group(source, mode='r')[name]
    n_time, rows, cols = source_array.shape
    new = not os.path.isdir(target_path)
    repository = stores.open_repository(target_path, create=new)
    if new or not repository.lookup_branch(stores.BRANCH) or len(list(repository.ancestry(branch=stores.BRANCH))) == 1:
        ds, _ = skeleton(settings, grid, quantity, source, source_path, tag, revision)
        enc = stores.encoding(settings, grid, quantity, 'temporal', n_time)
        stores.write_skeleton(repository, ds, enc, stores.SKELETON_MESSAGE.format(revision=revision))
    target = zarr.open_group(repository.readonly_session(branch=stores.BRANCH).store, mode='r')[name]
    if target.shape != source_array.shape:
        raise RuntimeError(f'{target_path}: shape {target.shape} != spatial {source_array.shape}; delete it to rebuild')
    tile_rows = target.chunks[1]
    block_rows = int((settings.get('temporal') or {}).get('block_rows', 200))
    if block_rows % tile_rows:
        raise ValueError(f'temporal.block_rows ({block_rows}) must be a multiple of the tile rows ({tile_rows})')
    done = stores.committed_blocks(repository)
    dims = target.metadata.dimension_names
    time_step = source_array.chunks[0]
    for row0 in range(0, rows, block_rows):
        row1 = min(row0 + block_rows, rows)
        if (row0, row1) in done:
            continue
        started = time.time()
        buffer = np.empty((n_time, row1 - row0, cols), dtype=source_array.dtype)
        # period by period (the spatial chunk), never the whole store at once
        for t0 in range(0, n_time, time_step):
            buffer[t0:t0 + time_step] = source_array[t0:t0 + time_step, row0:row1, :]
        block = xr.Dataset({name: (dims, buffer)})
        stores.write_region(repository, block, {dims[0]: slice(None), dims[1]: slice(row0, row1), dims[2]: slice(None)},
                            stores.BLOCK_MESSAGE.format(row0=row0, row1=row1, revision=revision))
        LOG.info(f'{os.path.basename(target_path)}: rows [{row0}:{row1}) in {time.time() - started:.1f} s')
        del buffer, block


def main():
    args = parse_args()
    settings = config.load_config(args.config)
    config.setup_logging(settings, prefix='rechunk_')
    revision = config.check_clean_tree(settings)
    tag = (settings.get('temporal') or {}).get('source_tag')
    if not tag:
        raise ValueError('temporal.source_tag is not set: rechunk reads the finalized, tagged spatial stores')
    for spec in settings['grids']:
        grid = from_spec(spec)
        for frequency in settings['frequencies']:
            for quantity, row in nomenclature.quantities().items():
                paths = [config.store_path(settings, layout, frequency, grid.name, row['canonical_name'])
                         for layout in ('spatial', 'temporal')]
                rechunk_store(settings, grid, quantity, *paths, tag, revision)
            LOG.info(f'{grid.name} {frequency}: temporal stores complete')


if __name__ == '__main__':
    main()
