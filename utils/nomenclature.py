"""A product's nomenclature key, read from the markdown file that documents it.

The style guide requires each project to keep a
``nomenclature-key_<dataset_source>.md`` mapping its original names, units and
temporal frequency onto the authoritative ``nomenclature_data.md``. Here there
is one key per product, ``nomenclature-key_<product>.md`` at the repo root, and
this module parses it rather than restating it in Python. So there is one place
the mapping is written down and no way for the documentation and the stores to
disagree.

Ported from ``data_engineering_mswep/utils/nomenclature.py``. What differs:

- **The key is chosen by product**, since one codebase serves every WISO-SAT
  product: the config's ``source`` where it sets one (GOSAT-2 reads GOSAT's
  key), else its ``product``.
- **The variable key carries a real unit conversion**, which MSWEP never
  needed. ``unit_conversion`` is parsed into a factor by ``conversion_factor``,
  so the multiplier a store was built with is the one the key documents.
- **A coordinate key** maps the geolocation store's ``time``/``lat``/``lon``
  (and TROPOMI's pixel corners) onto their source variables. A profile
  product's ``pressure`` is a variable store, not a coordinate (user decision
  2026-10-19).
  ``nomenclature_data.md`` has no coordinate rows, so these are not canonical
  names; they follow the gridded stores. A coordinate's ``unit_conversion`` is
  ``decoded`` for time, or parsed like a variable's.
- **Configs and stores name variables canonically.** The original name is the
  HDF5 path in the source file, which is no name for a store, so lookups run
  from the canonical side.
- **A source may be sliced** (added 2026-10-28 for TROPESS v2, shaped for
  TES; ``docs/products/tropess.md`` V9, D2): ``original_variable_name`` is a
  path, optionally followed by a numpy-style selection with ``:`` for the
  observation axis, e.g. ``x[:, 0:17]`` or ``AveragingKernel[:, 0:17, 17:34]``.
  One source can so feed several canonical names, one per slice.
- **A matrix store** (N18) holds several canonical arrays that form one
  matrix. An optional "Matrix Store Key" table names the store, its arrays
  (each a row of the variable key) and its long name.
"""

from __future__ import annotations

import functools
import os
import re
from typing import NamedTuple

KEY_FILENAME = 'nomenclature-key_{product}.md'

# A markdown file has no schema, so each table is found by its headers rather
# than its position; prose can then move around the tables without breaking
# the parse
VARIABLE_COLUMNS = frozenset(
    {'original_variable_name', 'canonical_name', 'canonical_units', 'unit_conversion'}
)
COORDINATE_COLUMNS = frozenset({'original_name', 'name', 'units', 'unit_conversion'})
FREQUENCY_COLUMNS = frozenset({'original_frequency_name', 'canonical_name'})
MATRIX_COLUMNS = frozenset({'store', 'arrays', 'canonical_long_name'})

# Constants a unit_conversion may name. N_A is exact by the 2019 SI definition,
# so the factor has no measurement uncertainty to record
CONSTANTS = {'N_A': 6.02214076e23}

# 'x 1000', 'x 1e4 / N_A': a multiplier made of numbers and named constants
# joined by * and /. Deliberately no + or -: an offset conversion would need
# the fill masked before it is applied, and nothing in scope needs one
FACTOR_TOKEN_RE = re.compile(r'\s*([*/]|[A-Za-z_]\w*|\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)')

# 'x', 'observation_ops/averaging_kernel[:, 0:17, 0:17]': a path, then an
# optional selection of integers and start:stop slices, one per axis from the
# observation axis on. No steps or negatives: every slice reads as the range
# of source indices it keeps
SOURCE_RE = re.compile(r'^(?P<path>[^\[\]\s]+)(?:\[(?P<selection>[^\[\]]*)\])?$')
SELECTION_ITEM_RE = re.compile(r'^(?:(?P<index>\d+)|(?P<start>\d*):(?P<stop>\d*))$')


class Variable(NamedTuple):
    """One row of the variable key.

    Attributes:
        original (str): The HDF5 path in the source file, e.g.
            'target_product/deltad'.
        original_units (str): The units the source publishes, as documented.
        canonical (str): The name from nomenclature_data.md.
        units (str): The canonical units.
        long_name (str): The canonical long name.
        unit_conversion (str): The conversion as written in the key.
    """

    original: str
    original_units: str
    canonical: str
    units: str
    long_name: str
    unit_conversion: str


