"""Footprint polygons, their overlap with each grid cell, and their areas.

From ``notebooks/drafting/tropomi_tools.py`` (``footprint_overlaps``,
``footprint_area_km2``, ``overlap_km2``; method decided 2026-11-09,
gridding-method.md Section 5):

- a footprint is the polygon joining its corners in order with straight
  edges, drawn in the grid's plane; its value holds uniformly inside;
- one whose corners span more than 180° of longitude crosses the
  antimeridian: it is moved to one side and its cells wrap back; one that
  still spans more than ``MAX_LON_SPAN`` encloses a pole and is not gridded,
  nor is one with a missing corner;
- the polygon is clipped to every cell of its bounding box
  (Sutherland-Hodgman, vectorized) and each piece's area taken by the
  shoelace formula; footprints are clipped in blocks of about ``max_pairs``
  (footprint, cell) pairs so memory is bounded however many there are;
- overlaps become km²: exact on EASE (equal-area), the overlap's share of
  its cell times the cell's true area on lat/lon;
- a footprint's whole area is its shoelace area in the EASE-Grid 2.0 global
  plane, whatever grid is built, so it compares between grids.

Only the ``corners`` footprint model exists so far: TROPOMI's. A sensor
with centres only needs its own model and a user decision first (STATE.md).
"""
import numpy as np

from utils.grids import ease2_xy

# a quadrilateral clipped by a cell's four sides keeps at most 8 vertices
MAX_VERTICES = 8
# a footprint spanning more than this after unwrapping encloses a pole
MAX_LON_SPAN = 90.0


def unwrap(lat_corners, lon_corners):
    """Corners as float64, moved to one side of the antimeridian, and which footprints are griddable.

    Args:
        lat_corners, lon_corners (numpy.ndarray): ``(n, corners)``, degrees.

    Returns:
        tuple: ``(lat, lon, usable)``; ``usable`` is False for a footprint with
            a missing corner or one that encloses a pole.
    """
    lat = np.asarray(lat_corners, dtype='float64')
    lon = np.asarray(lon_corners, dtype='float64').copy()
    crosses = np.nanmax(lon, axis=1) - np.nanmin(lon, axis=1) > 180
    lon[crosses] = np.where(lon[crosses] < 0, lon[crosses] + 360, lon[crosses])
    finite = np.isfinite(lat).all(axis=1) & np.isfinite(lon).all(axis=1)
    span = np.where(finite, np.nanmax(lon, axis=1) - np.nanmin(lon, axis=1), np.inf)
    return lat, lon, finite & (span <= MAX_LON_SPAN)


def footprint_area_km2(lat, lon):
    """Each footprint's whole area in km², in the EASE-Grid 2.0 equal-area plane.

    Args:
        lat, lon (numpy.ndarray): ``(n, corners)``, unwrapped (``unwrap``).

    Returns:
        numpy.ndarray: float64 km².
    """
    x, y = ease2_xy(lat, lon)
    return 0.5 * np.abs((x * np.roll(y, -1, axis=1) - np.roll(x, -1, axis=1) * y).sum(axis=1)) / 1e6


def _clip(x, y, n, along_x, bound, keep_above):
    """Clip polygons to one half-plane (one Sutherland-Hodgman pass, vectorized).

    Args:
        x, y (numpy.ndarray): ``(pairs, MAX_VERTICES)``; only the first ``n``
            vertices of each row are used.
        n (numpy.ndarray): Vertices per polygon.
        along_x (bool): Clip on x (else y).
        bound (float): The half-plane's edge.
        keep_above (bool): Keep the side >= bound (else <= bound).

    Returns:
        tuple: ``(x, y, n)`` of the clipped polygons.
    """
    k = np.arange(MAX_VERTICES)
    valid = k < n[:, None]
    following = (k + 1) % np.maximum(n, 1)[:, None]
    x2 = np.take_along_axis(x, following, axis=1)
    y2 = np.take_along_axis(y, following, axis=1)
    sign = 1.0 if keep_above else -1.0
    d1 = sign * ((x if along_x else y) - bound)
    d2 = sign * ((x2 if along_x else y2) - bound)
    in1, in2 = d1 >= 0, d2 >= 0
    crosses = valid & (in1 != in2)
    with np.errstate(divide='ignore', invalid='ignore'):
        t = np.where(crosses, d1 / (d1 - d2), 0.0)
    # each edge v1 -> v2 emits [its crossing, if it crosses], [v2, if v2 is kept]
    out_x = np.stack([x + t * (x2 - x), x2], axis=-1).reshape(len(n), -1)
    out_y = np.stack([y + t * (y2 - y), y2], axis=-1).reshape(len(n), -1)
    keep = np.stack([crosses, valid & in2], axis=-1).reshape(len(n), -1)
    # move each row's kept vertices to its front, in order
    pair, slot = np.nonzero(keep)
    position = np.cumsum(keep, axis=1)[pair, slot] - 1
    fits = position < MAX_VERTICES
    x_out = np.zeros_like(x)
    y_out = np.zeros_like(y)
    x_out[pair[fits], position[fits]] = out_x[pair[fits], slot[fits]]
    y_out[pair[fits], position[fits]] = out_y[pair[fits], slot[fits]]
    return x_out, y_out, np.minimum(keep.sum(axis=1), MAX_VERTICES)


