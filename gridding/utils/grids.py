"""The two global grid types: regular lat/lon and EASE-Grid 2.0 global.

From ``notebooks/drafting/tropomi_tools.py`` (decided 2026-11-09), with one
change: lat/lon rows now run north to south, as EASE's do and as the
GLEAM/MSWEP stores' ``lat`` does, so both grid types store row 0 at the top.

Both grids are separable (rows are parallels, columns meridians), so a cell
is one flat index ``row * n_cols + col`` and its centre a row latitude and a
column longitude. Each defines a plane in which its cells are squares of
side ``size``, and the footprint clip (``utils/footprints.py``) works there:
- lat/lon: (lon + 180, 90 - lat), degrees;
- EASE-Grid 2.0 global (EPSG:6933; Brodzik et al. 2012, 2014): (x - x_min,
  y_max - y), projected metres, closed form on the WGS84 ellipsoid through
  the authalic latitude (Snyder 1987). Equal-area, so overlap areas are true
  m². It stops short of the poles (±85.04° or ±84.44°).

A config names a grid as ``{type: latlon, resolution: 0.25}`` or
``{type: ease2, name: M25km}``; the EASE table below is NSIDC's published
definition of its standard global grids, not a setting.
"""
import functools

import numpy as np

WGS84_A = 6378137.0
WGS84_E2 = 0.00669437999014
_WGS84_E = np.sqrt(WGS84_E2)
# the projection's scale factor on its true parallels, ±30° (Snyder 1987,
# cylindrical equal-area on the ellipsoid)
_EASE2_K0 = np.cos(np.radians(30)) / np.sqrt(1 - WGS84_E2 * np.sin(np.radians(30)) ** 2)
# sphere for lat/lon cell areas (gridding-method.md, Section 3)
EARTH_KM = 6371.0

# NSIDC's EASE-Grid 2.0 global grids: cell side (m), columns, rows. Two
# families, each nesting within itself only: 36/9/3/1 km and
# 25/12.5/6.25/3.125 km.
EASE2_GLOBAL = {
    'M36km': (36032.220840584, 964, 406),
    'M09km': (9008.055210146, 3856, 1624),
    'M03km': (3002.6850700487, 11568, 4872),
    'M01km': (1000.89502334956, 34704, 14616),
    'M25km': (25025.26, 1388, 584),
    'M12.5km': (12512.63, 2776, 1168),
    'M6.25km': (6256.315, 5552, 2336),
    'M3.125km': (3128.1575, 11104, 4672),
}


def _authalic_q(lat):
    """Snyder's q (his eq. 3-12) at geodetic latitude ``lat`` in degrees."""
    s = np.sin(np.radians(lat))
    return (1 - WGS84_E2) * (s / (1 - WGS84_E2 * s**2)
                             - np.log((1 - _WGS84_E * s) / (1 + _WGS84_E * s)) / (2 * _WGS84_E))


_Q_POLE = _authalic_q(90.0)


def ease2_xy(lat, lon):
    """EASE-Grid 2.0 global projected coordinates (EPSG:6933), in metres.

    ``lon`` is used as given, not wrapped, so a footprint unwrapped past 180°
    lands past the grid's east edge, as on lat/lon. Agrees with pyproj to
    1e-8 m (drafting notes).
    """
    lat, lon = np.asarray(lat, dtype='float64'), np.asarray(lon, dtype='float64')
    return WGS84_A * _EASE2_K0 * np.radians(lon), WGS84_A * _authalic_q(lat) / (2 * _EASE2_K0)


def ease2_lat(y):
    """Geodetic latitude at EASE-Grid 2.0 global ``y`` (m), by Snyder's series (eq. 3-18)."""
    e2 = WGS84_E2
    beta = np.arcsin(np.clip(2 * _EASE2_K0 * np.asarray(y, dtype='float64') / (WGS84_A * _Q_POLE), -1, 1))
    return np.degrees(beta + (e2 / 3 + 31 * e2**2 / 180 + 517 * e2**3 / 5040) * np.sin(2 * beta)
                      + (23 * e2**2 / 360 + 251 * e2**3 / 3780) * np.sin(4 * beta)
                      + 761 * e2**3 / 45360 * np.sin(6 * beta))


def _size_token(value):
    """0.25 -> '0p25', 1.0 -> '1p0', 12.5 -> '12p5'."""
    text = f'{value:.10f}'.rstrip('0')
    text = text + '0' if text.endswith('.') else text
    return text.replace('.', 'p')