class Coordinate(NamedTuple):
    """One row of the coordinate key.

    Attributes:
        original (str): The HDF5 path in the source file.
        original_units (str): The units the source publishes, as documented.
        name (str): The coordinate's name in the geolocation store.
        units (str): The units it is stored with.
        unit_conversion (str): 'decoded' for a time the reader decodes from
            the source encoding; otherwise 'none' or 'x <factor>', as in the
            variable key.
    """

    original: str
    original_units: str
    name: str
    units: str
    unit_conversion: str


class MatrixStore(NamedTuple):
    """One row of the matrix store key: one store holding a matrix's pieces (N18).

    Attributes:
        store (str): The store's canonical name, e.g.
            'water_vapor_hdo_and_h2o_mole_fraction_dry_air_averaging_kernel_log'.
        arrays (tuple): The canonical names of its arrays, in order; each a
            row of the variable key.
        long_name (str): The matrix's canonical long name.
    """

    store: str
    arrays: tuple
    long_name: str


class Frequency(NamedTuple):
    """One row of the temporal frequency key.

    Attributes:
        original (str): The frequency as the configs spell it.
        canonical (str): The token from nomenclature_data.md, e.g. 'inst'.
        long_name (str): The canonical long name.
    """

    original: str
    canonical: str
    long_name: str


def key_path(product):
    """Path to a product's nomenclature key.

    Args:
        product (str): The product, e.g. 'tropomi'.

    Returns:
        str: Absolute path to ``nomenclature-key_<product>.md`` at the repo root.
    """
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        KEY_FILENAME.format(product=product),
    )


def parse_tables(text):
    """Pull every pipe-delimited markdown table out of a document.

    Args:
        text (str): The markdown document.

    Returns:
        list: One list of row dicts per table, each keyed by column header.
    """
    tables, rows, header = [], [], None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith('|'):
            # any non-table line ends the table that was being read
            if header and rows:
                tables.append(rows)
            rows, header = [], None
            continue
        cells = [cell.strip().strip('`') for cell in stripped.strip('|').split('|')]
        if header is None:
            header = cells
        elif set(''.join(cells)) <= set('-: '):
            continue                    # the |---|---| separator row
        else:
            rows.append(dict(zip(header, cells)))
    if header and rows:
        tables.append(rows)
    return tables


def find_table(tables, columns, path):
    """Pick the one table carrying a given set of columns.

    Args:
        tables (list): Tables as returned by ``parse_tables``.
        columns (frozenset): Column names the wanted table must have.
        path (str): The file the tables came from, for the error message.

    Returns:
        list: The matching table's rows.

    Raises:
        ValueError: If no table has those columns, or more than one does.
    """
    matches = [rows for rows in tables if columns <= set(rows[0])]
    if len(matches) != 1:
        raise ValueError(
            f'expected exactly one table in {path} with columns '
            f'{sorted(columns)}, found {len(matches)}'
        )
    return matches[0]


@functools.lru_cache(maxsize=None)
def read_tables(product):
    """Every table in a product's key.

    Args:
        product (str): The product, e.g. 'tropomi'.

    Returns:
        tuple: The parsed tables and the path they came from.

    Raises:
        FileNotFoundError: If the product has no key.
    """
    path = key_path(product)
    with open(path, 'r', encoding='utf-8') as file:
        return parse_tables(file.read()), path


@functools.lru_cache(maxsize=None)
def variables(product):
    """The variable key, keyed by canonical name.

    Args:
        product (str): The product, e.g. 'tropomi'.

    Returns:
        dict: Canonical name -> :class:`Variable`.

    Raises:
        ValueError: If the table is missing or malformed, a conversion does not
            parse, or two rows share a canonical or original name.
    """
    tables, path = read_tables(product)
    key = {}
    for row in find_table(tables, VARIABLE_COLUMNS, path):
        variable = Variable(
            original=row['original_variable_name'],
            original_units=row.get('original_units', ''),
            canonical=row['canonical_name'],
            units=row['canonical_units'],
            long_name=row['canonical_long_name'],
            unit_conversion=row['unit_conversion'],
        )
        required = (variable.original, variable.canonical, variable.units,
                    variable.long_name, variable.unit_conversion)
        if not all(required):
            raise ValueError(f'incomplete row for {variable.canonical!r} in {path}')
        # parsed now rather than at build time, so a typo in the key fails
        # before any file is opened
        conversion_factor(variable.unit_conversion)
        split_source(variable.original)
        # a collision would point two stores at one name, and the second build
        # would overwrite the first
        if variable.canonical in key:
            raise ValueError(f'two rows map onto {variable.canonical!r} in {path}')
        key[variable.canonical] = variable

    # one canonical name per source slice: a source may feed several names,
    # but one slice of it only one
    originals = [entry.original.replace(' ', '') for entry in key.values()]
    if len(set(originals)) != len(originals):
        raise ValueError(f'one source slice maps onto two canonical names in {path}')
    return key


