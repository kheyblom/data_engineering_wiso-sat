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
"""
import functools
import re

import icechunk  # type: ignore
import numpy as np
import zarr  # type: ignore

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