class Grid:
    """What both grid types share.

    A subclass sets ``kind``, ``name`` (the store token), ``size`` (a cell's
    side in its plane), ``shape`` (rows, cols), ``lat_edges`` (rows + 1, row
    order, north first), ``lon_edges`` (cols + 1), ``row_lat``, ``col_lon``,
    ``clamp_rows``, and the methods ``plane`` and ``row_area_km2``.
    """

    def __repr__(self):
        return self.name

    @property
    def n_cells(self):
        return self.shape[0] * self.shape[1]

    @property
    def cell_area_plane(self):
        """A cell's area in its plane: degrees² on lat/lon, m² on EASE."""
        return self.size**2

    def cell_area_km2(self, cells):
        """Each flat cell's true area in km²."""
        return self.row_area_km2()[np.asarray(cells) // self.shape[1]]


class LatLonGrid(Grid):
    """A regular global lat/lon grid of square cells ``resolution`` degrees on a side.

    Row 0 is the northernmost, column 0 starts at 180°W. Its plane is
    (lon + 180, 90 - lat) in degrees.

    Raises:
        ValueError: If the cell size does not divide 180.
    """
    kind = 'latlon'
    clamp_rows = True

    def __init__(self, resolution):
        n_lat = round(180 / resolution)
        if abs(n_lat * resolution - 180) > 1e-9:
            raise ValueError(f'lat/lon cell size must divide 180, got {resolution}')
        self.resolution = self.size = float(resolution)
        token = _size_token(self.size)
        self.name = f'latlon_{token}x{token}'
        self.shape = (n_lat, 2 * n_lat)
        self.lat_edges = 90 - self.size * np.arange(n_lat + 1)
        self.lon_edges = -180 + self.size * np.arange(2 * n_lat + 1)
        self.row_lat = 90 - self.size * (np.arange(n_lat) + 0.5)
        self.col_lon = -180 + self.size * (np.arange(2 * n_lat) + 0.5)

    def plane(self, lat, lon):
        return lon + 180, 90 - lat

    @functools.cache
    def row_area_km2(self):
        """Area of a cell in each row, on a sphere of radius ``EARTH_KM`` (Section 3)."""
        north, south = np.radians(self.lat_edges[:-1]), np.radians(self.lat_edges[1:])
        return EARTH_KM**2 * np.radians(self.size) * (np.sin(north) - np.sin(south))


class Ease2Grid(Grid):
    """An EASE-Grid 2.0 global grid (EPSG:6933), centred on (0°, 0°).

    Row 0 is the northernmost and column 0 starts at 180°W, so the flat index
    is NSIDC's. Its plane is (x - x_min, y_max - y) in metres.

    Args:
        nsidc_name (str): A key of ``EASE2_GLOBAL`` ('M25km').
    """
    kind = 'ease2'
    clamp_rows = False

    def __init__(self, nsidc_name):
        if nsidc_name not in EASE2_GLOBAL:
            raise ValueError(f'EASE-Grid 2.0 global grid must be one of {list(EASE2_GLOBAL)}, got {nsidc_name!r}')
        size, n_cols, n_rows = EASE2_GLOBAL[nsidc_name]
        self.nsidc_name = nsidc_name
        self.name = f'ease2_{nsidc_name.lower().replace(".", "p")}'
        self.size, self.shape = float(size), (n_rows, n_cols)
        self.x_min, self.y_max = -n_cols * self.size / 2, n_rows * self.size / 2
        metres_per_degree = WGS84_A * _EASE2_K0 * np.pi / 180
        self.x_centres = self.x_min + self.size * (np.arange(n_cols) + 0.5)
        self.y_centres = self.y_max - self.size * (np.arange(n_rows) + 0.5)
        self.lat_edges = ease2_lat(self.y_max - self.size * np.arange(n_rows + 1))
        self.lon_edges = (self.x_min + self.size * np.arange(n_cols + 1)) / metres_per_degree
        self.row_lat = ease2_lat(self.y_centres)
        self.col_lon = self.x_centres / metres_per_degree

    def plane(self, lat, lon):
        x, y = ease2_xy(lat, lon)
        return x - self.x_min, self.y_max - y

    @functools.cache
    def row_area_km2(self):
        """Every cell's area, exact on the ellipsoid: the grid is equal-area."""
        return np.full(self.shape[0], (self.size / 1000) ** 2)


def from_spec(spec):
    """A grid from its config entry.

    Args:
        spec (dict): ``{type: latlon, resolution: 0.25}`` or ``{type: ease2, name: M25km}``.

    Returns:
        Grid: The grid.
    """
    kind = spec.get('type')
    if kind == 'latlon':
        return LatLonGrid(float(spec['resolution']))
    if kind == 'ease2':
        return Ease2Grid(str(spec['name']))
    raise ValueError(f'grid type must be latlon or ease2, got {kind!r}')