@functools.lru_cache(maxsize=None)
def split_source(original):
    """A key's ``original_variable_name`` as a source path and a selection.

    Args:
        original (str): e.g. 'x', or 'x[:, 0:17]'.

    Returns:
        tuple: ``(path, selection)``: the source path, and a tuple of ``slice``
            and ``int`` per axis from the observation axis on, or None where
            the whole source is meant.

    Raises:
        ValueError: If the text does not parse, or the selection does not
            keep the whole observation axis.
    """
    match = SOURCE_RE.match(original.strip())
    if match is None:
        raise ValueError(f'cannot parse the source {original!r}')
    if match['selection'] is None:
        return match['path'], None
    items = []
    for text in match['selection'].split(','):
        item = SELECTION_ITEM_RE.match(text.strip())
        if item is None:
            raise ValueError(f'cannot parse {text.strip()!r} in the source {original!r}')
        if item['index'] is not None:
            items.append(int(item['index']))
        else:
            items.append(slice(int(item['start']) if item['start'] else None,
                               int(item['stop']) if item['stop'] else None))
    # every observation is kept: a slice selects within an observation
    if items[0] != slice(None, None):
        raise ValueError(f'the source {original!r} must keep the whole observation axis, written ":"')
    return match['path'], tuple(items)


def source_path(original):
    """The source path of a key's ``original_variable_name``, without its selection.

    Args:
        original (str): e.g. 'x[:, 0:17]'.

    Returns:
        str: e.g. 'x'.
    """
    return split_source(original)[0]


@functools.lru_cache(maxsize=None)
def matrix_stores(product):
    """The matrix store key, keyed by store name; empty where the key has none.

    Args:
        product (str): The product, e.g. 'tropess_v2'.

    Returns:
        dict: Store canonical name -> :class:`MatrixStore`.

    Raises:
        ValueError: If there is more than one such table, a row is incomplete,
            a store is also a variable row, or an array is not a variable row,
            is listed twice, or belongs to two stores.
    """
    tables, path = read_tables(product)
    matches = [rows for rows in tables if MATRIX_COLUMNS <= set(rows[0])]
    if not matches:
        return {}
    if len(matches) > 1:
        raise ValueError(f'expected at most one matrix store table in {path}, found {len(matches)}')
    key = variables(product)
    stores, owner = {}, {}
    for row in matches[0]:
        arrays = tuple(name.strip().strip('`').strip() for name in row['arrays'].split(','))
        entry = MatrixStore(store=row['store'], arrays=arrays, long_name=row['canonical_long_name'])
        if not entry.store or not entry.long_name or not all(arrays):
            raise ValueError(f'incomplete matrix store row for {entry.store!r} in {path}')
        if entry.store in key or entry.store in stores:
            raise ValueError(f'{entry.store!r} is named twice as a store in {path}')
        if len(set(arrays)) != len(arrays):
            raise ValueError(f'matrix store {entry.store!r} lists an array twice in {path}')
        for name in arrays:
            if name not in key:
                raise ValueError(f'matrix store {entry.store!r} array {name!r} has no variable row in {path}')
            if name in owner:
                raise ValueError(f'{name!r} is an array of both {owner[name]!r} and {entry.store!r} in {path}')
            owner[name] = entry.store
        stores[entry.store] = entry
    return stores


@functools.lru_cache(maxsize=None)
def coordinates(product):
    """The coordinate key, keyed by the coordinate's store name.

    Args:
        product (str): The product, e.g. 'tropomi'.

    Returns:
        dict: Name ('time', 'lat', 'lon', ...) -> :class:`Coordinate`.

    Raises:
        ValueError: If the table is missing, a row is incomplete, or time, lat
            or lon is absent: the style guide requires all three.
    """
    tables, path = read_tables(product)
    key = {}
    for row in find_table(tables, COORDINATE_COLUMNS, path):
        coordinate = Coordinate(
            original=row['original_name'],
            original_units=row.get('original_units', ''),
            name=row['name'],
            units=row['units'],
            unit_conversion=row['unit_conversion'],
        )
        if not all((coordinate.original, coordinate.name, coordinate.units,
                    coordinate.unit_conversion)):
            raise ValueError(f'incomplete coordinate row {coordinate.name!r} in {path}')
        # parsed now, as for variables, so a typo fails before any file is opened
        coordinate_factor(coordinate)
        key[coordinate.name] = coordinate
    missing = {'time', 'lat', 'lon'} - set(key)
    if missing:
        raise ValueError(f'the coordinate key in {path} lacks {sorted(missing)}')
    return key


