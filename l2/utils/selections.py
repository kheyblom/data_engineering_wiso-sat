"""Source slices, the checks on what they leave out, and lookups onto another grid.

Added 2026-10-28 for TROPESS v2 and shaped for TES (``docs/products/tropess.md``
V9, D2, user decision 2026-10-28). Three declared things, never detected:

- **A slice** of a source, written in the nomenclature key's
  ``original_variable_name`` (``x[:, 0:17]``; ``utils/nomenclature.py``,
  ``split_source``). The selection applies to the source's axes after the
  reader has squeezed its length-1 axes, the same array the verifier slices.
  One source can so feed several canonical names, one per slice (TES's
  stacked HDO and H2O halves).
- **What the slices leave out**, declared per source path in the config's
  ``source_remainders``: a range on one axis that must be ``empty`` (the
  source's declared fill, or NaN), or ``equal`` to another range of that
  axis (a copy, such as TROPESS v2's repeated pressure grid). The key's slices
  and the declared remainders together must cover every value of the source,
  or the config is refused, so nothing a source holds is dropped unseen.
- **A lookup onto another grid**, declared per source path in
  ``level_lookups``: ``{grid: <path>, at: <source>}`` takes, for each row and
  each written value of ``at``, the source's value at the one position where
  ``grid`` equals it (TROPESS v2's ``altitude``, on the 67-level
  forward-model grid, at the 17 retrieval pressures; R43). Every written
  ``at`` must be found exactly once.

This is the build's side. The verifier repeats all three from raw with its own
code (``verify_wisosat_zarr.py``), not these helpers.
"""

from __future__ import annotations

import numpy as np

from .nomenclature import split_source, variables

REMAINDER_RULES = ('empty', 'equal')


def declared_fill_values(settings, path):
    """The fill the config declares for a source path (NaN is always fill).

    Args:
        settings (dict): The loaded configuration.
        path (str): The source path.

    Returns:
        list: The declared values.
    """
    return list((settings.get('source_fill_values') or {}).get(path) or [])


def unwritten(values, fill):
    """True where a value is a declared fill or NaN.

    Args:
        values (numpy.ndarray): Values.
        fill (list): Declared fill values.

    Returns:
        numpy.ndarray: bool, the shape of ``values``.
    """
    out = np.zeros(values.shape, dtype=bool)
    for value in fill:
        out |= values == np.asarray(value, dtype=values.dtype)
    if values.dtype.kind == 'f':
        out |= np.isnan(values)
    return out


def remainder_rules(settings, path):
    """The config's checked remainders of one source, validated.

    Args:
        settings (dict): The loaded configuration.
        path (str): The source path.

    Returns:
        list: Dicts with ``axis`` (int, 1 or more), ``range`` (start, stop),
            ``rule`` and, for ``equal``, ``to`` (start, stop).

    Raises:
        ValueError: If an entry is malformed.
    """
    rules = []
    for entry in (settings.get('source_remainders') or {}).get(path) or []:
        axis, span, rule = entry.get('axis'), entry.get('range'), entry.get('rule')
        if not isinstance(axis, int) or axis < 1 or rule not in REMAINDER_RULES or len(span or ()) != 2:
            raise ValueError(
                f'source_remainders {path}: each entry needs an axis (1 or more), a range '
                f'[start, stop] and a rule in {REMAINDER_RULES}; got {entry}'
            )
        start, stop = (int(value) for value in span)
        checked = {'axis': axis, 'range': (start, stop), 'rule': rule}
        if rule == 'equal':
            to = entry.get('to')
            if len(to or ()) != 2 or int(to[1]) - int(to[0]) != stop - start:
                raise ValueError(f'source_remainders {path}: an equal rule needs a range "to" of the same length; got {entry}')
            checked['to'] = (int(to[0]), int(to[1]))
        rules.append(checked)
    return rules


def key_selections(product):
    """The key's slices of each sliced source.

    Args:
        product (str): Whose key.

    Returns:
        dict: Source path -> list of selections (tuples), for every source
            the key slices.
    """
    out = {}
    for entry in variables(product).values():
        path, selection = split_source(entry.original)
        if selection is not None:
            out.setdefault(path, []).append(selection)
    return out


def axis_index(ndim, axis, span):
    """An index tuple selecting ``span`` on one axis (counted from the obs axis) and all of the others.

    Args:
        ndim (int): The array's dimensions, the obs axis included.
        axis (int): The axis.
        span (tuple): (start, stop).

    Returns:
        tuple: The index.
    """
    index = [slice(None)] * ndim
    index[axis] = slice(*span)
    return tuple(index)


