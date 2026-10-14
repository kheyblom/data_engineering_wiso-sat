"""Reader for the IUP FOCAL GOSAT Level 2 product (v3.0.1).

FOCAL publishes two flat netCDF files per day, one per retrieval:

```
<raw>/IUP-GHG-L2-DED-GOSAT-FOCAL-<YYYY>-v3.0.1/v3.0.1/<YYYY>/IUP-GHG-L2-DED-GOSAT-FOCAL-<YYYYMMDD>-v3.0.1.nc
<raw>/IUP-GHG-L2-H2O-GOSAT-FOCAL-<YYYY>-v3.0.1/v3.0.1/<YYYY>/IUP-GHG-L2-H2O-GOSAT-FOCAL-<YYYYMMDD>-v3.0.1.nc
```

**One granule is one day, both files, merged** (decided 2026-10-14). The two
files hold separately quality-filtered sets of the same instrument's soundings,
and they overlap only partly (in 13 sampled days, 44% of DED soundings were in
the H2O file). So the day's obs axis is every distinct sounding of either
file, in time order:

- **Matching.** A sounding is identified by its time, latitude and longitude,
  compared bit for bit. In the sampled days this matched exactly the pairs that
  FOCAL's pass, scene and sounding numbers match. All 16 fields the two files
  share were identical on every matched sounding. The merge fails if a shared
  field ever disagrees.
- **Order.** Both files are time ordered, and the merge keeps each file's own
  order; it fails if it cannot.
- **Absent values.** A variable from one file is absent at the soundings only
  the other file has. The reader marks those, and shared code fills them (NaN,
  or the config's ``absent_fill_values`` for an integer).

Format facts:
- **Flat files.** A source is named by its variable name.
- **Observation dimension** is ``sounding_dim``.
- **Time** is float64 seconds since 1970-01-01. The values sit on no decimal
  grid coarser than a nanosecond, so ``decode_time`` returns exact
  datetime64[ns].
- **Version** is the root ``product_version`` attribute (``v3.0.1``).
- **GOSAT-2** files have the same format, with ``GOSAT2`` in the file name. The
  pattern below accepts both, so the GOSAT-2 configs can reuse this reader.

The build reads with netCDF4. The verifier reads each file on its own with
h5py and places its soundings by matching ``MATCH_SOURCES`` against the
stored geolocation, so it checks the merge without repeating it.
"""

from __future__ import annotations

import datetime
import os
import re

import netCDF4
import numpy as np

from utils.granules import Granule, GranuleData, SourceArray, decode_text, squeeze_dims

YEAR_DIR_RE = re.compile(
    r'^IUP-GHG-L2-(?P<kind>DED|H2O)-GOSAT-FOCAL-(?P<year>\d{4})-v(?P<version>[\d.]+)$'
)
FILE_RE = re.compile(
    r'^IUP-GHG-L2-(?P<kind>DED|H2O)-GOSAT2?-FOCAL-(?P<date>\d{8})-v(?P<version>[\d.]+)\.nc$'
)

# the files of a day's granule, in the order they are merged
KINDS = ('DED', 'H2O')

OBSERVATION_DIM = 'sounding_dim'
DIMENSION_RENAMES = {'level_dim': 'level', 'layer_dim': 'layer'}

VERSION_ATTR = 'product_version'

# what identifies a sounding across the day's two files
MATCH_SOURCES = ('time', 'latitude', 'longitude')


def list_granules(raw_root, expected_empty=()):
    """Every day with FOCAL files under the raw root, in date order.

    Args:
        raw_root (str): The product directory, e.g. ``.../raw/GOSAT``.
        expected_empty (Iterable): Unused: FOCAL has no empty granule
            directories, so none may be declared.

    Returns:
        list: :class:`Granule` per day, with paths in ``KINDS`` order.

    Raises:
        FileNotFoundError: If the root does not exist.
        ValueError: If a day has one kind of file but not the other. Merging
            just the one would turn a missing download into absent values.
    """
    if not os.path.isdir(raw_root):
        raise FileNotFoundError(f'no raw data directory at {raw_root}')
    if list(expected_empty):
        raise ValueError('GOSAT has no empty granules; expected_empty_granules must be unset')

    days = {}
    for entry in sorted(os.listdir(raw_root)):
        match = YEAR_DIR_RE.match(entry)
        if match is None:
            continue
        version_dir = os.path.join(raw_root, entry, f'v{match["version"]}')
        if not os.path.isdir(version_dir):
            continue
        year_dir = os.path.join(version_dir, match['year'])
        if not os.path.isdir(year_dir):
            continue
        for name in sorted(os.listdir(year_dir)):
            found = FILE_RE.match(name)
            # the GOSAT-2 2019 folder also holds L3 files, which this skips
            if found is None or found['kind'] != match['kind']:
                continue
            day = datetime.datetime.strptime(found['date'], '%Y%m%d').date()
            files = days.setdefault(day, {})
            if found['kind'] in files:
                raise ValueError(f'two {found["kind"]} files for {day}')
            files[found['kind']] = os.path.join(year_dir, name)

    unpaired = sorted(day for day, files in days.items() if set(files) != set(KINDS))
    if unpaired:
        raise ValueError(
            f'{len(unpaired)} days lack a DED or H2O file: {[str(day) for day in unpaired[:10]]}'
        )
    return [
        Granule(
            id=day.strftime('%Y%m%d'), day=day,
            paths=tuple(files[kind] for kind in KINDS),
        )
        for day, files in sorted(days.items())
    ]


