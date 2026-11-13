"""Read one UTC day of gridding inputs from a product's finalized L2 stores.

Gridding talks to L2 only through its stores (user decision 2026-11-10):
their ``obs`` axis, granule index and attributes, at a tag. Every store is
opened read-only at ``l2.tag``, or at its own entry in ``l2.store_tags``
where stores of one product were finalized at different times (AIRS v1's
four footprint stores, 2026-11-13). The snapshot the tag names is recorded
in every gridded store, so a grid says exactly which L2 state it was built
from (``provenance``).

A day is selected by observation time, never by granule: TROPESS granules
are not UTC days (``docs/products/tropess.md`` R27). The granule index gives
each granule's earliest and latest time, so the obs range that can hold the
day is the span of the granules overlapping it; rows are then kept by time.
That holds whether or not ``time`` is monotonic along obs.

Reads are chunk-aligned blocks of ``read_block_obs`` (a multiple of the
geolocation chunk), and each block reads time first, the selection inputs
only if rows remain, and the gridding inputs and corners only for rows that
pass, so a strict selection skips most of the bytes.

Two readers, by the config's ``method``:

- ``read_day`` (``column``, TROPOMI): δD, its σ and the H2O column are L2
  variables, and the footprint is the L2 corners;
- ``read_profile_day`` (``profile``, AIRS): the profiles on the L2 ``level``
  axis, from which ``utils/profiles.py`` derives what is gridded, and the
  footprint polygons drawn by a model (``airs_fov``) from published
  geometry fields. A day there is tens of thousands of rows, so it is read
  whole.
"""
import functools
import re

import icechunk  # type: ignore
import numpy as np
import zarr  # type: ignore

from utils import airs_fov
from utils.config import GEOLOCATION, l2_store_path

# icechunk warns that local storage is unsafe for concurrent commits; this only reads
icechunk.set_logs_filter('error')

UNIT_MS = {'milliseconds': 1, 'seconds': 1000, 'microseconds': 1e-3, 'nanoseconds': 1e-6}
TIME_UNITS_RE = re.compile(r'^(?P<unit>\w+) since 1900-01-01$')
MS_PER_DAY = 86_400_000
INDEX = ('granule_id', 'granule_obs_start', 'granule_obs_count', 'granule_time_start', 'granule_time_end')