def coverage_problems(path, shape, selections, rules):
    """Whether the key's slices and the declared remainders cover every value of a source.

    Args:
        path (str): The source path, for the message.
        shape (tuple): The source's shape, the obs axis included.
        selections (list): The key's selections of it.
        rules (list): Its ``remainder_rules``.

    Returns:
        list: One problem if anything is covered by neither, else none.
    """
    covered = np.zeros((1,) + tuple(shape[1:]), dtype=bool)
    for selection in selections:
        covered[(slice(None),) + tuple(selection[1:])] = True
    for rule in rules:
        if rule['axis'] >= len(shape) or rule['range'][1] > shape[rule['axis']]:
            return [f'{path}: source_remainders names axis {rule["axis"]} range {rule["range"]}, '
                    f'outside its shape {tuple(shape[1:])}']
        covered[axis_index(len(shape), rule['axis'], rule['range'])] = True
    if not covered.all():
        return [f'{path}: {int((~covered).sum())} of its {covered.size} values per observation are '
                f'neither in a slice the key names nor in a declared remainder']
    return []


def remainder_problems(path, values, fill, rules):
    """Whether a source's declared remainders hold what the config says.

    Args:
        path (str): The source path, for the message.
        values (numpy.ndarray): The source's values over the observations.
        fill (list): Its declared fill.
        rules (list): Its ``remainder_rules``.

    Returns:
        list: Problems, empty if every rule holds on every observation.
    """
    problems = []
    for rule in rules:
        region = values[axis_index(values.ndim, rule['axis'], rule['range'])]
        if rule['rule'] == 'empty':
            bad = int((~unwritten(region, fill)).sum())
            if bad:
                problems.append(f'{path}: {bad} values written in axis {rule["axis"]} range {rule["range"]}, '
                                f'declared empty')
        else:
            other = values[axis_index(values.ndim, rule['axis'], rule['to'])]
            gone, other_gone = unwritten(region, fill), unwritten(other, fill)
            same = (gone & other_gone) | (~gone & ~other_gone & (region == other))
            bad = int((~same.reshape(len(same), -1).all(axis=1)).sum())
            if bad:
                problems.append(f'{path}: axis {rule["axis"]} range {rule["range"]} differs from '
                                f'{rule["to"]} on {bad} observations, declared equal')
    return problems


def check_selections(datas, settings, product, paths):
    """Check, on a batch as read, every sliced or remaindered source this pass reads.

    Args:
        datas (list): GranuleData of the batch.
        settings (dict): The loaded configuration.
        product (str): Whose key.
        paths (Iterable): The source paths the pass reads.

    Raises:
        ValueError: If the slices and remainders do not cover a source, or a
            remainder breaks its rule.
    """
    selections = key_selections(product)
    problems = []
    for path in sorted(set(paths)):
        rules = remainder_rules(settings, path)
        if path not in selections and not rules:
            continue
        fill = declared_fill_values(settings, path)
        for data in datas:
            array = data.arrays[path]
            values = array.values if array.absent is None else array.values[~array.absent]
            problems += coverage_problems(path, array.values.shape, selections.get(path, []), rules)
            problems += [f'granule {data.granule.id}: {problem}'
                         for problem in remainder_problems(path, values, fill, rules)]
    if problems:
        raise ValueError('; '.join(dict.fromkeys(problems)))


def lookup_inputs(settings, path):
    """The sources a lookup onto another grid reads besides its own.

    Args:
        settings (dict): The loaded configuration.
        path (str): The looked-up source path.

    Returns:
        list: The ``grid`` path and the ``at`` path, or empty where none is declared.
    """
    lookup = (settings.get('level_lookups') or {}).get(path)
    if not lookup:
        return []
    if not lookup.get('grid') or not lookup.get('at'):
        raise ValueError(f'level_lookups {path}: needs a grid and an at; got {lookup}')
    return [lookup['grid'], split_source(lookup['at'])[0]]


def read_paths(settings, sources):
    """The source paths a set of the key's sources needs read: their own, and any lookup's.

    Args:
        settings (dict): The loaded configuration.
        sources (Iterable): Sources as the key writes them.

    Returns:
        set: Source paths.
    """
    paths = set()
    for source in sources:
        path = split_source(source)[0]
        paths.add(path)
        paths.update(lookup_inputs(settings, path))
    return paths


