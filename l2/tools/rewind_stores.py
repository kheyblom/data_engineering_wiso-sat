"""Rewind every store of a config to the commit that held its first N granules.

Written 2026-10-17 for the TROPOMI production stores. A rule change (TESTING.md
finding 10) altered which rows are observations in granule 7042 onward, which
shifts every later observation, so the stores are rewound to the last commit
before that granule and the build resumes from there. The commits after it
stay on disk, unreferenced, until ``finalize_wisosat_zarr.py --gc``, so a rewind
can be undone with the tips this script prints and saves.

Per store, the target commit is found by its message ("write granules
<first id>..<last id> (n)") and then confirmed by opening it: its granule index
must hold exactly N entries, equal to the first N of the current index, and its
obs length must be the sum of their counts. Every store must reach the same N,
so they stay on one obs axis.

Run from the repo root; nothing changes without ``--apply``:

    uv run python tools/rewind_stores.py --config <config> --granules N [--apply]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os

import numpy as np
import zarr

from utils.path_utils import load_config, log_path, run_stores, store_path
from utils.zarr_utils import BRANCH, open_existing_repository


def open_group(repository, snapshot_id=None):
    """A read-only zarr group of a store, at its branch tip or a snapshot."""
    if snapshot_id is None:
        session = repository.readonly_session(branch=BRANCH)
    else:
        session = repository.readonly_session(snapshot_id=snapshot_id)
    return zarr.open_group(session.store, mode='r')


def find_target(repository, n_granules):
    """The snapshot holding exactly the first ``n_granules``, confirmed.

    Args:
        repository (icechunk.Repository): The store.
        n_granules (int): How many granules to keep.

    Returns:
        tuple: (current tip snapshot id, target snapshot id, its message,
            its obs length).

    Raises:
        ValueError: If no commit ends at that granule, or it does not check out.
    """
    tip = open_group(repository)
    ids = tip['granule_id'][:]
    if not 0 < n_granules < ids.size:
        raise ValueError(f'the store holds {ids.size} granules; cannot keep {n_granules}')
    last_id = str(ids[n_granules - 1])
    ancestry = list(repository.ancestry(branch=BRANCH))
    matches = [s for s in ancestry if s.message.startswith('write granules ')
               and f'..{last_id} (' in s.message]
    if len(matches) != 1:
        raise ValueError(f'{len(matches)} commits end at granule {last_id}; expected 1')
    target = matches[0]

    group = open_group(repository, target.id)
    kept = group['granule_id'][:]
    counts = group['granule_obs_count'][:]
    data = [name for name in group.array_keys() if not name.startswith('granule')]
    n_obs = group[data[0]].shape[0]
    if kept.size != n_granules or not np.array_equal(kept, ids[:n_granules]):
        raise ValueError(f'commit {target.id} does not hold the first {n_granules} granules')
    if int(counts.sum()) != n_obs:
        raise ValueError(f'commit {target.id}: obs length {n_obs} != index sum {int(counts.sum())}')
    return ancestry[0].id, target.id, target.message, n_obs


def main():
    parser = argparse.ArgumentParser(description='rewind every store of a config to its first N granules.')
    parser.add_argument('--config', required=True, help='Path to YAML configuration file.')
    parser.add_argument('--granules', type=int, required=True, help='Granules to keep.')
    parser.add_argument('--apply', action='store_true', help='Reset the branches; without it, report only.')
    args = parser.parse_args()

    settings = load_config(args.config)
    plan = {}
    for store in run_stores(settings):
        repository = open_existing_repository(store_path(settings, store))
        tip, target, message, n_obs = find_target(repository, args.granules)
        plan[store] = {'tip': tip, 'target': target, 'message': message, 'n_obs': n_obs}
        print(f'{store}: tip {tip} -> {target} ({message!r}, {n_obs} obs)')

    lengths = {entry['n_obs'] for entry in plan.values()}
    if len(lengths) != 1:
        raise SystemExit(f'the stores would rewind to different obs lengths: {sorted(lengths)}')
    if not args.apply:
        print('dry run: nothing changed; add --apply to reset the branches')
        return

    # saved before anything moves, so every rewind can be undone until --gc
    record = log_path(settings, 'rewind_').replace('.log', '.json')
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    history = json.load(open(record)) if os.path.exists(record) else []
    history.append({'when': stamp, 'granules': args.granules, 'stores': plan})
    with open(record, 'w', encoding='utf-8') as handle:
        json.dump(history, handle, indent=1)
    print(f'tips saved to {record}')

    for store, entry in plan.items():
        repository = open_existing_repository(store_path(settings, store))
        repository.reset_branch(BRANCH, entry['target'])
        print(f'{store}: reset to {entry["target"]}')
    print('done')


if __name__ == '__main__':
    main()
