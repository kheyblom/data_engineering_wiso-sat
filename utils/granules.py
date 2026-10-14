"""The granule: the unit every product is read, written and resumed in.

Each product's reader (``products/<product>.py``) lists its granules and reads
one at a time into the shapes defined here. Everything downstream of that is
shared, so this module is the interface between the two halves:

- ``Granule`` is one source file, or the few files a product splits one
  granule across, and its place in the record. A reader returns them in source
  order (orbit order for TROPOMI), which the style guide requires the stores to
  keep. GOSAT is the multi-file case: each day's DED and H2O files hold
  overlapping sets of soundings, merged into one obs axis per day (decided
  2026-10-14).
- ``SourceArray`` is one source variable from one granule, raw: no fill
  masked, no unit converted. In a merged granule a variable can be absent at
  some observations (the sounding is not in its file); those are marked, and
  shared code fills them. Its dimensions are already the store's: the
  observation dimension is ``obs``, others lose a leading ``n``, and length-1
  dimensions are squeezed. Masking and conversion are shared code, because they
  are driven by the config and the nomenclature key rather than the format.
- ``GranuleData`` is everything one read returns.

The granule index every store carries is derived from these: one entry per
granule with its identifier, first observation, observation count, start and
end time, and file name (several, joined by ``FILE_SEPARATOR``, for a
multi-file granule).
"""

from __future__ import annotations

import collections
import datetime
import os
from typing import NamedTuple

import numpy as np
import pandas as pd

# The granule index, one entry per granule, carried identically by every
# store of a product. Coordinates on their own dimension, so a store's data
# variable is still its only data variable
GRANULE_DIM = 'granule'
INDEX_FIELDS = (
    'granule_id',
    'granule_obs_start',
    'granule_obs_count',
    'granule_time_start',
    'granule_time_end',
    'granule_file',
)
INDEX_ATTRS = {
    'granule_id': {'long_name': 'source granule identifier (e.g. orbit number)'},
    'granule_obs_start': {'long_name': 'index along obs of the first observation of the granule'},
    'granule_obs_count': {'long_name': 'number of observations in the granule'},
    'granule_time_start': {'long_name': 'time of the first observation of the granule'},
    'granule_time_end': {'long_name': 'time of the last observation of the granule'},
    'granule_file': {'long_name': 'source file name(s) of the granule, separated by "; "'},
}

# joins the file names of a multi-file granule in its index entry
FILE_SEPARATOR = '; '


class Granule(NamedTuple):
    """One granule: one source file, or the files one is split across.

    Attributes:
        id (str): The product's identifier for it, e.g. an orbit number.
        day (datetime.date): The UTC day the source tree files it under, which
            is what coverage is checked against.
        paths (tuple): Absolute paths of its files, in the reader's order.
    """

    id: str
    day: datetime.date
    paths: tuple


class SourceArray(NamedTuple):
    """One source variable from one granule, raw but on the store's dimensions.

    Attributes:
        dims (tuple): Store dimension names, ``obs`` first.
        values (numpy.ndarray): The values exactly as the file holds them,
            except that time has been decoded to datetime64. Where ``absent``
            is set the value is a placeholder.
        attrs (dict): The source variable's attributes, byte strings decoded.
        dimension_note (str): What was renamed and squeezed, for the metadata,
            e.g. 'nobs -> obs; nwin (length 1) squeezed'.
        absent (numpy.ndarray | None): Along ``obs``, True where the
            observation is not in the file this variable comes from. None when
            it is present everywhere, as in every single-file granule.
    """

    dims: tuple
    values: np.ndarray
    attrs: dict
    dimension_note: str
    absent: np.ndarray | None = None


class GranuleData(NamedTuple):
    """Everything one read of one granule returns.

    Attributes:
        granule (Granule): Which granule.
        n_obs (int): Its observation count.
        version (str): The processor version the file declares.
        attrs (dict): The file's global attributes, byte strings decoded.
        arrays (dict): Source path -> :class:`SourceArray`.
    """

    granule: Granule
    n_obs: int
    version: str
    attrs: dict
    arrays: dict


def decode_text(value):
    """Decode a byte string attribute, leaving anything else as it is.

    Args:
        value: An attribute value.

    Returns:
        The value, with bytes decoded as UTF-8 and stray padding stripped.
    """
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace').strip()
    if isinstance(value, np.ndarray) and value.dtype.kind == 'S':
        return [item.decode('utf-8', errors='replace').strip() for item in value.tolist()]
    return value


def check_order(granules):
    """Fail unless granule identifiers are unique.

    The reader sorts; this only guards against a tree holding one granule
    twice, which would duplicate its observations in every store.

    Args:
        granules (list): From the reader, in source order.

    Raises:
        ValueError: If an identifier repeats or nothing was found.
    """
    if not granules:
        raise ValueError('the raw tree holds no granules')
    counts = collections.Counter(granule.id for granule in granules)
    duplicated = sorted(gid for gid, count in counts.items() if count > 1)
    if duplicated:
        raise ValueError(f'granules appear more than once: {duplicated[:10]}')


