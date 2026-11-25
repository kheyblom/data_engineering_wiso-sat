"""Evidence that renamed gridded stores hold what they held before the rename.

Written for the TROPOMI 0.25 degree stores, renamed on 2026-11-25 to carry
their set (``v_8_1.day...`` -> ``v_8_1.clear_or_low_cloud.day...``; user
decision, W1 of the isotopes_transpiration handoff). From gridding/:

    uv run python tools/survey/rename_evidence.py record --config CONFIG --old-set '' --out BEFORE.json
    (mv each store to its new name; finalize --relocate, --text)
    uv run python tools/survey/rename_evidence.py check --config CONFIG --before BEFORE.json

The config gives the new names (its ``store_set``); ``--old-set`` is the
token the stores carried before ('' for none). Read only, login node: it
lists the ``chunks/`` and ``manifests/`` directories of each store (~60k
files for the 34 TROPOMI stores) and reads no chunk.

``record`` (before the rename, at the old names) writes, per store: its tags
and their snapshots, the head of main, every array's shape, dtype and chunk
shape, and the name and size of every file under ``chunks/`` and
``manifests/``.

``check`` (after, at the new names) requires, per store:

- the old name is gone and the new one exists;
- the same tags on the same snapshots, and the old head still in main's
  ancestry;
- the same arrays with the same shape, dtype and chunks;
- every chunk and manifest file of before, at the same size, and no new
  chunk file (a commit that changes attributes writes no chunk);
- an icechunk diff from each tag to main that changes no array and no chunk
  (only group attributes).

A mv within one Lustre directory is a rename(2): it moves no data, so this
is the record that nothing else happened, not a test of the filesystem.
"""
import argparse
import json
import os
import sys

import icechunk  # type: ignore
import zarr  # type: ignore

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from finalize_grid_wisosat import store_paths  # noqa: E402
from utils import config, stores  # noqa: E402

icechunk.set_logs_filter('error')
CONTENT = ('chunks', 'manifests')


def old_path(settings, path, old_set):
    """The store's name before the rename: its set token replaced by ``old_set`` ('' for none)."""
    token = config.version_token(settings)
    new = f'.{token}.{settings["store_set"]}.'
    old = f'.{token}.{old_set}.' if old_set else f'.{token}.'
    directory, name = os.path.split(path)
    assert name.count(new) == 1, name
    return os.path.join(directory, name.replace(new, old))


def files(path):
    """Relative path -> size of every file under the store's content directories."""
    listing = {}
    for top in CONTENT:
        for directory, _, names in os.walk(os.path.join(path, top)):
            for name in names:
                full = os.path.join(directory, name)
                listing[os.path.relpath(full, path)] = os.stat(full).st_size
    return listing


def describe(path):
    """Tags, head, arrays and content files of one store."""
    repository = stores.open_repository(path)
    group = zarr.open_group(repository.readonly_session(branch=stores.BRANCH).store, mode='r')
    return {
        'tags': {tag: repository.lookup_tag(tag) for tag in sorted(repository.list_tags())},
        'head': repository.lookup_branch(stores.BRANCH),
        'arrays': {name: [list(array.shape), str(array.dtype), list(array.chunks)]
                   for name, array in sorted(group.arrays())},
        'files': files(path),
    }


def record(settings, old_set, out):
    evidence = {}
    for layout in config.LAYOUTS:
        for _, _, _, path in store_paths(settings, layout):
            before = old_path(settings, path, old_set)
            evidence[path] = {'old_path': before, **describe(before)}
            print(f'{os.path.basename(before)}: {len(evidence[path]["files"])} files, '
                  f'tags {list(evidence[path]["tags"])}', flush=True)
    with open(out, 'w') as handle:
        json.dump(evidence, handle, indent=1)
    print(f'{len(evidence)} stores recorded in {out}')


def check(settings, before_file):
    with open(before_file) as handle:
        evidence = json.load(handle)
    failures = 0
    for path, before in evidence.items():
        name = os.path.basename(path)
        problems = []
        if os.path.exists(before['old_path']):
            problems.append('old name still exists')
        if not os.path.isdir(path):
            print(f'FAIL {name}: missing')
            failures += 1
            continue
        after = describe(path)
        repository = stores.open_repository(path)
        if after['tags'] != before['tags']:
            problems.append(f'tags {before["tags"]} -> {after["tags"]}')
        ancestry = [snapshot.id for snapshot in repository.ancestry(branch=stores.BRANCH)]
        if before['head'] not in ancestry:
            problems.append('old head not in main ancestry')
        if after['arrays'] != before['arrays']:
            problems.append('arrays differ')
        lost = [key for key, size in before['files'].items() if after['files'].get(key) != size]
        new_chunks = [key for key in after['files'] if key not in before['files'] and key.startswith('chunks')]
        if lost:
            problems.append(f'{len(lost)} content files missing or resized, e.g. {lost[:3]}')
        if new_chunks:
            problems.append(f'{len(new_chunks)} new chunk files, e.g. {new_chunks[:3]}')
        for tag in before['tags']:
            diff = repository.diff(from_tag=tag, to_branch=stores.BRANCH)
            if diff.updated_chunks or diff.updated_arrays or diff.new_arrays or diff.deleted_arrays \
                    or diff.moved_nodes or diff.new_groups or diff.deleted_groups:
                problems.append(f'diff {tag} -> main changes more than group attributes: {diff}')
        new_files = len(after['files']) - len(before['files'])
        if problems:
            failures += 1
            print(f'FAIL {name}: ' + '; '.join(problems))
        else:
            print(f'ok {name}: {len(before["files"])} content files unchanged ({new_files} new manifest files), '
                  f'{len(before["arrays"])} arrays, tags {list(before["tags"])} on the same snapshots, '
                  f'tag -> main changes group attributes only', flush=True)
    print(f'{len(evidence)} stores checked, {failures} failures')
    sys.exit(1 if failures else 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('action', choices=('record', 'check'))
    parser.add_argument('--config', required=True)
    parser.add_argument('--old-set', default='')
    parser.add_argument('--out')
    parser.add_argument('--before')
    args = parser.parse_args()
    settings = config.load_config(args.config)
    if args.action == 'record':
        record(settings, args.old_set, args.out)
    else:
        check(settings, args.before)


if __name__ == '__main__':
    main()
