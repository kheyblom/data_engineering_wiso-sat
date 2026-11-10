"""Parse the gridding key and check it against the authoritative nomenclature.

Two markdown files, both machine read:
- ``nomenclature-key_grid.md`` (this folder): each gridded quantity's
  canonical name, units, kind (sum or statistic) and dtype; the units each
  input must carry; and the frequency tokens;
- ``nomenclature_data.md`` (the style guide's key, path in config): the
  rows those names must match exactly.

The mapping lives only in the key (root CLAUDE.md: never restate it in
Python); code refers to quantities by their key name ('delta_d').
"""
import functools
from pathlib import Path

from utils.config import GRIDDING_ROOT

KEY_PATH = GRIDDING_ROOT / 'nomenclature-key_grid.md'


def _tables(path):
    """Every markdown table of a file, by the heading above it.

    Returns:
        dict: heading -> list of row dicts (header cells as keys, backticks stripped).
    """
    tables, heading, header = {}, None, None
    for line in Path(path).read_text().splitlines():
        if line.startswith('#'):
            heading, header = line.lstrip('#').strip(), None
            continue
        if not line.startswith('|'):
            header = None
            continue
        cells = [cell.strip().strip('`') for cell in line.strip().strip('|').split('|')]
        if header is None:
            header = cells
            tables.setdefault(heading, [])
        elif not all(set(cell) <= set('-: ') for cell in cells):
            tables[heading].append(dict(zip(header, cells)))
    return tables


@functools.cache
def quantities():
    """The Quantity Key: quantity -> dict (canonical_name, canonical_units, kind, dtype, formula), in key order."""
    return {row['quantity']: row for row in _tables(KEY_PATH)['Quantity Key']}


def quantity_names(kind=None):
    """Quantity names in key order, optionally only 'sum' or 'statistic'."""
    return [name for name, row in quantities().items() if kind is None or row['kind'] == kind]


@functools.cache
def input_units():
    """The Input Key: input -> the units its L2 variable must carry."""
    return {row['input']: row['canonical_units'] for row in _tables(KEY_PATH)['Input Key']}


@functools.cache
def _authority(path):
    tables = _tables(path)
    variables = {row['canonical_name']: row for row in tables['Data Variable Key']}
    frequencies = {row['canonical_name']: row for row in tables['Temporal Frequency Key']}
    return variables, frequencies


def authority_attrs(settings, quantity):
    """``long_name`` and ``units`` of a quantity, from nomenclature_data.md."""
    variables, _ = _authority(settings['nomenclature_data'])
    row = variables[quantities()[quantity]['canonical_name']]
    return {'long_name': row['long_name'], 'units': row['canonical_units']}


def frequency_long_name(settings, frequency):
    """The Temporal Frequency Key's long name for a token ('daily average')."""
    _, frequencies = _authority(settings['nomenclature_data'])
    return frequencies[frequency]['long_name']


def check(settings, frequencies):
    """Fail unless every quantity and frequency has an exact row in nomenclature_data.md.

    Args:
        settings (dict): The config (``nomenclature_data`` is the path).
        frequencies (list): The frequency tokens the config builds.

    Raises:
        ValueError: Naming each missing or mismatched row.
    """
    variables, known = _authority(settings['nomenclature_data'])
    problems = []
    for name, row in quantities().items():
        entry = variables.get(row['canonical_name'])
        if entry is None:
            problems.append(f'{name}: no row {row["canonical_name"]!r}')
        elif entry['canonical_units'] != row['canonical_units']:
            problems.append(f'{name}: key units {row["canonical_units"]!r}, nomenclature '
                            f'{entry["canonical_units"]!r}')
    key_frequencies = {row['frequency'] for row in _tables(KEY_PATH)['Temporal Frequency Key']}
    for frequency in frequencies:
        if frequency not in known:
            problems.append(f'frequency {frequency!r}: no row in the Temporal Frequency Key')
        if frequency not in key_frequencies:
            problems.append(f'frequency {frequency!r}: not in nomenclature-key_grid.md')
    if problems:
        raise ValueError('nomenclature check failed:\n  ' + '\n  '.join(problems))
