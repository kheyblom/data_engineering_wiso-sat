"""Load a gridding config and derive every name and path from it.

One config = one product: its L2 stores (at one tag), its gridding inputs
and selection, and the grids and frequencies to build. Everything a build
writes is named from here, never in code (root CLAUDE.md, carried over from
GLEAM): store paths, the version token, the log file.

Store names follow the style guide's
``<data_source>.<version>.<temporal_frequency>.<grid_name>.<variable>.zarr``
with data source ``wisosat.<product>`` (as the L2 stores), under a
``spatial/`` or ``temporal/`` parent directory: the two layouts share a
basename (exception carried from GLEAM/MSWEP, approved for the WISO-SAT
grids 2026-11-10).
"""
import importlib
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml  # type: ignore

LOG = logging.getLogger(__name__)

# gridding/, found from this file rather than the cwd
GRIDDING_ROOT = Path(__file__).resolve().parents[1]
LAYOUTS = ('spatial', 'temporal')
GEOLOCATION = 'geolocation'
# the keys every config must carry; the rest have defaults below
REQUIRED = ('product', 'version', 'l2', 'directories', 'output_conventions', 'nomenclature_data',
            'log_file', 'inputs', 'selection', 'grids', 'frequencies', 'chunks', 'attrs')
VERSION_PART_RE = re.compile(r'[A-Za-z]+|\d+')


def load_config(path):
    """Read a YAML config and check its required keys.

    Args:
        path (str | os.PathLike): The config file.

    Returns:
        dict: The settings, with ``config_path`` added.

    Raises:
        ValueError: If a required key is missing.
    """
    with open(path) as handle:
        settings = yaml.safe_load(handle)
    missing = [key for key in REQUIRED if key not in settings]
    if missing:
        raise ValueError(f'{path}: missing config keys {missing}')
    settings['config_path'] = str(path)
    return settings


def format_version(version):
    """The style guide's version token: letters and numbers split by '_'.

    '8.1' -> 'v_8_1'; 'v3.0.1' -> 'v_3_0_1'. A bare number gains the 'v'.

    Args:
        version (str): The version as the source writes it.

    Returns:
        str: The lower-case token.
    """
    parts = VERSION_PART_RE.findall(str(version))
    if not parts or not parts[0].isalpha():
        parts.insert(0, 'v')
    return '_'.join(parts).lower()


def version_token(settings):
    """The version slot of every store name, with any stream appended (``v_1.rs``)."""
    token = format_version(settings['version'])
    stream = settings.get('version_product')
    return f'{token}.{stream}' if stream else token


def source_module(settings):
    """The product module (``products/<source>.py``): selection and input rules."""
    return importlib.import_module(f'products.{settings.get("source", settings["product"])}')


def store_name(settings, frequency, grid_name, variable):
    """A store's basename, without its layout directory."""
    template = settings['output_conventions']['filename']
    return template.format(product=settings['product'], version=version_token(settings),
                           frequency=frequency, grid_name=grid_name, variable=variable)


def store_path(settings, layout, frequency, grid_name, variable):
    """Where a gridded store lives: ``<zarr>/<layout>/<name>``.

    Args:
        settings (dict): The config.
        layout (str): 'spatial' or 'temporal'.
        frequency (str): The frequency token ('day', '3day', 'month').
        grid_name (str): The grid token ('latlon_0p25x0p25').
        variable (str): The canonical variable name.

    Returns:
        str: The store directory.
    """
    if layout not in LAYOUTS:
        raise ValueError(f'layout must be one of {LAYOUTS}, got {layout!r}')
    return os.path.join(settings['directories']['zarr'], layout,
                        store_name(settings, frequency, grid_name, variable))


def l2_tag_text(settings):
    """The L2 tag(s) a config reads at, for the stores' ``source_l2_tag``: one tag, or the exceptions too."""
    l2 = settings['l2']
    others = l2.get('store_tags') or {}
    if not others:
        return l2['tag']
    return f'{l2["tag"]}; ' + '; '.join(f'{store}: {tag}' for store, tag in sorted(others.items()))


def l2_tag(settings, store):
    """The tag one L2 store is read at (``l2.store_tags`` overrides ``l2.tag``)."""
    return (settings['l2'].get('store_tags') or {}).get(store, settings['l2']['tag'])


def l2_store_path(settings, store):
    """Where one L2 store lives (``geolocation`` or a canonical variable)."""
    l2 = settings['l2']
    name = l2['filename'].format(product=settings['product'], version=version_token(settings), store=store)
    return os.path.join(l2['directory'], name)


def log_path(settings, prefix=''):
    """The log file, under ``directories.logs`` (relative to gridding/)."""
    directory = Path(settings['directories'].get('logs', 'logs'))
    if not directory.is_absolute():
        directory = GRIDDING_ROOT / directory
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory / f'{prefix}{settings["log_file"]}')


def setup_logging(settings, prefix=''):
    """Log to stdout and, appending, to the config's log file."""
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in (logging.StreamHandler(sys.stdout), logging.FileHandler(log_path(settings, prefix), mode='a')):
        handler.setFormatter(formatter)
        root.addHandler(handler)
    # icechunk and zarr are chatty at INFO about every chunk
    for name in ('icechunk', 'zarr', 'numcodecs', 'asyncio'):
        logging.getLogger(name).setLevel(logging.WARNING)


def code_revision():
    """HEAD of the repository, short form, or 'unknown' outside git."""
    try:
        return subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=GRIDDING_ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def uncommitted_changes():
    """``git status --porcelain`` of gridding/ only.

    Only gridding/ reaches a grid (user decision 2026-11-10, as L2 checks
    only l2/): uncommitted docs or l2 work never blocks a build.
    """
    result = subprocess.run(['git', 'status', '--porcelain', '--', '.'], cwd=GRIDDING_ROOT, check=True,
                            capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line.strip()]


def check_clean_tree(settings):
    """Refuse to write unless gridding/ is committed, so ``@ <revision>`` names the code.

    Only fixture configs may set ``allow_dirty_tree``; the fixture test
    enforces that.

    Returns:
        str: The revision to stamp on every commit ('<rev>-dirty' when allowed).

    Raises:
        RuntimeError: If the tree is dirty and the config does not allow it.
    """
    revision = code_revision()
    changes = uncommitted_changes()
    if not changes:
        return revision
    if settings.get('allow_dirty_tree'):
        LOG.warning(f'gridding/ has {len(changes)} uncommitted change(s); allowed by this config')
        return f'{revision}-dirty'
    raise RuntimeError(
        f'gridding/ has uncommitted changes ({len(changes)}); commit before building so every store '
        f'commit names the code that wrote it:\n' + '\n'.join(changes[:20])
    )