def _polygon_area(x, y, n):
    """Shoelace area of each polygon's first ``n`` vertices."""
    k = np.arange(MAX_VERTICES)
    following = (k + 1) % np.maximum(n, 1)[:, None]
    cross = x * np.take_along_axis(y, following, axis=1) - np.take_along_axis(x, following, axis=1) * y
    return 0.5 * np.abs(np.where(k < n[:, None], cross, 0.0).sum(axis=1))


def _clip_to_cells(u, v, row0, col0, rows, cols, grid):
    """Every footprint of a block clipped to each cell of its bounding box.

    Returns:
        tuple: ``(footprint, cell, area)`` per pair with a positive overlap:
            the footprint's row in the block, the flat cell, the area in the
            plane's units.
    """
    size, n_cols = grid.size, grid.shape[1]
    per_footprint = rows * cols
    footprint = np.repeat(np.arange(u.shape[0]), per_footprint)
    offset = np.arange(per_footprint.sum()) - np.repeat(np.cumsum(per_footprint) - per_footprint, per_footprint)
    row = row0[footprint] + offset // cols[footprint]
    col = col0[footprint] + offset % cols[footprint]
    # relative to the cell's first corner, so the clip works on small numbers
    corners = u.shape[1]
    x = np.zeros((footprint.size, MAX_VERTICES))
    y = np.zeros((footprint.size, MAX_VERTICES))
    x[:, :corners] = u[footprint] - col[:, None] * size
    y[:, :corners] = v[footprint] - row[:, None] * size
    n = np.full(footprint.size, corners)
    for along_x, bound, keep_above in ((True, 0.0, True), (True, size, False),
                                       (False, 0.0, True), (False, size, False)):
        x, y, n = _clip(x, y, n, along_x, bound, keep_above)
    area = _polygon_area(x, y, n)
    hit = area > 0
    return footprint[hit], row[hit] * n_cols + col[hit] % n_cols, area[hit]


def overlaps(lat, lon, grid, max_pairs=500_000):
    """The area each footprint shares with every cell it touches, in km².

    Args:
        lat, lon (numpy.ndarray): ``(n, 4)`` unwrapped corners of usable
            footprints (``unwrap``).
        grid (utils.grids.Grid): The grid.
        max_pairs (int): Pairs clipped at once; bounds memory (config
            ``max_pairs``).

    Returns:
        tuple: ``(footprint, cell, km2)``: one entry per (footprint, cell)
            pair with a positive overlap. On EASE the part of a footprint
            beyond the grid's edge has no cell and is dropped.
    """
    u, v = grid.plane(lat, lon)
    n_rows = grid.shape[0]
    row0 = np.clip(np.floor(v.min(axis=1) / grid.size).astype('int64'), 0, n_rows - 1)
    row1 = np.clip(np.floor(v.max(axis=1) / grid.size).astype('int64'), 0, n_rows - 1)
    col0 = np.floor(u.min(axis=1) / grid.size).astype('int64')
    col1 = np.floor(u.max(axis=1) / grid.size).astype('int64')
    rows, cols = row1 - row0 + 1, col1 - col0 + 1
    if not grid.clamp_rows:
        # EASE: a footprint wholly beyond the grid's edge has no rows at all
        beyond = (v.max(axis=1) < 0) | (v.min(axis=1) >= n_rows * grid.size)
        rows = np.where(beyond, 0, rows)
    ends = np.cumsum(rows * cols)
    pieces, first = [], 0
    while first < u.shape[0]:
        # whole footprints, up to max_pairs pairs (at least one footprint)
        start = ends[first] - rows[first] * cols[first]
        last = max(first + 1, int(np.searchsorted(ends, start + max_pairs, side='right')))
        block = slice(first, last)
        footprint, cell, area = _clip_to_cells(u[block], v[block], row0[block], col0[block],
                                               rows[block], cols[block], grid)
        pieces.append((footprint + first, cell, area))
        first = last
    if not pieces:
        return np.empty(0, 'int64'), np.empty(0, 'int64'), np.empty(0)
    footprint, cell, area = (np.concatenate(parts) for parts in zip(*pieces))
    if grid.kind == 'ease2':
        return footprint, cell, area / 1e6
    return footprint, cell, area / grid.cell_area_plane * grid.cell_area_km2(cell)