def lookup_levels(array, data, settings, path):
    """A source's values at the positions where its grid equals each written ``at``.

    Args:
        array (SourceArray): The looked-up source, as read.
        data (GranuleData): The granule, which holds the grid and ``at``.
        settings (dict): The loaded configuration.
        path (str): The looked-up source path.

    Returns:
        tuple: ``(values, dims, note)`` on ``at``'s dimensions; the source's
            declared fill (or NaN) where ``at`` is not written.

    Raises:
        ValueError: If a written ``at`` is found other than exactly once in
            its row's grid, or the source has no fill to write elsewhere.
    """
    lookup = settings['level_lookups'][path]
    grid = data.arrays[lookup['grid']].values
    at_path, at_selection = split_source(lookup['at'])
    at_array = data.arrays[at_path]
    at = at_array.values if at_selection is None else at_array.values[at_selection]
    at_dims = at_array.dims if at_selection is None else selected_dims(at_array.dims, at_selection)
    if at.ndim != 2 or grid.ndim != 2 or array.values.shape != grid.shape:
        raise ValueError(f'level_lookups {path}: needs 2-D at and grid, and a source on the grid\'s shape')
    written = ~unwritten(at, declared_fill_values(settings, at_path))
    hits = (grid[:, None, :] == at[:, :, None]) & written[:, :, None]
    found = hits.sum(axis=2)
    bad = int((written & (found != 1)).sum())
    if bad:
        raise ValueError(
            f'granule {data.granule.id}: {bad} written values of {lookup["at"]} are not found exactly '
            f'once in {lookup["grid"]} (level_lookups {path})'
        )
    values = np.take_along_axis(array.values, hits.argmax(axis=2), axis=1)
    fill = declared_fill_values(settings, path)
    if fill:
        values[~written] = np.asarray(fill[0], dtype=values.dtype)
    elif values.dtype.kind == 'f':
        values[~written] = np.nan
    else:
        raise ValueError(f'level_lookups {path}: an integer source needs a declared fill')
    note = (f'{path} on {lookup["grid"]} read where {lookup["grid"]} equals {lookup["at"]} '
            f'(level_lookups), so on {at_dims[1]}')
    return values, at_dims, note


def selected_dims(dims, selection):
    """A source's dimension names after a selection: an integer drops its axis.

    Args:
        dims (tuple): The names, ``obs`` first.
        selection (tuple): The selection.

    Returns:
        tuple: The names kept.
    """
    if len(selection) > len(dims):
        raise ValueError(f'a selection of {len(selection)} axes on {len(dims)} dimensions {dims}')
    return tuple(name for axis, name in enumerate(dims)
                 if axis >= len(selection) or not isinstance(selection[axis], int))


def selection_note(dims, selection):
    """What a selection kept, for the ``dimension_changes`` attribute.

    Args:
        dims (tuple): The names before it.
        selection (tuple): The selection.

    Returns:
        str: e.g. 'level 0:17 kept'.
    """
    parts = []
    for name, item in zip(dims[1:], selection[1:]):
        if isinstance(item, int):
            parts.append(f'{name} index {item} taken')
        elif item != slice(None):
            parts.append(f'{name} {item.start or 0}:{"" if item.stop is None else item.stop} kept')
    return '; '.join(parts)


def select_source(array, source, data, settings):
    """A source as the key names it: looked up onto another grid, then sliced, if declared.

    Args:
        array (SourceArray): The source as read.
        source (str): The key's source, e.g. 'x[:, 0:17]'.
        data (GranuleData): Its granule, for a lookup's inputs.
        settings (dict): The loaded configuration.

    Returns:
        SourceArray: The array the store holds, with its dimension note.
    """
    path, selection = split_source(source)
    values, dims, notes = array.values, array.dims, []
    if path in (settings.get('level_lookups') or {}):
        values, dims, note = lookup_levels(array, data, settings, path)
        notes.append(note)
    if selection is not None:
        dims = selected_dims(dims, selection)
        values = values[selection]
        note = selection_note(array.dims if not notes else dims, selection)
        if note:
            notes.append(note)
    if not notes:
        return array
    base = '' if array.dimension_note == 'none' else f'{array.dimension_note}; '
    return array._replace(values=values, dims=dims, dimension_note=base + '; '.join(notes))
