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

The build reads with netCDF4 and the verifier reads with h5py, so the two do
not share a decoding path. Only ``decode_time`` and ``check_granule`` are
shared with the verifier, because they are facts about this format rather than
steps of the pipeline.
"""

from __future__ import annotations

import datetime
import os
import re

import netCDF4
import numpy as np
import pandas as pd

from utils.granules import Granule, GranuleData, SourceArray, decode_text, squeeze_dims

FILE_RE = re.compile(r'^s5p_l2_hdo_(?P<product_version>\d{4})_(?P<orbit>\d{5})\.nc$')

# the source's observation dimension, and any rename the leading-'n' rule
# does not cover (none here: nlayer -> layer, nlevel -> level, ncorner -> corner)
OBSERVATION_DIM = 'nobs'
DIMENSION_RENAMES = {}

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


def list_granules(raw_root):
    """Every orbit file under the raw root, in orbit order.

    Orbit order is time order and is the order the style guide requires. Walks
    year, month, day and orbit directories only, so the cost is one listing
    per directory and no file is opened.

    Args:
        raw_root (str): The ``hdo`` directory.

    Returns:
        list: :class:`Granule` per orbit file, sorted by orbit number.

    Raises:
        FileNotFoundError: If the root does not exist.
        ValueError: If an orbit directory does not hold exactly one orbit file,
            or holds one for a different orbit.
    """
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
                    if len(matches) != 1:
                        problems.append(f'{orbit_dir} holds {len(matches)} orbit files')
                        continue
                    name, match = matches[0]
                    if int(match['orbit']) != int(orbit):
                        problems.append(f'{orbit_dir} holds {name}, a different orbit')
                        continue
                    granules.append(
                        Granule(id=match['orbit'], day=date, paths=(os.path.join(orbit_dir, name),))
                    )
    if problems:
        raise ValueError(
            f'{len(problems)} orbit directories are not as expected: {problems[:10]}'
        )
    return sorted(granules, key=lambda granule: int(granule.id))


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


def read_granule(granule, sources, time_source):
    """Read the named variables of one orbit file, raw.

    A top-level function of picklable arguments, so the build can run it in a
    process pool: HDF5 is not safe to call from several threads.

    Args:
        granule (Granule): The orbit, from ``list_granules``.
        sources (Sequence): Source paths to read, ``<group>/<variable>``.
        time_source (str): The source path of the time coordinate, which is
            returned decoded.

    Returns:
        GranuleData: The orbit's arrays on the store's dimensions, values
            exactly as stored except for the decoded time.

    Raises:
        KeyError: If a source is not in the file.
    """
    with netCDF4.Dataset(granule.paths[0], 'r') as handle:
        # masking off: the shared code masks the fill values the config
        # declares, and nothing else may decide what counts as missing
        handle.set_auto_mask(False)
        attrs = read_attrs(handle)
        n_obs = handle.dimensions[OBSERVATION_DIM].size
        arrays = {}
        for source in sources:
            group, name = source.split('/')
            variable = handle[group][name]
            values = variable[...]
            dims, values, note = squeeze_dims(
                values, variable.dimensions, OBSERVATION_DIM, DIMENSION_RENAMES
            )
            if source == time_source:
                # the decoded time loses the trailing field dimension
                values = decode_time(np.asarray(values))
                dims = ('obs',)
                note = f'{OBSERVATION_DIM} -> obs; ntime (year .. millisecond) decoded to one timestamp'
            arrays[source] = SourceArray(
                dims=dims,
                values=np.asarray(values),
                attrs=read_attrs(variable),
                dimension_note=note,
            )
    return GranuleData(
        granule=granule,
        n_obs=n_obs,
        version=str(attrs.get(VERSION_ATTR, '')),
        attrs=attrs,
        arrays=arrays,
    )


def check_granule(handle):
    """Format invariants the verifier confirms on every orbit.

    ``nobs`` is documented as the L1B swath flattened scanline-major. If that
    ever fails, an observation index no longer says where in the swath it was,
    and the layout note in the store metadata would be false.

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
    if scanline.size and not np.array_equal(
        scanline - scanline[0], position // PIXELS_PER_SCANLINE
    ):
        problems.append('scanline is not position // 215 from the first scanline')
    if not np.array_equal(pixel, position % PIXELS_PER_SCANLINE):
        problems.append('ground_pixel is not position % 215')
    return problems