def check_coverage(granules, settings):
    """Fail unless the days without a granule are exactly the declared ones.

    A day missing upstream is fine and documented; a day missing because a
    download is incomplete is how a store silently ends up short. The two look
    identical in the tree, so they are told apart by the config, as in MSWEP:
    the run proceeds only if what is missing is precisely
    ``expected_missing_days``.

    Args:
        granules (list): From the reader, in source order.
        settings (dict): The loaded configuration.

    Returns:
        list: The missing days, ascending.

    Raises:
        ValueError: If the missing days differ at all from the declared ones.
    """
    present = sorted({granule.day for granule in granules})
    span = pd.date_range(present[0], present[-1], freq='D').date
    missing = sorted(set(span) - set(present))
    declared = sorted(
        pd.Timestamp(day).date() for day in settings.get('expected_missing_days') or []
    )
    if missing != declared:
        unexpected = sorted(set(missing) - set(declared))
        recovered = sorted(set(declared) - set(missing))
        detail = []
        if unexpected:
            detail.append(
                f'{len(unexpected)} days have no granule and are not declared: '
                f'{[str(day) for day in unexpected[:10]]}{" ..." if len(unexpected) > 10 else ""}'
            )
        if recovered:
            detail.append(
                f'{len(recovered)} days declared missing have granules: '
                f'{[str(day) for day in recovered[:10]]}{" ..." if len(recovered) > 10 else ""}'
            )
        raise ValueError(
            'the raw tree does not cover what the config says it should; '
            + '; '.join(detail)
            + '. Either the download is incomplete or expected_missing_days '
            'needs updating'
        )
    return missing


def time_bounds(time):
    """First and last time of a granule, NaT when it holds no observations.

    Args:
        time (numpy.ndarray): The granule's decoded times.

    Returns:
        tuple: ``(start, end)``, in the times' own datetime64 unit.
    """
    if not time.size:
        nat = np.datetime64('NaT', np.datetime_data(time.dtype)[0])
        return nat, nat
    return time[0], time[-1]


def index_entries(datas, time_source, obs_start):
    """Granule index entries for a run of consecutive granules.

    Args:
        datas (list): :class:`GranuleData` in source order.
        time_source (str): The source path of the time coordinate.
        obs_start (int): Where along ``obs`` the first of them begins.

    Returns:
        dict: Index field -> numpy array, one entry per granule.
    """
    counts = np.array([data.n_obs for data in datas], dtype='int64')
    starts = obs_start + np.concatenate([[0], np.cumsum(counts)[:-1]]).astype('int64')
    bounds = [time_bounds(data.arrays[time_source].values) for data in datas]
    unit = datas[0].arrays[time_source].values.dtype
    return {
        'granule_id': np.array([data.granule.id for data in datas], dtype=object),
        'granule_obs_start': starts,
        'granule_obs_count': counts,
        'granule_time_start': np.array([start for start, _ in bounds], dtype=unit),
        'granule_time_end': np.array([end for _, end in bounds], dtype=unit),
        'granule_file': np.array(
            [FILE_SEPARATOR.join(os.path.basename(path) for path in data.granule.paths)
             for data in datas],
            dtype=object,
        ),
    }


def check_time(datas, time_source, previous_end=None):
    """Fail if time decreases within or between granules.

    The style guide requires that ``time`` never decrease along ``obs``.
    Appending in source order guarantees it only if the source itself is
    ordered, and that is a property of the data to check rather than assume.

    Args:
        datas (list): :class:`GranuleData` in source order.
        time_source (str): The source path of the time coordinate.
        previous_end (numpy.datetime64, optional): The last time already in the
            store, to check the seam with what was written before.

    Returns:
        numpy.datetime64 | None: The last time of these granules, to pass as
            ``previous_end`` next time; the incoming value if all were empty.

    Raises:
        ValueError: If time decreases anywhere.
    """
    last = previous_end
    for data in datas:
        time = data.arrays[time_source].values
        if not time.size:
            continue
        steps = np.diff(time.astype('int64'))
        if (steps < 0).any():
            raise ValueError(
                f'time decreases inside granule {data.granule.id} at '
                f'{int((steps < 0).sum())} observations'
            )
        if last is not None and not np.isnat(last) and time[0] < last:
            raise ValueError(
                f'granule {data.granule.id} starts at {time[0]}, before the '
                f'previous granule ends at {last}'
            )
        last = time[-1]
    return last


def squeeze_dims(values, source_dims, observation_dim, renames):
    """Put a source array onto the store's dimensions.

    The rules are the style guide's: the observation dimension becomes ``obs``,
    other dimensions take the source name without a leading ``n`` (or an
    explicit rename the reader supplies), and length-1 dimensions are squeezed.

    Args:
        values (numpy.ndarray): The raw array.
        source_dims (tuple): Its dimension names in the source.
        observation_dim (str): The source's observation dimension.
        renames (dict): Source dimension -> store dimension, overriding the
            leading-``n`` rule.

    Returns:
        tuple: ``(dims, values, note)``: the store's dimensions, the values on
            them, and a description of every change for the metadata.

    Raises:
        ValueError: If the observation dimension is not the leading one.
    """
    if not source_dims or source_dims[0] != observation_dim:
        raise ValueError(
            f'expected {observation_dim!r} to lead, got dimensions {source_dims}'
        )
    keep = [axis for axis, size in enumerate(values.shape) if axis == 0 or size != 1]
    dims, notes = [], []
    for axis, name in enumerate(source_dims):
        if axis not in keep:
            notes.append(f'{name} (length 1) squeezed')
            continue
        if axis == 0:
            store_name = 'obs'
        elif name in renames:
            store_name = renames[name]
        else:
            store_name = name[1:] if name.startswith('n') and len(name) > 1 else name
        if store_name != name:
            notes.append(f'{name} -> {store_name}')
        dims.append(store_name)
    values = values.reshape([values.shape[axis] for axis in keep])
    return tuple(dims), values, '; '.join(notes) or 'none'
