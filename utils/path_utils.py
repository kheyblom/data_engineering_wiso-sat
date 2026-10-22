"""Configuration loading, store naming and the stores a run builds.

One config drives one product, and one run builds several stores of it: the
``geolocation`` store, which every run includes, plus one store per variable
the config lists. Each store is its own icechunk repository, named per the
style guide's file naming convention:

```
<zarr>/wisosat.<product>.<version>.<frequency>.<grid_name>.<variable>.zarr
<zarr>/wisosat.tropomi.v_8_1.inst.native_swath.water_vapor_column_delta_d.zarr
```

``wisosat.<product>`` is the data source (decided 2026-10-14). The version is
the processor version the source files carry in their own attributes, declared
in the config so the store can be named before a file is opened; the build
checks every granule against it. There is no product token.

Variables are named canonically in the config, since they name stores.
``source`` names the product whose reader and nomenclature key a config uses,
when that is not its own: GOSAT-2 shares GOSAT's file format, so its config
sets ``product: gosat2`` (store names) and ``source: gosat`` (user decision
2026-10-22). Raw paths are given whole in ``directories.raw`` rather than assembled: the
products' trees share no layout, and the reader owns everything below that
root.
"""

from __future__ import annotations

import importlib
import os
import re

import yaml # type: ignore

from .nomenclature import canonical_frequency, variable as key_variable, variables

# The variable slot of the geolocation store, per the style guide
GEOLOCATION = 'geolocation'

# Canonical names that start with this are quality flags. The style guide
# requires them in every production run, so a config cannot leave one out
QUALITY_FLAG_PREFIX = 'quality_flags'

# 'V5.3.4c-test' -> runs of letters or of digits, separated per the guide
VERSION_PART_RE = re.compile(r'[A-Za-z]+|\d+')