class L2:
    """A product's L2 stores at one tag, opened lazily and read only.

    Args:
        settings (dict): The config (``l2`` block).
    """

    def __init__(self, settings):
        self.settings = settings
        self.tag = settings['l2']['tag']
        self.store_tags = dict(settings['l2'].get('store_tags') or {})

    def tag_of(self, store):
        """The tag one store is read at."""
        return self.store_tags.get(store, self.tag)

    @functools.cache
    def repository(self, store):
        path = l2_store_path(self.settings, store)
        return icechunk.Repository.open(icechunk.local_filesystem_storage(path))

    @functools.cache
    def group(self, store):
        """The store's root group at the tag (fails plainly if the tag is absent)."""
        repository = self.repository(store)
        tag = self.tag_of(store)
        if tag not in repository.list_tags():
            raise RuntimeError(f'L2 store {store!r} has no tag {tag!r} '
                               f'({l2_store_path(self.settings, store)})')
        return zarr.open_group(repository.readonly_session(tag=tag).store, mode='r')

    def array(self, store, name=None):
        return self.group(store)[name or store]

    def snapshot(self, store):
        """The snapshot id the tag names in one store."""
        return self.repository(store).lookup_tag(self.tag_of(store))

    def provenance(self, stores):
        """``store=snapshot`` for each store read, for the gridded stores' attributes."""
        return {store: self.snapshot(store) for store in stores}

    def fill(self, store):
        """The integer ``_FillValue`` of a store's variable, or None for floats (NaN)."""
        array = self.array(store)
        return array.attrs.get('_FillValue') if np.issubdtype(array.dtype, np.integer) else None

    def units(self, store):
        return self.array(store).attrs.get('units')

    @functools.cache
    def time_ms(self):
        """Milliseconds per unit of the stored ``time`` (L2 time units are per product)."""
        match = TIME_UNITS_RE.match(self.array(GEOLOCATION, 'time').attrs['units'])
        if not match or match['unit'] not in UNIT_MS:
            raise ValueError(f'unexpected L2 time units {self.array(GEOLOCATION, "time").attrs["units"]!r}')
        return UNIT_MS[match['unit']]

    @functools.cache
    def index(self):
        """The granule index of observed granules: arrays of start, count, time_start, time_end (stored units)."""
        geo = self.group(GEOLOCATION)
        values = {name: geo[name][:] for name in INDEX}
        observed = values['granule_obs_count'] > 0
        return {name: array[observed] for name, array in values.items()}

    def record_days(self):
        """First and last day (day numbers since 1900-01-01) holding an observation."""
        index = self.index()
        per_day = MS_PER_DAY / self.time_ms()
        return int(index['granule_time_start'].min() // per_day), int(index['granule_time_end'].max() // per_day)

    def day_window(self, day):
        """The half-open obs range that can hold a day's observations, and the day in stored time units."""
        per_day = MS_PER_DAY / self.time_ms()
        start, end = day * per_day, (day + 1) * per_day
        index = self.index()
        hits = (index['granule_time_end'] >= start) & (index['granule_time_start'] < end)
        if not hits.any():
            return (0, 0), (start, end)
        first = index['granule_obs_start'][hits]
        stop = first + index['granule_obs_count'][hits]
        return (int(first.min()), int(stop.max())), (start, end)


def read_day(l2, day, settings, product):
    """The day's footprints that pass the selection, with every gridding input.

    Args:
        l2 (L2): The stores.
        day (int): Day number since 1900-01-01.
        settings (dict): The config (``inputs``, ``selection``, ``read_block_obs``).
        product (module): ``products/<source>.py``: ``selection_stores`` and ``select``.

    Returns:
        tuple: ``(values, counts)``. ``values``: ``lat_corners``,
            ``lon_corners`` and each of the config's ``inputs`` (by input
            name: 'delta_d', 'delta_d_uncertainty', 'weight'), for the rows
            kept. ``counts``: rows in the day, rows passing the quality
            selection, rows over a threshold, rows missing an input.
    """
    inputs = settings['inputs']
    selection = settings['selection']
    thresholds = selection.get('thresholds') or {}
    quality_stores = product.selection_stores(selection)
    block = int(settings.get('read_block_obs', 2 * l2.array(GEOLOCATION, 'time').chunks[0]))
    (first, stop), (start, end) = l2.day_window(day)
    parts = []
    counts = {'rows': 0, 'quality': 0, 'over_threshold': 0, 'missing_input': 0}
    position = first
    while position < stop:
        window = slice(position, min((position // block + 1) * block, stop))
        position = window.stop
        time = l2.array(GEOLOCATION, 'time')[window]
        keep = (time >= start) & (time < end)
        counts['rows'] += int(keep.sum())
        if not keep.any():
            continue
        values = {store: l2.array(store)[window] for store in quality_stores}
        keep &= product.select(values, {store: l2.fill(store) for store in quality_stores}, selection)
        counts['quality'] += int(keep.sum())
        if not keep.any():
            continue
        rows = np.flatnonzero(keep)
        kept = {name: (values[store] if store in values else l2.array(store)[window])[rows]
                for name, store in inputs.items() if name != 'footprint'}
        over = np.zeros(rows.size, dtype=bool)
        for store, bounds in thresholds.items():
            name = _input_of(inputs, store)
            if name is not None:
                data = kept[name]
            elif store in values:
                data = values[store][rows]
            else:
                data = l2.array(store)[window][rows]
            with np.errstate(invalid='ignore'):
                if 'max' in bounds:
                    over |= data > bounds['max']
                if 'min' in bounds:
                    over |= data < bounds['min']
        missing = ~np.logical_and.reduce([np.isfinite(array) for array in kept.values()])
        counts['over_threshold'] += int((over & ~missing).sum())
        counts['missing_input'] += int(missing.sum())
        good = ~over & ~missing
        if not good.any():
            continue
        rows = rows[good]
        kept = {name: array[good] for name, array in kept.items()}
        corners = slice(window.start + int(rows.min()), window.start + int(rows.max()) + 1)
        kept['lat_corners'] = l2.array(GEOLOCATION, 'lat_corners')[corners][rows - (corners.start - window.start)]
        kept['lon_corners'] = l2.array(GEOLOCATION, 'lon_corners')[corners][rows - (corners.start - window.start)]
        parts.append(kept)
    names = ['lat_corners', 'lon_corners', *(name for name in inputs if name != 'footprint')]
    if not parts:
        empty = {name: np.empty(0) for name in names}
        empty['lat_corners'] = empty['lon_corners'] = np.empty((0, 4))
        return empty, counts
    return {name: np.concatenate([part[name] for part in parts]) for name in names}, counts


def _input_of(inputs, store):
    """The input name ('weight') whose L2 variable is ``store``, or None."""
    return next((name for name, value in inputs.items() if value == store), None)


# ------------------------------------------------------- the profile method

PROFILE_INPUTS = ('ratio', 'h2o', 'pressure', 'apriori')


class AirsPhases:
    """The orbit phase of each AIRS day (L2 granule), for the ``airs_fov`` footprints.

    One fit per granule from its every target (``airs_fov.fit_phase``),
    whatever the selection keeps. A granule without a sound fit takes the
    nearest sound one's, carried over by the scan count (``airs_fov``,
    "Days with too few targets").

    Args:
        l2 (L2): The stores.
        stores (dict): The config's ``footprint`` block: the L2 variables
            behind ``granule``, ``scanline``, ``pixel`` and ``view_angle``.
    """

    def __init__(self, l2, stores):
        self.l2, self.stores = l2, stores
        index = l2.index()
        ids = [str(value) for value in index['granule_id']]
        # a TROPESS granule is one day's files, and its id the date (YYYYMMDD)
        self.days = np.array([f'{value[:4]}-{value[4:6]}-{value[6:8]}' for value in ids],
                             dtype='datetime64[D]').astype('int64')
        self.starts, self.counts = index['granule_obs_start'], index['granule_obs_count']

    def granule_of(self, obs):
        """Each observation's granule, as a position in the index of observed granules."""
        return np.searchsorted(self.starts, obs, side='right') - 1

    def geometry(self, rows):
        """Signed scan angle and scan number of the observations ``rows`` (a slice or indices)."""
        read = {name: self.l2.array(store)[rows] for name, store in self.stores.items()}
        return (airs_fov.scan_angle(read['view_angle'], read['pixel']),
                airs_fov.scan_number(read['granule'], read['scanline']))

    @functools.cache
    def own(self, k):
        """Granule ``k``'s own fit, or None where it has too few targets to fit at all."""
        if self.counts[k] < 3:
            return None
        rows = slice(int(self.starts[k]), int(self.starts[k] + self.counts[k]))
        scan, n = self.geometry(rows)
        return airs_fov.fit_phase(n, self.l2.array(GEOLOCATION, 'lat')[rows].astype('float64'), scan)

    @functools.cache
    def resolve(self, k):
        """The fit granule ``k``'s footprints use, and how many days ahead of that fit ``k`` is.

        Raises:
            RuntimeError: If no granule within ``MAX_CARRY_DAYS`` has a sound fit.
        """
        if airs_fov.is_sound(self.own(k)):
            return self.own(k), 0
        # the other days by distance in time, the earlier first on a tie
        gap = np.abs(self.days - self.days[k])
        for j in np.argsort(gap, kind='stable'):
            if j == k or gap[j] > airs_fov.MAX_CARRY_DAYS:
                continue
            if airs_fov.is_sound(self.own(int(j))):
                return self.own(int(j)), int(self.days[k] - self.days[j])
        raise RuntimeError(f'AIRS day {self.l2.index()["granule_id"][k]}: no day within '
                           f'{airs_fov.MAX_CARRY_DAYS} days has enough targets to fit the orbit phase')

    def polygons(self, obs, lat, lon):
        """The footprint polygons of observations ``obs`` (sorted indices): ``(n, VERTICES)`` lat and lon."""
        plat = np.empty((obs.size, airs_fov.VERTICES))
        plon = np.empty((obs.size, airs_fov.VERTICES))
        if not obs.size:
            return plat, plon
        window = slice(int(obs.min()), int(obs.max()) + 1)
        scan, n = self.geometry(window)
        scan, n = scan[obs - window.start], n[obs - window.start]
        granule = self.granule_of(obs)
        for k in np.unique(granule):
            member = granule == k
            fit, days_ahead = self.resolve(int(k))
            plat[member], plon[member] = airs_fov.polygons(lat[member], lon[member], scan[member],
                                                           airs_fov.phase(fit, n[member], days_ahead), fit['k'])
        return plat, plon


def footprint_stores(settings):
    """The L2 variables a footprint model reads beyond geolocation (the config's ``footprint`` block)."""
    return list((settings.get('footprint') or {}).values())


def read_profile_day(l2, day, settings, product, phases):
    """The day's retrievals that pass the selection, with their profiles and footprint polygons.

    Args:
        l2 (L2): The stores.
        day (int): Day number since 1900-01-01.
        settings (dict): The config (``inputs``, ``selection``).
        product (module): ``products/<source>.py``: ``selection_stores`` and ``select``.
        phases (AirsPhases): The footprint model's orbit phases.

    Returns:
        tuple: ``(values, counts)``. ``values``: ``pressure``, ``ratio``,
            ``h2o``, ``apriori`` and ``kernel`` (the kernel's diagonal), each
            ``(n, slots)`` float64, and ``lat_corners``, ``lon_corners``
            ``(n, vertices)``. ``counts``: rows in the day and rows passing
            the quality selection; nothing is dropped here for a missing
            input (``utils.profiles.derive`` decides what each group can use).
    """
    inputs = settings['inputs']
    selection = settings['selection']
    if selection.get('thresholds'):
        raise ValueError('the profile method takes no selection thresholds; put the rule in the quality level')
    quality_stores = product.selection_stores(selection)
    (first, stop), (start, end) = l2.day_window(day)
    counts = {'rows': 0, 'quality': 0, 'over_threshold': 0, 'missing_input': 0}
    window = slice(first, stop)
    rows = np.empty(0, dtype='int64')
    if stop > first:
        time = l2.array(GEOLOCATION, 'time')[window]
        keep = (time >= start) & (time < end)
        counts['rows'] = int(keep.sum())
        if keep.any():
            values = {store: l2.array(store)[window] for store in quality_stores}
            keep &= product.select(values, {store: l2.fill(store) for store in quality_stores}, selection)
            counts['quality'] = int(keep.sum())
        rows = np.flatnonzero(keep)
    out = {}
    slots = l2.array(inputs['pressure']).shape[1]
    if not rows.size:
        out = {name: np.empty((0, slots)) for name in (*PROFILE_INPUTS, 'kernel')}
        out['lat_corners'] = out['lon_corners'] = np.empty((0, airs_fov.VERTICES))
        return out, counts
    # only the span of the kept rows is read (a day is the tail of one granule and most of the next)
    span = slice(first + int(rows.min()), first + int(rows.max()) + 1)
    inside = rows - (span.start - first)
    for name in PROFILE_INPUTS:
        out[name] = l2.array(inputs[name])[span][inside].astype('float64')
    kernel = l2.array(inputs['kernel'])
    step = kernel.chunks[0]
    diagonal = np.empty((rows.size, slots))
    # the kernel is (obs, level, level_2): one chunk of obs at a time, keeping only its diagonal
    for edge in range(span.start - span.start % step, span.stop, step):
        block = slice(max(edge, span.start), min(edge + step, span.stop))
        member = (inside >= block.start - span.start) & (inside < block.stop - span.start)
        if member.any():
            taken = kernel[block][inside[member] - (block.start - span.start)]
            diagonal[member] = np.einsum('nii->ni', taken)
    out['kernel'] = diagonal
    lat = l2.array(GEOLOCATION, 'lat')[span][inside].astype('float64')
    lon = l2.array(GEOLOCATION, 'lon')[span][inside].astype('float64')
    out['lat_corners'], out['lon_corners'] = phases.polygons(rows + first, lat, lon)
    return out, counts