@functools.lru_cache(maxsize=None)
def frequencies(product):
    """The temporal frequency key, keyed by the name the configs spell.

    Args:
        product (str): The product, e.g. 'tropomi'.

    Returns:
        dict: Original frequency name -> :class:`Frequency`.

    Raises:
        ValueError: If the table is missing or a row is incomplete.
    """
    tables, path = read_tables(product)
    key = {}
    for row in find_table(tables, FREQUENCY_COLUMNS, path):
        frequency = Frequency(
            original=row['original_frequency_name'],
            canonical=row['canonical_name'],
            long_name=row['canonical_long_name'],
        )
        if not all(frequency):
            raise ValueError(f'incomplete row for {frequency.original!r} in {path}')
        key[frequency.original] = frequency
    return key


def variable(product, canonical):
    """The key row for a canonical variable name.

    Args:
        product (str): The product, e.g. 'tropomi'.
        canonical (str): The canonical name.

    Returns:
        Variable: The row.

    Raises:
        KeyError: If the product's key has no such row. The style guide calls
            for a new entry in nomenclature_data.md rather than a guess, so this
            is deliberately fatal.
    """
    key = variables(product)
    if canonical not in key:
        raise KeyError(
            f'{canonical!r} has no row in {key_path(product)}; add it there, and '
            f'to nomenclature_data.md first if it is not already in that key'
        )
    return key[canonical]


def canonical_frequency(product, original):
    """Canonical token for a temporal frequency.

    Args:
        product (str): The product, e.g. 'tropomi'.
        original (str): The frequency as the config spells it.

    Returns:
        str: The canonical token, e.g. 'inst'.

    Raises:
        KeyError: If the frequency has no row in the key.
    """
    key = frequencies(product)
    if original not in key:
        raise KeyError(
            f'{original!r} has no row in the temporal frequency key of '
            f'{key_path(product)}'
        )
    return key[original].canonical


def coordinate_factor(coordinate):
    """The multiplier a coordinate's ``unit_conversion`` describes.

    Args:
        coordinate (Coordinate): A coordinate key row.

    Returns:
        float | None: The factor, or None for 'none' and for a decoded time,
            whose conversion is the reader's ``decode_time``.

    Raises:
        ValueError: If the conversion does not parse.
    """
    if coordinate.unit_conversion == 'decoded':
        return None
    return conversion_factor(coordinate.unit_conversion)


def conversion_factor(text):
    """Parse a ``unit_conversion`` into the multiplier it describes.

    Args:
        text (str): 'none', or 'x ' followed by numbers and named constants
            joined by '*' and '/', e.g. 'x 1e4 / N_A'.

    Returns:
        float | None: The factor, or None for 'none'.

    Raises:
        ValueError: If the text does not parse. A conversion the code cannot
            read must not be skipped quietly, or a store would carry the source
            units under a canonical label.
    """
    if text == 'none':
        return None
    if not text.startswith('x '):
        raise ValueError(f"cannot parse unit_conversion {text!r}; expected 'none' or 'x <factor>'")

    body = text[2:]
    tokens, position = [], 0
    while position < len(body):
        match = FACTOR_TOKEN_RE.match(body, position)
        if match is None:
            raise ValueError(f'cannot parse unit_conversion {text!r} at {body[position:]!r}')
        tokens.append(match.group(1))
        position = match.end()
        # trailing whitespace has no token to match
        if not body[position:].strip():
            break

    # operands and operators must alternate, starting and ending on an operand,
    # so 'x 2 3' or 'x / 4' fail rather than being read some unintended way
    operands, operators = tokens[0::2], tokens[1::2]
    if (
        not operands
        or len(operands) != len(operators) + 1
        or any(token not in '*/' for token in operators)
        or any(token in ('*', '/') for token in operands)
    ):
        raise ValueError(f'cannot parse unit_conversion {text!r}')

    values = []
    for token in operands:
        if token in CONSTANTS:
            values.append(CONSTANTS[token])
        elif token[0].isdigit():
            values.append(float(token))
        else:
            raise ValueError(f'unknown constant {token!r} in unit_conversion {text!r}')

    # left to right, in float64, so the factor is the one the text spells
    factor = values[0]
    for operator, value in zip(operators, values[1:]):
        factor = factor * value if operator == '*' else factor / value
    return factor
