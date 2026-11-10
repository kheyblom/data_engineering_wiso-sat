"""Gridded stores: coordinates, encoding, and the two write paths.

One store per variable (style guide), each its own icechunk repository with
one branch, ``main``. Two layouts of the same basename (user decisions
2026-11-10, after GLEAM/MSWEP):
- ``spatial/``: chunks of one period and the whole grid (or the config's
  tile), built from L2 by ``grid_wisosat.py`` with **append** commits of
  ``periods_per_commit`` periods. Resume is the store's own length.
- ``temporal/``: the whole record in each chunk of a small spatial tile,
  made by ``rechunk_wisosat.py`` from the tagged spatial store with
  **region** writes into a skeleton, one block of rows per commit. Resume
  reads the block commit messages back.

Coordinates: ``time`` is each period's first day, int64 days since
1900-01-01 (proleptic_gregorian), with ``time_bounds`` giving its end;
rows run north to south. Lat/lon grids are (time, lat, lon); EASE grids are
(time, y, x) in EPSG:6933 metres, with 1-D ``lat(y)`` and ``lon(x)``
(separable). Both carry cell edges and ``cell_area`` (km², per row).

Empty cells: statistics are NaN, the sums are 0 (a sum over no footprints;
it adds over days as it should) and ``observation_count`` is 0.
"""
import logging
import re

import icechunk  # type: ignore
import numpy as np
import xarray as xr  # type: ignore
import zarr  # type: ignore
from icechunk.xarray import to_icechunk  # type: ignore

from utils import nomenclature, periods

LOG = logging.getLogger(__name__)
BRANCH = 'main'
TIME_UNITS = 'days since 1900-01-01'
CALENDAR = 'proleptic_gregorian'
APPEND_MESSAGE = 'write periods {first}..{last} ({count}) @ {revision}'
APPEND_RE = re.compile(r'^write periods (?P<first>\S+)\.\.(?P<last>\S+) \((?P<count>\d+)\) @ (?P<revision>\S+)$')
BLOCK_MESSAGE = 'write rows [{row0}:{row1}) @ {revision}'
BLOCK_RE = re.compile(r'^write rows \[(?P<row0>\d+):(?P<row1>\d+)\) @ (?P<revision>\S+)$')
SKELETON_MESSAGE = 'create skeleton @ {revision}'

icechunk.set_logs_filter('error')


def dims(grid):
    """The two spatial dimension names of a grid's stores."""
    return ('lat', 'lon') if grid.kind == 'latlon' else ('y', 'x')


def grid_coords(grid):
    """Every non-time coordinate of a grid's stores, as xarray variables."""
    row, col = dims(grid)
    lat_bounds = np.stack([grid.lat_edges[:-1], grid.lat_edges[1:]], axis=1)
    lon_bounds = np.stack([grid.lon_edges[:-1], grid.lon_edges[1:]], axis=1)
    coords = {
        'lat': (row, grid.row_lat, {'long_name': 'latitude of the cell centre', 'units': 'degrees_north',
                                    'bounds': 'lat_bounds'}),
        'lon': (col, grid.col_lon, {'long_name': 'longitude of the cell centre', 'units': 'degrees_east',
                                    'bounds': 'lon_bounds'}),
        'lat_bounds': ((row, 'bounds'), lat_bounds, {'long_name': 'latitude of the cell edges (north, south)',
                                                    'units': 'degrees_north'}),
        'lon_bounds': ((col, 'bounds'), lon_bounds, {'long_name': 'longitude of the cell edges (west, east)',
                                                    'units': 'degrees_east'}),
        'cell_area': (row, grid.row_area_km2(), {'long_name': 'area of a grid cell', 'units': 'km2',
                                                 'comment': _area_comment(grid)}),
    }
    if grid.kind == 'ease2':
        coords['y'] = ('y', grid.y_centres, {'long_name': 'EASE-Grid 2.0 projected y of the cell centre',
                                             'units': 'm', 'axis': 'Y'})
        coords['x'] = ('x', grid.x_centres, {'long_name': 'EASE-Grid 2.0 projected x of the cell centre',
                                             'units': 'm', 'axis': 'X'})
        coords['crs'] = ((), np.int32(0), {
            'grid_mapping_name': 'lambert_cylindrical_equal_area',
            'standard_parallel': 30.0, 'longitude_of_central_meridian': 0.0,
            'false_easting': 0.0, 'false_northing': 0.0,
            'semi_major_axis': 6378137.0, 'inverse_flattening': 298.257223563,
            'epsg_code': 'EPSG:6933', 'long_name': f'EASE-Grid 2.0 global ({grid.nsidc_name})',
        })
    return {name: xr.Variable(*spec) for name, spec in coords.items()}


def _area_comment(grid):
    if grid.kind == 'ease2':
        return 'every cell has the same area: the grid is equal-area on the WGS84 ellipsoid'
    return 'on a sphere of radius 6371 km: R^2 * resolution (rad) * (sin(north) - sin(south))'


def time_variables(bounds):
    """``time`` (period start) and ``time_bounds`` (start, exclusive end) from day numbers."""
    start = periods.EPOCH + bounds[:, 0].astype('timedelta64[D]')
    edges = periods.EPOCH + bounds.astype('timedelta64[D]')
    return {
        'time': xr.Variable('time', start.astype('datetime64[ns]'),
                            {'long_name': 'first day of the period', 'bounds': 'time_bounds'}),
        'time_bounds': xr.Variable(('time', 'bounds'), edges.astype('datetime64[ns]'),
                                   {'long_name': 'first day of the period and the day after its last'}),
    }


