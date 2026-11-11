"""Finalize the gridded stores of one config and layout: the only mutator after a build.

    uv run python finalize_grid_wisosat.py --config CONFIG --layout spatial --status
    uv run python finalize_grid_wisosat.py --config CONFIG --layout spatial --attrs [--apply]
    uv run python finalize_grid_wisosat.py --config CONFIG --layout spatial --tag NAME [--apply]
    uv run python finalize_grid_wisosat.py --config CONFIG --layout spatial --gc [--apply]
    uv run python finalize_grid_wisosat.py --config CONFIG --layout spatial --relocate [--apply]

One action per invocation; nothing is written without ``--apply`` (dry run
first). The order is load-bearing, as in GLEAM and l2/: ``--attrs``, then
``--tag``, then ``--gc``. Tags are immutable, so a tag made before the
attributes would name a store that does not describe itself; ``--tag``
refuses a store without them.

``--relocate`` is for stores moved on disk after their build (2026-11-11:
``grid/<product>/`` to ``zarr/<product>/l3/``, user decision). Three root
attributes hold absolute paths: ``related_store``, ``source_l2_stores`` and,
on temporal stores, ``rechunked_from``. It rewrites them from the config as
the build would now write them and, on a finalized store, appends the move
to ``history``. Values, verification and tags are untouched, so a tag made
before the move still names the old paths; a store already matching is
left alone.

``--attrs`` writes ``history``, ``date_created``, ``verification`` and the
time coverage, and only for stores a passing verify run of this layout
covered (``logs/verify_<log_file>``: its ``stores:`` line, then ``0
failures`` and ``stores verified``). It merges into the root group's
attributes; it never touches variable attributes. Once written, ``history``
is not regenerated.

Tag names: ``<version>-<grid_name>-<frequency>-<layout>-verified-YYYYMMDD``
is a reasonable form; the name is the caller's.
"""
import argparse
import datetime
import logging
import os
import re
import sys

import icechunk  # type: ignore
import numpy as np
import zarr  # type: ignore

from utils import config, nomenclature, periods, stores
from utils.grids import from_spec

LOG = logging.getLogger('finalize_grid_wisosat')
ATTRS_MESSAGE = 'add provenance and discovery attributes'
RELOCATE_MESSAGE = 'rewrite path attributes after a move'
FINAL_ATTRS = ('history', 'date_created', 'verification', 'time_coverage_start', 'time_coverage_end')
LINE_RE = re.compile(r'^(?P<stamp>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ \w+ verify_grid_wisosat: (?P<text>.*)$')
STORES_RE = re.compile(r'^layout: (?P<layout>\w+); phases: \[(?P<phases>[^\]]*)\]; stores: \[(?P<stores>[^\]]*)\]$')
SUMMARY_RE = re.compile(r'^(?P<checks>\d+) checks, (?P<failures>\d+) failures$')