def load_config(file_path: str) -> dict:
    """Load YAML configuration from a file.

    Args:
        file_path (str): Path to the YAML configuration file.

    Returns:
        dict: The loaded configuration.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    return config


def format_version(version):
    """Rewrite a version per the style guide's version naming convention.

    Letters and numbers are separated by underscores, decimals and hyphens
    become underscores, and the whole is lowercase, as every filename component
    must be. A version without a leading 'v' gets one, so the slot reads as a
    version wherever it appears.

    Args:
        version (str): The version as written in the config, e.g. '8.1'.

    Returns:
        str: e.g. '8.1' -> 'v_8_1', 'v3.0.1' -> 'v_3_0_1',
            'V5.3.4c-test' -> 'v_5_3_4_c_test'.

    Raises:
        ValueError: If the version has no letters or digits at all.
    """
    parts = [part.lower() for part in VERSION_PART_RE.findall(str(version))]
    if not parts:
        raise ValueError(f'cannot parse version {version!r}')
    if parts[0] != 'v':
        parts.insert(0, 'v')
    return '_'.join(parts)


def source_product(settings):
    """The product whose reader and nomenclature key a config uses.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        str: ``source`` if the config sets it, else ``product``.
    """
    return settings.get('source') or settings['product']


def load_reader(settings):
    """Import the reader module for the configured source.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        module: ``products.<source>``.
    """
    return importlib.import_module(f'products.{source_product(settings)}')


def run_variables(settings):
    """The canonical variables this run builds stores for, in config order.

    Args:
        settings (dict): The loaded configuration; ``variables`` lists them.

    Returns:
        list: Canonical names, without the geolocation store.

    Raises:
        KeyError: If a listed variable has no row in the product's key.
        ValueError: If the list is empty or repeats a name, or omits a quality
            flag the key carries.
    """
    names = list(settings.get('variables') or [])
    if not names:
        raise ValueError('config lists no variables')
    if len(set(names)) != len(names):
        raise ValueError(f'config lists a variable twice: {names}')
    for name in names:
        # raises with a pointer to the key when the row is missing
        key_variable(source_product(settings), name)

    flags = [name for name in variables(source_product(settings)) if name.startswith(QUALITY_FLAG_PREFIX)]
    missing = [name for name in flags if name not in names]
    if missing:
        raise ValueError(
            f'config omits {missing}; the style guide requires quality flags in '
            f'every production run'
        )
    return names


def run_stores(settings):
    """Every store a run writes: geolocation first, then each variable.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        list: Store variable slots, e.g. ['geolocation', 'water_vapor_column_delta_d', ...].
    """
    return [GEOLOCATION] + run_variables(settings)


def template_fields(settings, store):
    """Fields a ``str.format`` template in the config may reference.

    Every scalar at the top level of the config, plus what is derived from it.
    Pairs follow MSWEP's rule: the plain field is the canonical spelling used in
    store names, and the ``_label`` beside it is what the source writes.

    - ``version`` is the filename form (``v_8_1``); ``version_label`` is the
      config's own (``8.1``).
    - ``frequency`` is the canonical token (``inst``); ``temporal_resolution``
      is the config's word for it (``observation``).
    - ``variable`` is the store's variable slot: a canonical name, or
      ``geolocation``. ``variable_label`` is the source path, or ``geolocation``.

    Args:
        settings (dict): The loaded configuration.
        store (str): The store's variable slot.

    Returns:
        dict: Field name -> value.
    """
    fields = {
        key: value
        for key, value in settings.items()
        if isinstance(value, (str, int, float))
    }
    fields.update(settings.get('output_conventions', {}))
    fields['version_label'] = str(settings['version'])
    fields['version'] = format_version(settings['version'])
    fields['frequency'] = canonical_frequency(
        source_product(settings), settings['temporal_resolution']
    )
    fields['variable'] = store
    fields['variable_label'] = (
        store if store == GEOLOCATION else key_variable(source_product(settings), store).original
    )
    return fields


def render(template, fields, name):
    """Render one template string, naming the culprit if a field is unknown.

    Args:
        template (str): The template.
        fields (dict): From ``template_fields``.
        name (str): What is being rendered, for the error message.

    Returns:
        str: The rendered string.

    Raises:
        ValueError: If the template refers to a field the config does not set.
    """
    try:
        return template.format_map(fields)
    except KeyError as error:
        raise ValueError(
            f'{name} refers to {error}, which is not set in the config'
        ) from None


def format_filename(settings, store):
    """Render ``output_conventions.filename`` for one store.

    Args:
        settings (dict): The loaded configuration.
        store (str): The store's variable slot.

    Returns:
        str: e.g. 'wisosat.tropomi.v_8_1.inst.native_swath.geolocation.zarr'.
    """
    template = settings['output_conventions']['filename']
    return render(template, template_fields(settings, store), 'the filename template')


def format_attrs(settings, store, section='attrs'):
    """Render a config attribute section for one store.

    Each string is a template over ``template_fields``, so attribute text can
    say ``{variable}`` or ``{version_label}`` instead of repeating them.

    Args:
        settings (dict): The loaded configuration.
        store (str): The store's variable slot.
        section (str): ``'attrs'`` for global attributes, shared by every store
            of the product; ``'variable_attrs'`` for a mapping of store
            variable -> attributes, of which only this store's entry is
            returned.

    Returns:
        dict: Attribute name -> value, empty if there is nothing to set.
    """
    fields = template_fields(settings, store)
    values = settings.get(section) or {}
    if section == 'variable_attrs':
        values = values.get(store) or {}
    return {
        name: render(value, fields, f'attribute {name!r}') if isinstance(value, str) else value
        for name, value in values.items()
    }


def store_path(settings, store):
    """Full path of one store.

    Args:
        settings (dict): The loaded configuration.
        store (str): The store's variable slot.

    Returns:
        str: ``<directories.zarr>/<filename>``.
    """
    return os.path.join(settings['directories']['zarr'], format_filename(settings, store))


def log_path(settings, prefix=''):
    """Path of a log file named after the config's ``log_file``.

    Args:
        settings (dict): The loaded configuration.
        prefix (str): e.g. 'verify_', so each entry point's forensics stay in
            their own file.

    Returns:
        str: The path.
    """
    return os.path.join(settings['directories']['logs'], f'{prefix}{settings["log_file"]}')
