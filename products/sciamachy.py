"""Reader for the SRON SCIAMACHY H2O/HDO Level 2 product (SICOR, processor 8.1).

One granule is one orbit file, filed by the month its orbit starts in:

```
<raw>/<YYYYMM>/sci_l2_h2o_hdo_<product_version>_<orbit:05d>.nc
```

The format is SRON's, as TROPOMI's (same groups, ``nobs``, broken-down time,
no ``_FillValue``), so the time decoding, attribute reading and open probe are
TROPOMI's own functions. What differs, measured by the audit of every file on
2026-10-22 (``docs/products/sciamachy.md``; TESTING.md finding 13):

- **Filed by month, no date in the name.** Granules are ordered by orbit
  number, never by folder: 65 orbits hold times outside their folder's
  month (S11). Coverage is checked by month (``COVERAGE_FREQUENCY``), since a
  day would need every file opened to list the tree.
- **Hidden transfer leftovers** (``.ArchiveServiceTemp.sb-*``, duplicates of
  month-folder files, some truncated; S5) and a ``.DS_Store`` sit in the raw
  root, so only ``YYYYMM`` folders are walked.
- **No shells or partial files**: every row of every file has time, lat and
  lon. The shared row rule is still applied, as for every product.
- **The millisecond field reaches 1000** (the next whole second) in 759 files
  (S10); ``decode_time``, through pandas, carries it.
- **Two defects repeat observations** (S8, S9), so the config declares the
  rows to leave out and this reader confirms each declaration before leaving
  them out (``DeclaredRows`` in ``utils/granules.py``; user decision
  2026-10-22).
- **``pixel_id`` is the source row + 1**, which ``check_granule`` confirms on
  every file (P3c). Declared rows are left out only after the last row kept,
  so the granule index still gives every observation's source row and no
  index store is needed.

The build reads with netCDF4 and the verifier with h5py, as for TROPOMI.
"""

from __future__ import annotations

import datetime
import os
import re

import netCDF4
import numpy as np

from products.tropomi import decode_time, opens, read_attrs
from utils.granules import (
    Granule, GranuleData, SourceArray, declared_mask, leaked_rows, observed_rows, same_bits,
    squeeze_dims,
)

FILE_RE = re.compile(r'^sci_l2_h2o_hdo_(?P<product_version>\d{4})_(?P<orbit>\d{5})\.nc$')
MONTH_RE = re.compile(r'^(?P<year>\d{4})(?P<month>\d{2})$')

# as TROPOMI: nlayer -> layer, nlevel -> level, ncorner -> corner by the
# leading-'n' rule
OBSERVATION_DIM = 'nobs'
DIMENSION_RENAMES = {}
# level 0 is 0 Pa and the last level is the surface pressure (checked
# 2026-10-22, orbit 45263)
VERTICAL_ORDER = 'top_first'

VERSION_ATTR = 'version'

# the tree is filed by month (utils/granules.py COVERAGE_KEYS)
COVERAGE_FREQUENCY = 'MS'

# this reader applies the config's declared_rows_left_out
DECLARED_ROWS = True


def list_granules(raw_root, expected_empty=(), expected_unreadable=()):
    """Every orbit file in the month folders, in orbit order.

    Orbit order is time order. Only ``YYYYMM`` folders are walked, so the
    hidden transfer leftovers in the raw root are never seen; no file is
    opened except a declared-unreadable one, to confirm it still fails.

    Args:
        raw_root (str): The ``HDO_SICORv10`` directory.
        expected_empty (Iterable): Unused; a month folder holds files, not
            orbit directories. Accepted for the shared interface, and must
            be empty.
        expected_unreadable (Iterable): Orbit numbers whose files are known to
            be corrupt (``expected_unreadable_granules``); none so far.

    Returns:
        list: :class:`Granule` per orbit file, sorted by orbit number. Its
            ``day`` is the first of its folder's month.

    Raises:
        FileNotFoundError: If the root does not exist.
        ValueError: If a month folder holds a file that is not an orbit file,
            an orbit appears twice, an empty granule is declared, or a file
            declared unreadable opens or is not there.
    """
    if list(expected_empty):
        raise ValueError('expected_empty_granules does not apply to SCIAMACHY: it has no orbit directories')
    expected_unreadable = {int(orbit) for orbit in expected_unreadable}
    found_unreadable = set()
    if not os.path.isdir(raw_root):
        raise FileNotFoundError(f'no raw data directory at {raw_root}')

    granules, problems = [], []
    for month in sorted(entry for entry in os.listdir(raw_root) if MONTH_RE.match(entry)):
        match = MONTH_RE.match(month)
        day = datetime.date(int(match['year']), int(match['month']), 1)
        month_dir = os.path.join(raw_root, month)
        for name in sorted(os.listdir(month_dir)):
            found = FILE_RE.match(name)
            if not found:
                problems.append(f'{month_dir} holds {name}, not an orbit file')
                continue
            path = os.path.join(month_dir, name)
            if int(found['orbit']) in expected_unreadable:
                found_unreadable.add(int(found['orbit']))
                if opens(path):
                    problems.append(f'{path} is declared unreadable but opens')
                continue
            granules.append(Granule(id=found['orbit'], day=day, paths=(path,)))
    stale = sorted(expected_unreadable - found_unreadable)
    if stale:
        problems.append(f'orbits declared unreadable have no file: {stale}')
    if problems:
        raise ValueError(f'{len(problems)} problems in the raw tree: {problems[:10]}')
    return sorted(granules, key=lambda granule: int(granule.id))


