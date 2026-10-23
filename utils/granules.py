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
- ``RowRule`` says which source rows are observations, for every product
  (user decision 2026-10-17, extending 2026-10-16). **An observation is a row
  whose time, latitude and longitude are all written.** Every reader keeps
  only those rows, through ``observed_rows`` and ``leaked_rows``. A row left
  out may hold nothing but missing values, except in the sources the config
  names in ``allowed_on_rows_left_out``; anything else written on it fails
  the read, because leaving it out would lose data. The verifier works the
  same rows out from raw on its own.
- ``DeclaredRows`` are observations a config leaves out by name, because they
  repeat others (SCIAMACHY, 2026-10-22). Each declaration states what the
  rows must match, and the build and the verifier each check it from raw.
- ``declared_masked_values`` are single values a config masks as defects
  (TROPESS's first ``x`` of each Standard file, R22, 2026-10-23). The reader
  confirms each against its stated condition and marks it on the
  ``SourceArray``; shared code stores NaN there.

The granule index every store carries is derived from these: one entry per
granule with its identifier, first observation, observation count, earliest
and latest time, and file name (several, joined by ``FILE_SEPARATOR``, for a
multi-file granule). A reader may add fields of its own (``INDEX_EXTRA``),
such as TROPESS's per-file algorithm and format versions.
"""

from __future__ import annotations

import collections
import datetime
import os
from typing import NamedTuple

import netCDF4
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
    'granule_source_rows',
)
INDEX_ATTRS = {
    'granule_id': {'long_name': 'source granule identifier (e.g. orbit number)'},
    'granule_obs_start': {'long_name': 'index along obs of the first observation of the granule'},
    'granule_obs_count': {'long_name': 'number of observations in the granule'},
    'granule_time_start': {'long_name': 'time of the earliest observation of the granule'},
    'granule_time_end': {'long_name': 'time of the latest observation of the granule'},
    'granule_file': {'long_name': 'source file name(s) of the granule, separated by "; "'},
    'granule_source_rows': {
        'long_name': 'rows the source file(s) declare along their observation dimension',
        'comment': (
            'Larger than granule_obs_count where rows that are not observations '
            '(no time, latitude or longitude written, and no retrieval) were left '
            'out; 0 observations means the file holds none. For a merged granule, '
            'the sum over its files before merging.'
        ),
    },
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
        masked (numpy.ndarray | None): Along ``obs``, True where the config
            declares the value a defect (``declared_masked_values``) and the
            reader has confirmed it; stored as NaN. None where nothing is.
    """

    dims: tuple
    values: np.ndarray
    attrs: dict
    dimension_note: str
    absent: np.ndarray | None = None
    masked: np.ndarray | None = None


class GranuleData(NamedTuple):
    """Everything one read of one granule returns.

    Attributes:
        granule (Granule): Which granule.
        n_obs (int): Its observation count, as stored.
        version (str): The processor version the file declares.
        attrs (dict): The file's global attributes, byte strings decoded.
        arrays (dict): Source path -> :class:`SourceArray`.
        n_source_rows (int | None): Rows the file(s) declare, before merging or
            leaving out rows that are not observations. None means the same as
            ``n_obs``.
        platform (str | None): The platform the file(s) declare, for a reader
            whose format serves more than one (``PLATFORM_ATTR``); else None.
        index_extra (dict | None): The reader's own granule index fields
            (``INDEX_EXTRA``) for this granule, name -> string.
    """

    granule: Granule
    n_obs: int
    version: str
    attrs: dict
    arrays: dict
    n_source_rows: int | None = None
    platform: str | None = None
    index_extra: dict | None = None


# the coordinates a row needs to be an observation: where and when
LOCATION_COORDINATES = ('time', 'lat', 'lon')


class DeclaredRows(NamedTuple):
    """Rows of one granule left out by declaration, with what they must match.

    For a defect the row rule cannot see: rows that are observations, but
    repeats of others, so keeping them would break "time never decreases"
    (user decision 2026-10-22; ``docs/products/sciamachy.md`` P6). Declared in
    config (``declared_rows_left_out``), never detected, and left out only
    while the build and the verifier each confirm the stated match:

    - ``repeat_of``: the rows are copies of an earlier block of the same file,
      repeated whole, equal bit for bit in every source read except
      ``repeat_except`` (SCIAMACHY orbit 15838, triplicated);
    - ``location_of``: the rows have exactly the time, latitude and longitude
      of a block of another granule, which keeps them (SCIAMACHY orbits
      45262 and 45263, overlapping; a one-time exception to "never select
      observations").

    Attributes:
        granule (str): The granule's identifier.
        start (int): First source row left out.
        stop (int): One past the last.
        repeat_of (tuple | None): ``(start, stop)`` of the block repeated.
        repeat_except (tuple): Source paths that may differ between copies.
        location_of (tuple | None): ``(granule, start, stop, path)``: the
            other granule's block and its first file.
        reason (str): Why, as the config states it, for the metadata.
    """

    granule: str
    start: int
    stop: int
    repeat_of: tuple | None
    repeat_except: tuple
    location_of: tuple | None
    reason: str


class RowRule(NamedTuple):
    """Which rows of a source file are observations; see the module docstring.

    Attributes:
        location (tuple): Source paths of time, lat and lon, from the key's
            coordinate table.
        fills (dict): Source path -> the fill values the config declares for
            it (``source_fill_values``), which count as missing here too.
        allowed (tuple): Source paths that may hold values on a row left out
            (``allowed_on_rows_left_out``), e.g. viewing geometry the producer
            computes before it geolocates.
        declared (dict): Granule id -> :class:`DeclaredRows`, from
            ``declared_rows``; only a reader with ``DECLARED_ROWS`` applies it.
        masked (tuple): The config's ``declared_masked_values`` entries, as
            dicts; only a reader with ``DECLARED_MASKS`` applies them.
    """

    location: tuple
    fills: dict
    allowed: tuple = ()
    declared: dict = {}
    masked: tuple = ()


def declared_rows(settings, granules):
    """The config's ``declared_rows_left_out``, checked against the listing.

    Each entry names a granule, the source rows ``[start, stop)`` it leaves
    out, a ``reason``, and exactly one check: ``repeat_of: [start, stop]``
    (with optional ``repeat_except``), or ``same_location_as: {granule,
    rows: [start, stop]}``.

    Args:
        settings (dict): The loaded configuration.
        granules (list): The reader's listing, to find each granule named.

    Returns:
        dict: Granule id -> :class:`DeclaredRows`.

    Raises:
        ValueError: If an entry is malformed, names a granule not listed, or
            a granule is named twice.
    """
    paths = {granule.id: granule.paths[0] for granule in granules}
    declared = {}
    for entry in settings.get('declared_rows_left_out') or []:
        gid = str(entry.get('granule', ''))
        start, stop = (int(row) for row in entry.get('rows', (0, 0)))
        repeat = entry.get('repeat_of')
        other = entry.get('same_location_as')
        problems = []
        if gid not in paths:
            problems.append(f'granule {gid!r} is not in the listing')
        if gid in declared:
            problems.append(f'granule {gid!r} is declared twice')
        if not 0 <= start < stop:
            problems.append(f'rows {entry.get("rows")} are not [start, stop) with start < stop')
        if (repeat is None) == (other is None):
            problems.append('give exactly one of repeat_of and same_location_as')
        if not str(entry.get('reason', '')).strip():
            problems.append('a reason is required')
        location_of = None
        if repeat is not None:
            first, last = (int(row) for row in repeat)
            if not 0 <= first < last <= start or (stop - start) % (last - first):
                problems.append(
                    f'repeat_of {repeat} must be an earlier block whose length divides {stop - start}'
                )
            repeat = (first, last)
        if other is not None:
            ogid = str(other.get('granule', ''))
            first, last = (int(row) for row in other.get('rows', (0, 0)))
            if ogid not in paths or ogid == gid:
                problems.append(f'same_location_as names {ogid!r}, which is not another listed granule')
            if last - first != stop - start or first < 0:
                problems.append(f'same_location_as rows {other.get("rows")} are not {stop - start} rows')
            location_of = (ogid, first, last, paths.get(ogid))
        if problems:
            raise ValueError(f'declared_rows_left_out entry {entry}: {"; ".join(problems)}')
        declared[gid] = DeclaredRows(
            granule=gid, start=start, stop=stop, repeat_of=repeat,
            repeat_except=tuple(entry.get('repeat_except') or ()),
            location_of=location_of, reason=str(entry['reason']).strip(),
        )
    return declared


def declared_mask(n_rows, declared):
    """The rows a declaration leaves out, as a mask over a file's rows.

    Args:
        n_rows (int): The file's rows.
        declared (DeclaredRows | None): The granule's declaration, if any.

    Returns:
        numpy.ndarray: bool per row, True where left out.

    Raises:
        ValueError: If the declared rows run past the file.
    """
    mask = np.zeros(n_rows, dtype=bool)
    if declared is None:
        return mask
    if declared.stop > n_rows:
        raise ValueError(
            f'granule {declared.granule}: declared rows {declared.start}-{declared.stop} '
            f'run past its {n_rows} rows'
        )
    mask[declared.start:declared.stop] = True
    return mask


def same_bits(left, right):
    """Whether two raw arrays are identical, NaN included, bit for bit.

    Args:
        left (numpy.ndarray): One array.
        right (numpy.ndarray): The other.

    Returns:
        bool: True if shape, dtype and every byte agree.
    """
    return left.shape == right.shape and left.dtype == right.dtype and left.tobytes() == right.tobytes()


def unwritten(values, fill=()):
    """Rows of a raw array that hold no value at all.

    A value is missing if it is the netCDF default fill for its dtype (what an
    unwritten HDF5 chunk reads back as), a declared fill, or NaN.

    Args:
        values (numpy.ndarray): A raw array, observation dimension first.
        fill (Iterable): The source's declared fill values.

    Returns:
        numpy.ndarray: bool per row, True where every element is missing.
    """
    flat = values.reshape(values.shape[0], -1)
    missing = np.zeros(flat.shape, dtype=bool)
    candidates = list(fill)
    default = netCDF4.default_fillvals.get(values.dtype.str[1:])
    if default is not None:
        candidates.append(default)
    for value in candidates:
        missing |= flat == np.asarray(value, dtype=values.dtype)
    if values.dtype.kind == 'f':
        missing |= np.isnan(flat)
    return missing.all(axis=1)


def observed_rows(location, rule):
    """The rows that are observations: time, lat and lon all written.

    Args:
        location (dict): Source path -> raw array, for every source in
            ``rule.location``.
        rule (RowRule): The rule.

    Returns:
        numpy.ndarray: bool per row.
    """
    keep = None
    for source in rule.location:
        located = ~unwritten(location[source], rule.fills.get(source, ()))
        keep = located if keep is None else keep & located
    return keep


def leaked_rows(source, values, keep, rule):
    """How many rows left out hold a value in this source that may not be lost.

    The location sources are exempt (a row can have a time but no position),
    and so are the sources the config allows.

    Args:
        source (str): The source path.
        values (numpy.ndarray): Its raw array, every row.
        keep (numpy.ndarray): From ``observed_rows``.
        rule (RowRule): The rule.

    Returns:
        int: Rows left out on which this source holds a value.
    """
    if keep.all() or source in rule.location or source in rule.allowed:
        return 0
    return int((~unwritten(values[~keep], rule.fills.get(source, ()))).sum())


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


# the period a reader's tree files granules under (``COVERAGE_FREQUENCY`` in
# the reader, daily if it names none) -> the config key declaring the periods
# with no granule, and the word for one in messages. SCIAMACHY files orbits by
# month, and its file names carry no date (2026-10-22)
COVERAGE_KEYS = {'D': ('expected_missing_days', 'days'), 'MS': ('expected_missing_months', 'months')}


def check_coverage(granules, settings, frequency='D'):
    """Fail unless the periods without a granule are exactly the declared ones.

    A day missing upstream is fine and documented; a day missing because a
    download is incomplete is how a store silently ends up short. The two look
    identical in the tree, so they are told apart by the config, as in MSWEP:
    the run proceeds only if what is missing is precisely
    ``expected_missing_days``. A reader whose tree is filed by month checks
    months instead, against ``expected_missing_months``.

    Args:
        granules (list): From the reader, in source order.
        settings (dict): The loaded configuration.
        frequency (str): The reader's ``COVERAGE_FREQUENCY``, a key of
            ``COVERAGE_KEYS``.

    Returns:
        list: The missing periods' first days, ascending.

    Raises:
        ValueError: If the missing periods differ at all from the declared
            ones, or the frequency is unknown.
    """
    if frequency not in COVERAGE_KEYS:
        raise ValueError(f'unknown coverage frequency {frequency!r}; expected one of {list(COVERAGE_KEYS)}')
    key, unit = COVERAGE_KEYS[frequency]
    present = sorted({granule.day for granule in granules})
    span = pd.date_range(present[0], present[-1], freq=frequency).date
    missing = sorted(set(span) - set(present))
    declared = sorted(pd.Timestamp(day).date() for day in settings.get(key) or [])
    if missing != declared:
        unexpected = sorted(set(missing) - set(declared))
        recovered = sorted(set(declared) - set(missing))
        detail = []
        if unexpected:
            detail.append(
                f'{len(unexpected)} {unit} have no granule and are not declared: '
                f'{[str(day) for day in unexpected[:10]]}{" ..." if len(unexpected) > 10 else ""}'
            )
        if recovered:
            detail.append(
                f'{len(recovered)} {unit} declared missing have granules: '
                f'{[str(day) for day in recovered[:10]]}{" ..." if len(recovered) > 10 else ""}'
            )
        raise ValueError(
            'the raw tree does not cover what the config says it should; '
            + '; '.join(detail)
            + f'. Either the download is incomplete or {key} needs updating'
        )
    return missing


def time_bounds(time):
    """Earliest and latest time of a granule, NaT when it holds no observations.

    The minimum and maximum, not the first and last: the same for a product
    whose files are in time order, and the right span for one whose files
    are not (TROPESS, user decision 2026-10-23).

    Args:
        time (numpy.ndarray): The granule's decoded times.

    Returns:
        tuple: ``(start, end)``, in the times' own datetime64 unit.
    """
    if not time.size:
        nat = np.datetime64('NaT', np.datetime_data(time.dtype)[0])
        return nat, nat
    return time.min(), time.max()


def index_fields(reader):
    """Every granule index field a product's stores carry.

    Args:
        reader (module): The product's reader.

    Returns:
        tuple: ``INDEX_FIELDS``, then the reader's ``INDEX_EXTRA`` fields.
    """
    return INDEX_FIELDS + tuple(getattr(reader, 'INDEX_EXTRA', {}))


def index_attrs(reader):
    """Attributes of every granule index field a product's stores carry.

    Args:
        reader (module): The product's reader.

    Returns:
        dict: Field -> attributes.
    """
    return INDEX_ATTRS | dict(getattr(reader, 'INDEX_EXTRA', {}))


def index_entries(datas, time_source, obs_start):
    """Granule index entries for a run of consecutive granules.

    Args:
        datas (list): :class:`GranuleData` in source order.
        time_source (str): The source path of the time coordinate.
        obs_start (int): Where along ``obs`` the first of them begins.

    Returns:
        dict: Index field -> numpy array, one entry per granule, with the
            reader's own fields last.

    Raises:
        ValueError: If the granules do not all carry the same extra fields.
    """
    counts = np.array([data.n_obs for data in datas], dtype='int64')
    starts = obs_start + np.concatenate([[0], np.cumsum(counts)[:-1]]).astype('int64')
    bounds = [time_bounds(data.arrays[time_source].values) for data in datas]
    unit = datas[0].arrays[time_source].values.dtype
    extra = list(datas[0].index_extra or {})
    if any(list(data.index_extra or {}) != extra for data in datas):
        raise ValueError('the granules of one append carry different extra index fields')
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
        'granule_source_rows': np.array(
            [data.n_obs if data.n_source_rows is None else data.n_source_rows for data in datas],
            dtype='int64',
        ),
    } | {
        field: np.array([data.index_extra[field] for data in datas], dtype=object)
        for field in extra
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