def dataset(settings, grid, quantity, data, bounds, attrs, static=True):
    """One store's batch as an xarray Dataset.

    Args:
        settings (dict): The config.
        grid (utils.grids.Grid): The grid.
        quantity (str): The key's quantity ('delta_d').
        data (numpy.ndarray): ``(periods, rows, cols)``.
        bounds (numpy.ndarray): ``(periods, 2)`` day numbers.
        attrs (dict): The store's global attributes.
        static (bool): Include the non-time coordinates (first write only:
            an append would rewrite them every batch).

    Returns:
        xarray.Dataset: Variable named by its canonical name.
    """
    row = nomenclature.quantities()[quantity]
    name = row['canonical_name']
    variable_attrs = {**nomenclature.authority_attrs(settings, quantity),
                      **(settings.get('variable_attrs') or {}).get(quantity, {})}
    if grid.kind == 'ease2':
        variable_attrs['grid_mapping'] = 'crs'
    coords = time_variables(bounds)
    if static:
        coords.update(grid_coords(grid))
    data_vars = {name: xr.Variable(('time', *dims(grid)), data.astype(row['dtype']), variable_attrs)}
    if 'time_bounds' in coords:
        data_vars['time_bounds'] = coords.pop('time_bounds')
    return xr.Dataset(data_vars, coords=coords, attrs=attrs)


def encoding(settings, grid, quantity, layout, n_time=None):
    """Chunks, dtype, fill and time encoding of one store.

    Args:
        layout (str): 'spatial' or 'temporal'.
        n_time (int | None): The full time length (temporal chunks hold it all).
    """
    row = nomenclature.quantities()[quantity]
    chunks = layout_chunks(settings, grid, layout, n_time)
    fill = None if np.issubdtype(np.dtype(row['dtype']), np.integer) else np.nan
    time_chunk = chunks[0] if layout == 'temporal' else int(settings.get('periods_per_commit', 10))
    return {
        row['canonical_name']: {'chunks': chunks, 'dtype': row['dtype'], '_FillValue': fill},
        'time': {'units': TIME_UNITS, 'calendar': CALENDAR, 'dtype': 'int64', 'chunks': (time_chunk,)},
        'time_bounds': {'units': TIME_UNITS, 'calendar': CALENDAR, 'dtype': 'int64', 'chunks': (time_chunk, 2)},
    }


def layout_chunks(settings, grid, layout, n_time=None):
    """(time, rows, cols) chunk shape: config ``chunks.<layout>``, per grid override, -1 = whole axis.

    Spatial defaults to one period and the whole grid; temporal to the whole
    record and 20 x 20 cells (GLEAM/MSWEP's tile).
    """
    spec = {**(settings['chunks'].get(layout) or {}),
            **((grid_spec(settings, grid).get('chunks') or {}).get(layout) or {})}
    defaults = {'spatial': (1, -1, -1), 'temporal': (-1, 20, 20)}[layout]
    shape = (n_time or 1, *grid.shape)
    chunk = [spec.get(key, default) for key, default in zip(('time', 'rows', 'cols'), defaults)]
    return tuple(int(full if size == -1 else min(size, full)) for size, full in zip(chunk, shape))


def grid_spec(settings, grid):
    """The config entry that produced a grid."""
    from utils.grids import from_spec
    return next(spec for spec in settings['grids'] if from_spec(spec).name == grid.name)


def open_repository(path, create=False):
    """A store's repository; created only when asked, so a typo never makes an empty one."""
    storage = icechunk.local_filesystem_storage(path)
    if create:
        return icechunk.Repository.open_or_create(storage)
    return icechunk.Repository.open(storage)


def stored_times(repository):
    """The stored ``time_bounds`` as day numbers (``(n, 2)``), empty if nothing is written."""
    session = repository.readonly_session(branch=BRANCH)
    try:
        group = zarr.open_group(session.store, mode='r')
        array = group['time_bounds']
    except (KeyError, FileNotFoundError, zarr.errors.GroupNotFoundError):
        return np.empty((0, 2), dtype='int64')
    raw = array[:]
    units = array.attrs.get('units', TIME_UNITS)
    if units != TIME_UNITS:
        raise ValueError(f'unexpected time_bounds units {units!r}')
    return raw.astype('int64')


def write_append(repository, ds, encoding_, first, message):
    """One append commit: the first batch creates the store, later ones extend ``time``.

    xarray replaces the group's attributes on append with the appended
    dataset's (L2 finding, 2026-10-14), so every batch carries them.
    """
    session = repository.writable_session(BRANCH)
    if first:
        to_icechunk(ds, session, mode='w', encoding=encoding_)
    else:
        to_icechunk(ds, session, append_dim='time')
    return session.commit(message)


def write_skeleton(repository, ds, encoding_, message):
    """The temporal store's full shape, coordinates and attributes; no data chunks.

    ``ds`` holds its coordinates (and ``time_bounds``) as numpy, written now,
    and its data variable as a lazy dask array, which ``compute=False``
    leaves unwritten (GLEAM/MSWEP's region path).
    """
    session = repository.writable_session(BRANCH)
    ds.to_zarr(session.store, mode='w', compute=False, encoding=encoding_, zarr_format=3, consolidated=False)
    return session.commit(message)


def write_region(repository, ds, region, message):
    """One block of rows of the temporal store, then commit."""
    session = repository.writable_session(BRANCH)
    to_icechunk(ds, session, region=region)
    return session.commit(message)


def committed_blocks(repository):
    """``(row0, row1)`` of every block commit on main, from the commit messages."""
    blocks = set()
    for snapshot in repository.ancestry(branch=BRANCH):
        match = BLOCK_RE.match(snapshot.message)
        if match:
            blocks.add((int(match['row0']), int(match['row1'])))
    return blocks
