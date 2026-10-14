"""Finalize verified WISO-SAT Level 2 stores for delivery.

The only script here that mutates a finished store, kept apart from
``verify_wisosat_zarr.py`` so the verifier stays read only and can prove a
finalization step did no harm. Ported from ``finalize_mswep_zarr.py``; what
differs is that one config names several stores, so each action runs over all
of them, or over ``--stores``.

Four actions, exactly one per invocation. The three that write must run in
this order: a tag is immutable, so tagging before the attributes exist names a
store that does not describe itself for good.

``--status``
    Where each store stands: verification, attributes pending, tags, reachable
    history and what is unreachable. Reads only.
``--attrs``
    Write the global attributes: the config's, the coverage derived from the
    granule index and the verifier's log, and the provenance. Additive, one
    metadata commit per store. It cannot drop or change a variable attribute.
``--tag NAME``
    Name each store's branch tip.
``--gc``
    Delete objects no surviving snapshot references. Dry-run it first.

Nothing happens without ``--apply``.

**A store cannot claim a verification it has not had.** ``--attrs`` refuses
unless the config's verifier log holds a passing run over every default phase
that covered this store. ``verification``, ``history`` and ``date_created`` are
derived from that log and the repository, never taken from the config.

``--gc --apply`` is irreversible: icechunk only collects unreachable objects,
and this script checks reachable bytes and history length either side, but a
store with no second copy has nothing to restore from.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import re
import subprocess
import sys

import numpy as np
import zarr

from utils.log_utils import setup_logging
from utils.path_utils import load_config, log_path, run_stores, store_path
from utils.zarr_utils import BRANCH, open_existing_repository, open_store
# imported rather than restated, so the bar for 'verified' cannot drift from
# what the verifier runs by default
from verify_wisosat_zarr import DEFAULT_PHASES, KNOWN_MESSAGES

LOG = logging.getLogger(__name__)

STORE_DIRECTORIES = ('chunks', 'manifests', 'snapshots', 'transactions', 'overwritten')

# lines verify_wisosat_zarr.py writes; these have to stay in step with it
VERIFY_SUMMARY_RE = re.compile(
    r'^(?P<when>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d).*?'
    r'(?P<checks>\d+) checks, (?P<failures>\d+) failures'
)
VERIFY_PHASES_RE = re.compile(r'phases: \[(?P<phases>[^\]]*)\]')
VERIFY_STORES_RE = re.compile(r'stores: \[(?P<stores>[^\]]*)\]')
VERIFY_BOUNDS_RE = re.compile(
    r'geospatial bounds: lat \[(?P<lat0>[^,]+), (?P<lat1>[^\]]+)\] '
    r'lon \[(?P<lon0>[^,]+), (?P<lon1>[^\]]+)\]'
)
VERIFY_PASSED = 'stores verified'

# this script's own commit, which build_history must not count as a build
ATTRS_MESSAGE = KNOWN_MESSAGES[1]
INITIAL_MESSAGE = KNOWN_MESSAGES[0]
NON_BUILD_MESSAGES = (INITIAL_MESSAGE, ATTRS_MESSAGE)
OUR_HISTORY_MARKER = 'by wisosat_zarr.py'


def parse_args():
    """Parse the command line.

    Returns:
        argparse.Namespace: The parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description='finalize verified wiso-sat level 2 zarr stores for delivery.'
    )
    parser.add_argument(
        '--config', type=str, required=True, help='Path to YAML configuration file.'
    )
    parser.add_argument(
        '--stores', type=str, default=None,
        help='Comma separated subset of the stores the config names. Default: all.',
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--status', action='store_true', help='Report only.')
    action.add_argument(
        '--attrs', action='store_true',
        help='Write the global attributes. Refuses unless the verifier passed.',
    )
    action.add_argument('--tag', type=str, default=None, help='Create this tag at each tip.')
    action.add_argument(
        '--gc', action='store_true',
        help='Delete unreachable objects. Irreversible with --apply.',
    )
    parser.add_argument(
        '--apply', action='store_true',
        help='Actually make the change. Without it every action only reports.',
    )
    return parser.parse_args()


def repository_revision():
    """The git revision of this working tree, for the history attribute.

    Returns:
        str: The short revision, '-dirty' if the tree has uncommitted changes,
            or 'unknown' if git cannot answer.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        revision = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, check=True, cwd=here,
        ).stdout.strip()
        dirty = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True, text=True, check=True, cwd=here,
        ).stdout.strip()
        return f'{revision}-dirty' if dirty else revision
    except Exception:
        # provenance is worth recording but not worth failing a finalization for
        return 'unknown'


def verification_evidence(settings, store):
    """The last verifier run that passed, covered every phase and this store.

    A partial run (``--phases index``) or one over other stores can pass while
    proving nothing about this one, so neither counts.

    Args:
        settings (dict): The loaded configuration.
        store (str): The store's variable slot.

    Returns:
        dict | None: ``when``, ``checks``, ``failures``, ``phases`` and
            ``bounds`` of that run, or None.
    """
    path = log_path(settings, 'verify_')
    if not os.path.isfile(path):
        LOG.warning(f'no verifier log at {path}')
        return None

    passed = None
    phases, stores, bounds, pending = None, None, None, None
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            if (match := VERIFY_PHASES_RE.search(line)):
                phases = [p.strip().strip("'\"") for p in match['phases'].split(',')]
                stores, bounds, pending = None, None, None
            elif (match := VERIFY_STORES_RE.search(line)):
                stores = [s.strip().strip("'\"") for s in match['stores'].split(',')]
            elif (match := VERIFY_BOUNDS_RE.search(line)):
                bounds = {key: float(match[key]) for key in ('lat0', 'lat1', 'lon0', 'lon1')}
            elif (match := VERIFY_SUMMARY_RE.match(line)):
                pending = {
                    'when': match['when'], 'checks': int(match['checks']),
                    'failures': int(match['failures']), 'phases': phases,
                    'stores': stores, 'bounds': bounds,
                }
            elif VERIFY_PASSED in line and pending and not pending['failures']:
                if (
                    set(DEFAULT_PHASES) <= set(pending['phases'] or [])
                    and store in (pending['stores'] or [])
                    and pending['bounds']
                ):
                    passed = pending
    return passed


def coverage_attrs(dataset, evidence):
    """ACDD coverage attributes, from the granule index and the verifier.

    The time coverage comes from the index, which every store carries. The
    geospatial bounds come from the verifier's pass, which read every lat and
    lon; reading them again here would cost as much as a verification.

    Args:
        dataset (xarray.Dataset): The store.
        evidence (dict): From ``verification_evidence``.

    Returns:
        dict: The attributes.
    """
    starts = dataset['granule_time_start'].values
    ends = dataset['granule_time_end'].values
    starts, ends = starts[~np.isnat(starts)], ends[~np.isnat(ends)]
    bounds = evidence['bounds']
    return {
        'time_coverage_start': str(starts.min().astype('datetime64[ms]')) + 'Z',
        'time_coverage_end': str(ends.max().astype('datetime64[ms]')) + 'Z',
        'geospatial_lat_min': round(bounds['lat0'], 4),
        'geospatial_lat_max': round(bounds['lat1'], 4),
        'geospatial_lon_min': round(bounds['lon0'], 4),
        'geospatial_lon_max': round(bounds['lon1'], 4),
        'granule_count': int(dataset.sizes['granule']),
        'observation_count': int(dataset.sizes['obs']),
    }


def build_history(repository, settings, evidence, current):
    """How the store was built and audited, from the repository itself.

    Args:
        repository (icechunk.Repository): The store's repository.
        settings (dict): The loaded configuration.
        evidence (dict): From ``verification_evidence``.
        current (dict): The store's attributes as they stand.

    Returns:
        tuple: The history string and the ISO 8601 UTC creation timestamp.
    """
    snapshots = list(repository.ancestry(branch=BRANCH))
    built = [s for s in snapshots if s.message not in NON_BUILD_MESSAGES]
    finished = built[0].written_at.astimezone(datetime.timezone.utc)
    started = built[-1].written_at.astimezone(datetime.timezone.utc)
    created = finished.strftime('%Y-%m-%dT%H:%M:%SZ')

    # once written, the history is kept: it names the revision that built the
    # store, and regenerating it would churn on every unrelated commit here
    existing = current.get('history', '')
    if OUR_HISTORY_MARKER in existing:
        return existing, created
    history = (
        f'{started.date().isoformat()}/{finished.date().isoformat()}: written from '
        f'the {settings["product"]} {settings["version"]} source files by '
        f'wisosat_zarr.py (data_engineering_wiso-sat @ {repository_revision()}) '
        f'in {len(built)} commits, appending granules in source order. '
        f'{evidence["when"][:10]}: verified against those same files by '
        f'verify_wisosat_zarr.py, then finalized by finalize_wisosat_zarr.py.'
    )
    return history, created


def resolve_attrs(repository, settings, store, evidence):
    """The global attributes a store should carry.

    The store's own attributes are the base; derived coverage goes on top, and
    the provenance last, because ``verification`` must say what the verifier
    reported rather than what a config claims.

    Args:
        repository (icechunk.Repository): The store's repository.
        settings (dict): The loaded configuration.
        store (str): The store's variable slot.
        evidence (dict | None): From ``verification_evidence``.

    Returns:
        tuple: The merged attributes and the current ones.
    """
    dataset = open_store(repository)
    current = dict(dataset.attrs)
    current.pop('coordinates', None)
    merged = dict(current)
    if evidence:
        history, created = build_history(repository, settings, evidence, current)
        merged |= coverage_attrs(dataset, evidence) | {
            'history': history,
            'date_created': created,
            'verification': (
                f'Verified {evidence["when"][:10]} against the source files by '
                f'verify_wisosat_zarr.py: {evidence["checks"]} checks, '
                f'{evidence["failures"]} failures across '
                f'{", ".join(evidence["phases"])}, over the {len(evidence["stores"])} '
                f'stores of this product. Every observation was compared, not a '
                f'sample, bit for bit, with the raw side read through h5py with no '
                f'masking so the two sides cannot agree by construction.'
            ),
        }
    return merged, current


def object_counts(path):
    """Count the objects in each of the repository's on-disk directories.

    Args:
        path (str): Directory holding the store.

    Returns:
        dict: Directory name -> number of objects in it.
    """
    return {
        name: len(os.listdir(os.path.join(path, name)))
        for name in STORE_DIRECTORIES
        if os.path.isdir(os.path.join(path, name))
    }


def summarize(summary):
    """Render a garbage collection summary as one line.

    Args:
        summary (icechunk.GCSummary): The summary.

    Returns:
        str: The counts, bytes in GiB.
    """
    return (
        f'{summary.bytes_deleted / 1024**3:.2f} GiB: {summary.chunks_deleted} chunks, '
        f'{summary.manifests_deleted} manifests, {summary.snapshots_deleted} snapshots, '
        f'{summary.transaction_logs_deleted} transaction logs'
    )


def run_status(repository, settings, store, path):
    """Report where one store stands.

    Args:
        repository (icechunk.Repository): The store's repository.
        settings (dict): The loaded configuration.
        store (str): The store's variable slot.
        path (str): Directory holding the store.

    Returns:
        int: 0.
    """
    evidence = verification_evidence(settings, store)
    merged, current = resolve_attrs(repository, settings, store, evidence)
    pending = [key for key in merged if current.get(key) != merged[key]]
    tags = repository.list_tags()
    reachable = len(list(repository.ancestry(branch=BRANCH)))
    LOG.info(
        f'{store}: verified {evidence["when"][:10] if evidence else "NO"}; '
        f'{len(pending)} attributes pending; tags {sorted(tags) or "none"}; '
        f'{reachable} reachable snapshots; on disk {object_counts(path)}'
    )
    summary = repository.garbage_collect(datetime.datetime.now(datetime.timezone.utc), dry_run=True)
    LOG.info(f'{store}: unreachable {summarize(summary)}')
    remaining = []
    if not evidence:
        remaining.append('run verify_wisosat_zarr.py')
    else:
        if pending:
            remaining.append('--attrs')
        if not tags:
            remaining.append('--tag NAME')
        if summary.bytes_deleted or summary.snapshots_deleted:
            remaining.append('--gc')
    LOG.info(f'{store}: remaining {" then ".join(remaining) or "nothing, finalized"}')
    return 0


def run_attrs(repository, settings, store, apply_changes):
    """Write one store's global attributes.

    Args:
        repository (icechunk.Repository): The store's repository.
        settings (dict): The loaded configuration.
        store (str): The store's variable slot.
        apply_changes (bool): Whether to commit.

    Returns:
        int: 0 on success, 1 if the store has not been verified.
    """
    evidence = verification_evidence(settings, store)
    if not evidence:
        LOG.error(
            f'{store}: refusing to write attributes: no passing, complete '
            f'verifier run covering this store in {log_path(settings, "verify_")}'
        )
        return 1
    merged, current = resolve_attrs(repository, settings, store, evidence)
    changed = [key for key in merged if current.get(key) != merged[key]]
    for key in changed:
        LOG.info(f'{store}:   set {key} = {merged[key]!r}')
    if not changed:
        LOG.info(f'{store}: attributes already up to date')
        return 0
    if not apply_changes:
        LOG.info(f'{store}: dry run, nothing written; pass --apply to commit')
        return 0
    session = repository.writable_session(branch=BRANCH)
    group = zarr.open_group(session.store, mode='r+')
    group.update_attributes(merged)
    LOG.info(f'{store}: committed {session.commit(ATTRS_MESSAGE)}')
    return 0


def run_tag(repository, store, tag, apply_changes):
    """Create a tag at one store's branch tip.

    Args:
        repository (icechunk.Repository): The store's repository.
        store (str): The store's variable slot.
        tag (str): The tag.
        apply_changes (bool): Whether to create it.

    Returns:
        int: 0 on success, 1 if the tag already exists.
    """
    tip = next(iter(repository.ancestry(branch=BRANCH)))
    if tag in repository.list_tags():
        LOG.error(f'{store}: tag {tag!r} already exists; tags are immutable')
        return 1
    if not apply_changes:
        LOG.info(f'{store}: dry run; --apply would tag {tip.id} ({tip.message}) as {tag!r}')
        return 0
    repository.create_tag(tag, tip.id)
    LOG.info(f'{store}: created tag {tag!r} at {tip.id}')
    return 0


def run_gc(repository, store, apply_changes):
    """Delete objects no surviving snapshot references, checked either side.

    Args:
        repository (icechunk.Repository): The store's repository.
        store (str): The store's variable slot.
        apply_changes (bool): Whether to delete.

    Returns:
        int: 0 on success, 1 if the reachable state changed.
    """
    cutoff = datetime.datetime.now(datetime.timezone.utc)
    before = (repository.chunk_storage_stats().native_bytes,
              len(list(repository.ancestry(branch=BRANCH))))
    LOG.info(f'{store}: dry run would delete {summarize(repository.garbage_collect(cutoff, dry_run=True))}')
    if not apply_changes:
        return 0
    LOG.info(f'{store}: deleted {summarize(repository.garbage_collect(cutoff, dry_run=False))}')
    after = (repository.chunk_storage_stats().native_bytes,
             len(list(repository.ancestry(branch=BRANCH))))
    if after != before:
        LOG.error(
            f'{store}: garbage collection changed the reachable store {before} -> '
            f'{after}; do not trust it, restore it before use'
        )
        return 1
    return 0


def main(settings, args):
    """Run the selected action over the selected stores.

    Args:
        settings (dict): The loaded configuration.
        args (argparse.Namespace): Parsed arguments.

    Returns:
        int: 0 if the action succeeded on every store, 1 otherwise.
    """
    stores = run_stores(settings)
    if args.stores:
        chosen = [s.strip() for s in args.stores.split(',') if s.strip()]
        bad = [s for s in chosen if s not in stores]
        if bad:
            raise ValueError(f'{bad} are not stores of this config; choose from {stores}')
        stores = chosen
    if not args.apply and not args.status:
        LOG.info('--apply not given: reporting only, nothing will be written')

    status = 0
    for store in stores:
        path = store_path(settings, store)
        # Repository.open rather than open_or_create, so a mistyped path fails
        # instead of producing an empty repository that every step agrees with
        repository = open_existing_repository(path)
        if args.status:
            result = run_status(repository, settings, store, path)
        elif args.attrs:
            result = run_attrs(repository, settings, store, args.apply)
        elif args.tag:
            result = run_tag(repository, store, args.tag, args.apply)
        else:
            result = run_gc(repository, store, args.apply)
        status = status or result
    return status


if __name__ == '__main__':
    arguments = parse_args()
    configuration = load_config(arguments.config)
    os.makedirs(configuration['directories']['logs'], exist_ok=True)
    setup_logging(log_path(configuration, 'finalize_'))
    sys.exit(main(configuration, arguments))
