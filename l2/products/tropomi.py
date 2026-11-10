"""Reader for the SRON TROPOMI HDO Level 2 product (processor 8.1).

One granule is one orbit file:

```
<raw>/<YYYY>/<MM>/<DD>/<orbit>/s5p_l2_hdo_<product_version>_<orbit:05d>.nc
```

Format facts the reader depends on, measured 2026-10-13/14 (see
``docs/products/tropomi.md``):

- **No root variables.** Everything sits in the groups ``target_product``,
  ``instrument``, ``diagnostics``, ``meteo`` and ``side_product``, so a source
  is named by its HDF5 path, ``<group>/<variable>``.
- **``nobs`` is the L1B swath flattened** scanline-major, 215 ground pixels per
  scanline. ``check_granule`` confirms this for every orbit; the verifier runs
  it.
- **``nwin`` has length 1** and is squeezed.
- **Time is broken down**: ``instrument/time`` is int32 ``(nobs, 7)``,
  year .. millisecond. ``decode_time`` turns it into datetime64[ms], which
  holds it exactly.
- **No ``_FillValue`` is declared.** Missing values are the netCDF default
  fills (float 9.96921e36, int -2147483647), so the configs declare them and
  shared code masks them. This reader returns values exactly as stored.
- **The tree holds stray ``.DS_Store`` files**, so only all-digit directory
  names are walked.
- **Unprocessed rows** (audit of all 38,648 files, 2026-10-16). SRON leaves
  some rows unwritten:
  - 109 files are shells, with nothing written at all;
  - 77 are partial, mostly unprocessed pixels.

  A row whose ``time`` is all fill was never processed, and every variable
  the pipeline reads is fill on it too (48.7 million such rows checked).
- **Six rows have a time but no position** (orbits 8480, 8674 and 8726, June
  2019, found by the first production verification, 2026-10-17). SRON wrote
  their time and viewing geometry (SZA ~100.5-101 deg, night) and nothing
  else: no latitude, longitude or retrieval.

  Both kinds are left out by the shared rule (``RowRule`` in
  ``utils/granules.py``; user decisions 2026-10-16 and 2026-10-17): a row is
  an observation only if time, latitude and longitude are all written. The
  production config allows ``instrument/solar_zenith_angle`` to hold values
  on a row left out; anything else written there makes ``read_granule``
  raise. A shell becomes a granule with no observations; the index keeps its
  row count as ``granule_source_rows``.
- **Three files are corrupt upstream** (orbits 3335, 7821 and 7844, the same
  bytes as on the server). They are skipped only if declared in
  ``expected_unreadable_granules``, and only while they still fail to open.
  That is probed in a child process: HDF5 segfaults on 3335 rather than
  raising (found by the first production job, 2026-10-16).

The build reads with netCDF4 and the verifier reads with h5py, so the two do
not share a decoding path. Only ``decode_time`` and ``check_granule`` are
shared with the verifier, because they are facts about this format rather than
steps of the pipeline.
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
import sys

import netCDF4
import numpy as np
import pandas as pd

from utils.granules import (
    Granule, GranuleData, SourceArray, decode_text, leaked_rows, observed_rows, squeeze_dims,
)

FILE_RE = re.compile(r'^s5p_l2_hdo_(?P<product_version>\d{4})_(?P<orbit>\d{5})\.nc$')

# the source's observation dimension, and any rename the leading-'n' rule
# does not cover (none here: nlayer -> layer, nlevel -> level, ncorner -> corner)
OBSERVATION_DIM = 'nobs'
DIMENSION_RENAMES = {}
# index 0 of level is the top of the atmosphere, 0 Pa, and the last level is
# the surface (naming pass N7)
VERTICAL_ORDER = 'top_first'

# the root attribute holding the processor version the stores are named by
VERSION_ATTR = 'version'

PIXELS_PER_SCANLINE = 215

# fields of instrument/time, in order
TIME_FIELDS = ('year', 'month', 'day', 'hour', 'minute', 'second', 'millisecond')


def digit_entries(directory):
    """Subdirectories whose names are all digits, sorted numerically.

    Args:
        directory (str): A directory of the raw tree.

    Returns:
        list: Entry names.
    """
    return sorted((entry for entry in os.listdir(directory) if entry.isdigit()), key=int)


def list_granules(raw_root, expected_empty=(), expected_unreadable=()):
    """Every orbit file under the raw root, in orbit order.

    Orbit order is time order and is the order the style guide requires. Walks
    year, month, day and orbit directories only, so the cost is one listing
    per directory and no file is opened.

    Some orbit directories are empty upstream (353 checked against the server,
    2026-10-14), and an empty one can also be a download that never arrived
    (339 were). The two look the same on disk, so they are told apart by the
    config, as missing days are: an empty directory is skipped only if its
    orbit is in ``expected_empty``.

    Args:
        raw_root (str): The ``hdo`` directory.
        expected_empty (Iterable): Orbit numbers whose directories are known to
            be empty upstream (``expected_empty_granules`` in the config).
        expected_unreadable (Iterable): Orbit numbers whose files are known to
            be corrupt upstream (``expected_unreadable_granules``). Each is
            opened to confirm it still fails, so a repaired file is not left
            out silently.

    Returns:
        list: :class:`Granule` per orbit file, sorted by orbit number.

    Raises:
        FileNotFoundError: If the root does not exist.
        ValueError: If an orbit directory is empty and not declared, a declared
            one holds a file, one holds several orbit files or another orbit's
            file, or a file declared unreadable opens or is not there.
    """
    expected_empty = {int(orbit) for orbit in expected_empty}
    expected_unreadable = {int(orbit) for orbit in expected_unreadable}
    found_unreadable = set()
    if not os.path.isdir(raw_root):
        raise FileNotFoundError(f'no raw data directory at {raw_root}')

    granules, problems = [], []
    for year in digit_entries(raw_root):
        for month in digit_entries(os.path.join(raw_root, year)):
            for day in digit_entries(os.path.join(raw_root, year, month)):
                day_dir = os.path.join(raw_root, year, month, day)
                date = datetime.date(int(year), int(month), int(day))
                for orbit in digit_entries(day_dir):
                    orbit_dir = os.path.join(day_dir, orbit)
                    matches = [
                        (name, match)
                        for name in os.listdir(orbit_dir)
                        for match in [FILE_RE.match(name)]
                        if match
                    ]
                    if not matches and int(orbit) in expected_empty:
                        continue
                    if int(orbit) in expected_empty:
                        problems.append(f'{orbit_dir} is declared empty but holds a file')
                    if len(matches) != 1:
                        problems.append(f'{orbit_dir} holds {len(matches)} orbit files')
                        continue
                    name, match = matches[0]
                    if int(match['orbit']) != int(orbit):
                        problems.append(f'{orbit_dir} holds {name}, a different orbit')
                        continue
                    if int(orbit) in expected_unreadable:
                        found_unreadable.add(int(orbit))
                        if opens(os.path.join(orbit_dir, name)):
                            problems.append(f'{orbit_dir} is declared unreadable but opens')
                        continue
                    granules.append(
                        Granule(id=match['orbit'], day=date, paths=(os.path.join(orbit_dir, name),))
                    )
    stale = sorted(expected_unreadable - found_unreadable)
    if stale:
        problems.append(f'orbits declared unreadable have no file: {stale}')
    if problems:
        raise ValueError(
            f'{len(problems)} orbit directories are not as expected: {problems[:10]}'
        )
    return sorted(granules, key=lambda granule: int(granule.id))


def opens(path):
    """Whether netCDF4 can open a file.

    Tried in a child process, because HDF5 does not always fail cleanly on a
    corrupt file: orbit 3335 (a bad fractal heap header) segfaults it, and
    in this process that would end the build without a traceback. Only
    declared-unreadable files are probed, so the extra interpreter is cheap.

    Args:
        path (str): The file.

    Returns:
        bool: True if it opens; False if opening raises or crashes.
    """
    probe = 'import sys, netCDF4; netCDF4.Dataset(sys.argv[1], "r").close()'
    result = subprocess.run(
        [sys.executable, '-c', probe, path], capture_output=True, check=False
    )
    return result.returncode == 0


def is_fill(values):
    """Rows of a raw array that hold only the netCDF default fill.

    An unwritten HDF5 chunk reads back as the dataset's fill value, which SRON
    leaves at the netCDF default, so this is what an unprocessed row looks like.

    Args:
        values (numpy.ndarray): A raw array, observation dimension first.

    Returns:
        numpy.ndarray: bool per row.
    """
    fill = np.asarray(netCDF4.default_fillvals[values.dtype.str[1:]], dtype=values.dtype)
    flat = values.reshape(values.shape[0], -1)
    return (flat == fill).all(axis=1)


def decode_time(raw):
    """Decode ``instrument/time`` into datetime64[ms].

    Args:
        raw (numpy.ndarray): int32 ``(n, 7)``, year .. millisecond.

    Returns:
        numpy.ndarray: datetime64[ms] ``(n,)``, exact.

    Raises:
        ValueError: If the array is not ``(n, 7)``.
    """
    if raw.ndim != 2 or raw.shape[1] != len(TIME_FIELDS):
        raise ValueError(f'expected time as (n, {len(TIME_FIELDS)}), got {raw.shape}')
    frame = pd.DataFrame(raw.astype('int64'), columns=TIME_FIELDS)
    return pd.to_datetime(frame).to_numpy().astype('datetime64[ms]')


def read_attrs(item):
    """An item's attributes, byte strings decoded.

    Args:
        item: A netCDF4 Dataset, Group or Variable.

    Returns:
        dict: Attribute name -> value.
    """
    return {name: decode_text(item.getncattr(name)) for name in item.ncattrs()}


def read_granule(granule, sources, time_source, rule):
    """Read the named variables of one orbit file, raw.

    A top-level function of picklable arguments, so the build can run it in a
    process pool: HDF5 is not safe to call from several threads.

    Args:
        granule (Granule): The orbit, from ``list_granules``.
        sources (Sequence): Source paths to read, ``<group>/<variable>``.
        time_source (str): The source path of the time coordinate, which is
            returned decoded.
        rule (RowRule): Which rows are observations.

    Returns:
        GranuleData: The orbit's observations on the store's dimensions,
            values exactly as stored except for the decoded time.

    Raises:
        KeyError: If a source is not in the file.
        ValueError: If a row left out holds data the rule does not allow, so
            leaving it out would lose something.
    """
    with netCDF4.Dataset(granule.paths[0], 'r') as handle:
        # masking off: the shared code masks the fill values the config
        # declares, and nothing else may decide what counts as missing
        handle.set_auto_mask(False)
        attrs = read_attrs(handle)
        n_rows = handle.dimensions[OBSERVATION_DIM].size
        # read even when no store being built needs them: they decide the rows
        location = {}
        for source in rule.location:
            group, name = source.split('/')
            location[source] = np.asarray(handle[group][name][...])
        keep = observed_rows(location, rule)
        arrays = {}
        for source in sources:
            group, name = source.split('/')
            variable = handle[group][name]
            values = location[source] if source in location else np.asarray(variable[...])
            if not keep.all():
                leaked = leaked_rows(source, values, keep, rule)
                if leaked:
                    raise ValueError(
                        f'orbit {granule.id}: {source} holds data on {leaked} rows with no '
                        f'time, latitude or longitude; they cannot be left out'
                    )
                values = values[keep]
            dims, values, note = squeeze_dims(
                values, variable.dimensions, OBSERVATION_DIM, DIMENSION_RENAMES
            )
            if not keep.all():
                note = (
                    f'{note}; {int((~keep).sum())} of {n_rows} rows left out as not '
                    f'observations (no time, latitude or longitude written)'
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
                attrs=read_attrs(variable),
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

    ``nobs`` is documented as the L1B swath flattened scanline-major. If that
    ever fails, an observation index no longer says where in the swath it was,
    and the layout note in the store metadata would be false. The check runs on
    the rows where the indices were written: in a partial file they are often
    unwritten, and there is nothing to check.

    Args:
        handle (h5py.File): The open orbit file.

    Returns:
        list: Problems found, empty if the orbit is as documented.
    """
    problems = []
    scanline = handle['instrument/scanline'][...]
    pixel = handle['instrument/ground_pixel'][...]
    position = np.arange(scanline.size)
    if scanline.size % PIXELS_PER_SCANLINE:
        problems.append(f'nobs {scanline.size} is not a whole number of {PIXELS_PER_SCANLINE}-pixel scanlines')
    written = ~is_fill(scanline)
    if written.any():
        first = int(np.argmax(written))
        base = int(scanline[first]) - first // PIXELS_PER_SCANLINE
        if not np.array_equal(scanline[written], base + position[written] // PIXELS_PER_SCANLINE):
            problems.append('scanline is not position // 215 from the first scanline')
    written = ~is_fill(pixel)
    if not np.array_equal(pixel[written], position[written] % PIXELS_PER_SCANLINE):
        problems.append('ground_pixel is not position % 215')
    return problems