def check_declared(granule, declared, location, arrays):
    """Confirm a granule's declared rows are what the config says they are.

    Args:
        granule (Granule): The granule.
        declared (DeclaredRows): Its declaration.
        location (dict): Source path -> raw array, every row, for time, lat
            and lon.
        arrays (dict): Source path -> raw array, every row, for every other
            source read.

    Raises:
        ValueError: If a repeat differs from its block, or an overlap does not
            have the other granule's time, latitude and longitude exactly.
    """
    rows = slice(declared.start, declared.stop)
    if declared.repeat_of is not None:
        first, last = declared.repeat_of
        differ = []
        for source, values in (location | arrays).items():
            if source in declared.repeat_except:
                continue
            block = values[first:last]
            copies = values[rows].reshape((-1,) + block.shape)
            if not all(same_bits(copy, block) for copy in copies):
                differ.append(source)
        if differ:
            raise ValueError(
                f'orbit {granule.id}: declared rows {declared.start}-{declared.stop - 1} are '
                f'not copies of rows {first}-{last - 1} in {differ}'
            )
    if declared.location_of is not None:
        other, first, last, path = declared.location_of
        with netCDF4.Dataset(path, 'r') as handle:
            handle.set_auto_mask(False)
            differ = []
            for source, values in location.items():
                group, name = source.split('/')
                theirs = np.asarray(handle[group][name][first:last])
                if not same_bits(values[rows], theirs):
                    differ.append(source)
        if differ:
            raise ValueError(
                f'orbit {granule.id}: declared rows {declared.start}-{declared.stop - 1} do '
                f'not have the {differ} of orbit {other} rows {first}-{last - 1}'
            )


def read_granule(granule, sources, time_source, rule):
    """Read the named variables of one orbit file, raw.

    A top-level function of picklable arguments, so the build can run it in a
    process pool: HDF5 is not safe to call from several threads.

    Args:
        granule (Granule): The orbit, from ``list_granules``.
        sources (Sequence): Source paths to read, ``<group>/<variable>``.
        time_source (str): The source path of the time coordinate, which is
            returned decoded.
        rule (RowRule): Which rows are observations, and the declared rows.

    Returns:
        GranuleData: The orbit's observations on the store's dimensions,
            values exactly as stored except for the decoded time.

    Raises:
        KeyError: If a source is not in the file.
        ValueError: If a row left out holds data the rule does not allow, or
            a declared block is not what its declaration says.
    """
    declared = rule.declared.get(granule.id)
    with netCDF4.Dataset(granule.paths[0], 'r') as handle:
        # masking off: the shared code masks the fill values the config
        # declares, and nothing else may decide what counts as missing
        handle.set_auto_mask(False)
        attrs = read_attrs(handle)
        n_rows = handle.dimensions[OBSERVATION_DIM].size
        location, raw, variables = {}, {}, {}
        for source in dict.fromkeys([*rule.location, *sources]):
            group, name = source.split('/')
            variables[source] = handle[group][name]
            values = np.asarray(variables[source][...])
            (location if source in rule.location else raw)[source] = values
        # rows that are not observations, and rows declared as repeats
        observed = observed_rows(location, rule)
        dropped = declared_mask(n_rows, declared)
        if declared is not None:
            check_declared(granule, declared, location, raw)
        keep = observed & ~dropped
        arrays = {}
        for source in sources:
            values = location[source] if source in location else raw[source]
            leaked = leaked_rows(source, values, observed, rule)
            if leaked:
                raise ValueError(
                    f'orbit {granule.id}: {source} holds data on {leaked} rows with no '
                    f'time, latitude or longitude; they cannot be left out'
                )
            dims, values, note = squeeze_dims(
                values[keep], variables[source].dimensions, OBSERVATION_DIM, DIMENSION_RENAMES
            )
            if not observed.all():
                note = (
                    f'{note}; {int((~observed).sum())} of {n_rows} rows left out as not '
                    f'observations (no time, latitude or longitude written)'
                )
            if declared is not None:
                note = (
                    f'{note}; rows {declared.start}-{declared.stop - 1} of {n_rows} left out '
                    f'as declared: {declared.reason}'
                )
            if source == time_source:
                # the decoded time loses the trailing field dimension
                values = decode_time(np.asarray(values))
                dims = ('obs',)
                note = note.replace(
                    'ntime -> time', 'ntime (year .. millisecond) decoded to one timestamp'
                )
            arrays[source] = SourceArray(
                dims=dims,
                values=np.asarray(values),
                attrs=read_attrs(variables[source]),
                dimension_note=note,
            )
    return GranuleData(
        granule=granule,
        n_obs=int(keep.sum()),
        version=str(attrs.get(VERSION_ATTR, '')),
        attrs=attrs,
        arrays=arrays,
        n_source_rows=n_rows,
    )


def check_granule(handle):
    """Format invariants the verifier confirms on every orbit.

    ``pixel_id`` ("One-based pixel index in Level 1B file") is the source row
    + 1. That is why no index store is needed: the granule index gives every
    observation's source row (P3c, approved 2026-10-22).

    Args:
        handle (h5py.File): The open orbit file.

    Returns:
        list: Problems found, empty if the orbit is as documented.
    """
    pixel = handle['instrument/pixel_id'][...]
    if not np.array_equal(pixel, np.arange(1, pixel.size + 1)):
        return ['pixel_id is not the row + 1']
    return []