icechunk.set_logs_filter('error')


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--config', required=True)
    parser.add_argument('--layout', choices=config.LAYOUTS, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--status', action='store_true')
    action.add_argument('--attrs', action='store_true')
    action.add_argument('--tag')
    action.add_argument('--gc', action='store_true')
    action.add_argument('--relocate', action='store_true')
    parser.add_argument('--apply', action='store_true', help='write; without it, report only')
    return parser.parse_args()


def store_paths(settings, layout):
    """(grid, frequency, variable, path) of every store of this layout."""
    paths = []
    for spec in settings['grids']:
        grid = from_spec(spec)
        for frequency in settings['frequencies']:
            paths += [(grid, frequency, row['canonical_name'],
                       config.store_path(settings, layout, frequency, grid.name, row['canonical_name']))
                      for row in nomenclature.quantities().values()]
    return paths


def relocated_attrs(settings, layout, grid, frequency, variable, group):
    """The path attributes that differ from where the config now puts things, rewritten.

    Built as grid_wisosat.py and rechunk_wisosat.py build them, so a moved
    store reads as if it had been built in place.

    Returns:
        dict: Attribute -> new value; empty when the store already matches.
    """
    other = 'temporal' if layout == 'spatial' else 'spatial'
    wanted = {'related_store': config.store_path(settings, other, frequency, grid.name, variable),
              'source_l2_stores': settings['l2']['directory']}
    if layout == 'temporal':
        # '<spatial path> at tag <tag>, by ...': only the path moved
        old = group.attrs['rechunked_from']
        wanted['rechunked_from'] = wanted['related_store'] + old[old.index(' at tag '):]
    changed = {key: value for key, value in wanted.items() if group.attrs.get(key) != value}
    if changed and group.attrs.get('history'):
        # related_store is <root>/<other layout>/<name>, so its grandparent is the old root
        old_root = os.path.dirname(os.path.dirname(group.attrs['related_store']))
        new_root = settings['directories']['zarr']
        moved = f'from {old_root}/{layout}/ to {new_root}/{layout}/' if old_root != new_root else 'L2 stores moved'
        changed['history'] = (f'{group.attrs["history"]} {datetime.date.today().isoformat()}: moved {moved}; '
                              f'path attributes ({", ".join(sorted(changed))}) rewritten by '
                              f'finalize_grid_wisosat.py --relocate, values unchanged.')
    return changed


def verification_evidence(settings, layout):
    """Store basename -> (date, phases, checks) of the last passing verify run of this layout that covered it."""
    evidence, pending = {}, None
    try:
        lines = open(config.log_path(settings, 'verify_')).read().splitlines()
    except FileNotFoundError:
        return evidence
    for line in lines:
        match = LINE_RE.match(line)
        if not match:
            continue
        text = match['text']
        stores_match = STORES_RE.match(text)
        if stores_match:
            pending = None
            if stores_match['layout'] == layout:
                pending = {'date': match['stamp'][:10], 'phases': stores_match['phases'],
                           'stores': [name.strip() for name in stores_match['stores'].split(',')]}
            continue
        summary = SUMMARY_RE.match(text)
        if summary and pending is not None:
            pending['checks'] = int(summary['checks'])
            pending['failures'] = int(summary['failures'])
            continue
        if text == 'stores verified' and pending is not None and pending.get('failures') == 0:
            for name in pending['stores']:
                evidence[name] = pending
            pending = None
    return evidence


def build_commits(repository):
    """The build's commits on main, oldest first (skeleton, appends and blocks; not this script's)."""
    commits = [snapshot for snapshot in repository.ancestry(branch=stores.BRANCH)
               if snapshot.message not in ('Repository initialized', ATTRS_MESSAGE, RELOCATE_MESSAGE)]
    return commits[::-1]


def derive_attrs(settings, layout, path, group, repository, evidence):
    """The attributes ``--attrs`` writes, from the commits, the time axis and the verify run."""
    commits = build_commits(repository)
    revisions = sorted({snapshot.message.rsplit('@ ', 1)[-1] for snapshot in commits if '@ ' in snapshot.message})
    first, last = commits[0].written_at, commits[-1].written_at
    bounds = group['time_bounds'][:]
    script = 'grid_wisosat.py' if layout == 'spatial' else 'rechunk_wisosat.py'
    today = datetime.date.today().isoformat()
    history = (f'{first:%Y-%m-%d}/{last:%Y-%m-%d}: written from the finalized WISO-SAT L2 stores '
               f'(source_l2_tag) by {script} (data_engineering_wiso-sat/gridding @ {", ".join(revisions)}) in '
               f'{len(commits)} commits. {today}: verified by verify_grid_wisosat.py and finalized by '
               f'finalize_grid_wisosat.py.')
    if layout == 'temporal':
        history = history.replace('written from the finalized WISO-SAT L2 stores (source_l2_tag)',
                                  'rechunked from the tagged spatial store (rechunked_from)')
    scheme = ('every store\'s structure, coordinates, time axis, attributes and L2 snapshots; values on '
              'sampled periods, every cell recomputed from L2 by independent code (shapely, pyproj, pandas)'
              if layout == 'spatial' else
              'every store\'s structure, coordinates, time axis and attributes; values on sampled tiles x '
              'periods, equal bit for bit to the spatial store it was rechunked from')
    verification = (f'{evidence["date"]}: verify_grid_wisosat.py --layout {layout}, phases [{evidence["phases"]}], '
                    f'{evidence["checks"]} checks over {len(evidence["stores"])} stores, 0 failures. Checks: '
                    f'{scheme}. Sampled by decision (user, 2026-11-10), not every value.')
    return {
        'history': group.attrs.get('history') or history,
        'date_created': last.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'verification': verification,
        'time_coverage_start': str(periods.day_date(int(bounds[0][0]))),
        'time_coverage_end': str(periods.day_date(int(bounds[-1][1]) - 1)),
    }


def main():
    args = parse_args()
    settings = config.load_config(args.config)
    config.setup_logging(settings, prefix='finalize_')
    evidence = verification_evidence(settings, args.layout)
    mode = 'APPLY' if args.apply else 'dry run'
    problems = 0
    for grid, frequency, variable, path in store_paths(settings, args.layout):
        name = path.rsplit('/', 1)[-1]
        try:
            repository = stores.open_repository(path)
        except Exception as error:  # noqa: BLE001 - a missing store is reported, not raised
            LOG.error(f'{name}: cannot open ({error})')
            problems += 1
            continue
        group = zarr.open_group(repository.readonly_session(branch=stores.BRANCH).store, mode='r')
        missing = [key for key in FINAL_ATTRS if key not in group.attrs]
        tags = sorted(repository.list_tags())
        if args.status:
            stale = sorted(set(relocated_attrs(settings, args.layout, grid, frequency, variable, group)) - {'history'})
            LOG.info(f'{name}: tags {tags or "none"}; missing attrs {missing or "none"}; '
                     f'verified {evidence[name]["date"] if name in evidence else "no"}; '
                     f'stale paths {stale or "none"}')
        elif args.relocate:
            attrs = relocated_attrs(settings, args.layout, grid, frequency, variable, group)
            if not attrs:
                LOG.info(f'{name}: paths match the config; nothing to do')
                continue
            LOG.info(f'{mode} {name}: ' + '; '.join(f'{key}={value!r}' for key, value in attrs.items()))
            if args.apply:
                session = repository.writable_session(stores.BRANCH)
                zarr.open_group(session.store, mode='r+').update_attributes(attrs)
                session.commit(RELOCATE_MESSAGE)
        elif args.attrs:
            if name not in evidence:
                LOG.error(f'{name}: no passing verify run of the {args.layout} layout covers it')
                problems += 1
                continue
            attrs = derive_attrs(settings, args.layout, path, group, repository, evidence[name])
            LOG.info(f'{mode} {name}: ' + '; '.join(f'{key}={value!r}' for key, value in attrs.items()))
            if args.apply:
                session = repository.writable_session(stores.BRANCH)
                zarr.open_group(session.store, mode='r+').update_attributes(attrs)
                session.commit(ATTRS_MESSAGE)
        elif args.tag:
            if missing:
                LOG.error(f'{name}: missing {missing}; run --attrs first')
                problems += 1
                continue
            if args.tag in tags:
                LOG.error(f'{name}: tag {args.tag} exists')
                problems += 1
                continue
            LOG.info(f'{mode} {name}: tag {args.tag} at {repository.lookup_branch(stores.BRANCH)}')
            if args.apply:
                repository.create_tag(args.tag, repository.lookup_branch(stores.BRANCH))
        elif args.gc:
            cutoff = datetime.datetime.now(datetime.timezone.utc)
            result = repository.garbage_collect(cutoff, dry_run=not args.apply)
            LOG.info(f'{mode} {name}: gc would delete / deleted {result.chunks_deleted} chunks, '
                     f'{result.manifests_deleted} manifests, {result.snapshots_deleted} snapshots, '
                     f'{result.bytes_deleted:,} bytes')
    if problems:
        LOG.error(f'{problems} store(s) not done')
        sys.exit(1)


if __name__ == '__main__':
    main()