def decode_time(raw):
    """Decode float64 seconds since 1970-01-01 to exact datetime64[ns].

    The whole seconds and the fraction are split before scaling. That keeps
    the arithmetic exact: a float64 near 1.3e9 resolves 2**-22 s, so the
    fraction times 1e9 is an exact product, which then rounds to the nearest
    nanosecond.

    Args:
        raw (numpy.ndarray): float64 seconds since 1970-01-01.

    Returns:
        numpy.ndarray: datetime64[ns].

    Raises:
        ValueError: If any time does not survive the round trip, which would
            mean nanoseconds do not hold it exactly.
    """
    raw = np.asarray(raw, dtype='float64')
    whole = np.floor(raw)
    nanoseconds = np.round((raw - whole) * 1e9).astype('int64')
    back = whole + nanoseconds / 1e9
    if not np.array_equal(back, raw):
        raise ValueError(
            f'{int((back != raw).sum())} times are not held exactly in nanoseconds'
        )
    total = whole.astype('int64') * 1_000_000_000 + nanoseconds
    return total.astype('datetime64[ns]')


def read_attrs(item):
    """An item's attributes, byte strings decoded.

    Args:
        item: A netCDF4 Dataset or Variable.

    Returns:
        dict: Attribute name -> value.
    """
    return {name: decode_text(item.getncattr(name)) for name in item.ncattrs()}


def merge_positions(handles):
    """Where each file's soundings sit on the day's merged obs axis.

    Args:
        handles (list): Open netCDF4 datasets, in ``KINDS`` order.

    Returns:
        tuple: The merged observation count, and per file an int array of
            positions.

    Raises:
        ValueError: If a file repeats a sounding, or the merge cannot keep a
            file's own order.
    """
    keys = []
    for handle in handles:
        record = np.empty(
            handle.dimensions[OBSERVATION_DIM].size,
            dtype=[('time', 'f8'), ('latitude', 'u4'), ('longitude', 'u4')],
        )
        record['time'] = handle['time'][...]
        # bit patterns, so a sounding matches only the identical position
        record['latitude'] = handle['latitude'][...].view('u4')
        record['longitude'] = handle['longitude'][...].view('u4')
        if np.unique(record).size != record.size:
            raise ValueError(f'{handle.filepath()} repeats a sounding')
        keys.append(record)

    # sorted lexicographically, time first: the merged axis is in time order
    merged, inverse = np.unique(np.concatenate(keys), return_inverse=True)
    positions, offset = [], 0
    for record in keys:
        placed = inverse[offset:offset + record.size]
        offset += record.size
        if (np.diff(placed) <= 0).any():
            raise ValueError('the merge would reorder soundings within a file')
        positions.append(placed)
    return merged.size, positions


def read_granule(granule, sources, time_source):
    """Read one day's files and merge them onto one obs axis, raw.

    Args:
        granule (Granule): The day, from ``list_granules``.
        sources (Sequence): Variable names to read.
        time_source (str): The time variable, returned decoded.

    Returns:
        GranuleData: The day's arrays on the merged obs axis. A variable is
            marked absent where its file lacks the sounding.

    Raises:
        KeyError: If no file of the day holds a source.
        ValueError: If the files declare different versions, or disagree on a
            variable they share at a shared sounding.
    """
    handles = [netCDF4.Dataset(path, 'r') for path in granule.paths]
    try:
        for handle in handles:
            # masking off: only the config's declared fill counts as missing
            handle.set_auto_mask(False)
        versions = {str(handle.getncattr(VERSION_ATTR)) for handle in handles}
        if len(versions) != 1:
            raise ValueError(f'the files of {granule.id} declare versions {sorted(versions)}')
        n_obs, positions = merge_positions(handles)

        arrays = {}
        for source in sources:
            holders = [i for i, handle in enumerate(handles) if source in handle.variables]
            if not holders:
                raise KeyError(f'no file of {granule.id} holds {source}')
            values, absent, attrs, dims, note = None, np.ones(n_obs, dtype=bool), None, None, None
            for i in holders:
                variable = handles[i][source]
                dims_i, raw, note_i = squeeze_dims(
                    variable[...], variable.dimensions, OBSERVATION_DIM, DIMENSION_RENAMES
                )
                if source == time_source:
                    raw = decode_time(raw)
                if values is None:
                    values = np.zeros((n_obs,) + raw.shape[1:], dtype=raw.dtype)
                    attrs, dims, note = read_attrs(variable), dims_i, note_i
                placed = positions[i]
                # a sounding both files hold must carry the same value in each
                overlap = ~absent[placed]
                if overlap.any():
                    before = values[placed[overlap]]
                    after = raw[overlap]
                    if before.tobytes() != after.tobytes():
                        raise ValueError(
                            f'{source} differs between the files of {granule.id} at a '
                            f'sounding both hold'
                        )
                values[placed] = raw
                absent[placed] = False
            in_files = ' and '.join(KINDS[i] for i in holders)
            arrays[source] = SourceArray(
                dims=dims,
                values=values,
                attrs=attrs,
                dimension_note=f'{note}; the day\'s DED and H2O soundings merged '
                f'onto one obs axis (this variable from the {in_files} file)',
                absent=absent if absent.any() else None,
            )
        return GranuleData(
            granule=granule,
            n_obs=n_obs,
            version=versions.pop(),
            attrs=read_attrs(handles[0]),
            arrays=arrays,
        )
    finally:
        for handle in handles:
            handle.close()


def check_granule(handle):
    """Format invariants the verifier confirms on every file.

    Args:
        handle (h5py.File): An open file.

    Returns:
        list: Problems found: here, only time running backwards within the
            file, which the merge's order guarantee depends on.
    """
    time = handle['time'][...]
    if (np.diff(time) < 0).any():
        return ['time decreases within the file']
    return []
