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

**``history`` names the code that wrote each part of the store.** Every build
commit carries the git revision that wrote it (since 2026-10-18), and the
history lists each run of commits with one revision: its granules, dates and
revision. A store whose commits predate that (the first TROPOMI production
stores) needs ``--build-revisions REV@INDEX,...``, each revision with the
granule index it started writing at. Each must be a commit of this repository
older than the build commits it is given for, must start at a commit
boundary, and is marked in the history as supplied at finalization. The
history is written once and then kept.

**A dirty build revision must be explained** (user decision 2026-10-18). A
revision stamped ``-dirty`` (the working tree was not a clean commit when the
build started) or ``unknown`` goes into ``history`` only with
``--dirty-notes 'REV-dirty=what was uncommitted'``. The revision must be a
commit of this repository, and the history marks the explanation as given at
finalization. Builds now refuse a dirty tree (``check_clean_tree``), so this is
for stores built before that. A fixture config (``allow_dirty_tree``) records
its revisions as they are.

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
from utils.zarr_utils import (
    BRANCH, COMMIT_RE, code_revision, open_existing_repository, open_store,
)
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
    parser.add_argument(
        '--build-revisions', type=str, default=None,
        help='For build commits that name no code revision: REV@GRANULE_INDEX,... '
        'giving each revision with the granule index it started writing at.',
    )
    parser.add_argument(
        '--dirty-notes', type=str, action='append', default=None,
        help='Explain a build revision stamped -dirty: REV-dirty=TEXT, what was '
        'uncommitted when the build ran. Repeat for several.',
    )
    return parser.parse_args()


class MissingRevisions(ValueError):
    """Build commits that name no code revision, with none supplied for them,
    or a dirty revision with no explanation."""


def parse_dirty_notes(items):
    """Parse ``--dirty-notes``.

    Args:
        items (list | None): ``REV-dirty=TEXT`` strings.

    Returns:
        dict: Stamped revision -> explanation.

    Raises:
        ValueError: If an item is malformed or names a revision twice.
    """
    notes = {}
    for item in items or []:
        revision, separator, text = item.partition('=')
        revision, text = revision.strip(), text.strip()
        if not separator or not text or not (revision.endswith('-dirty') or revision == 'unknown'):
            raise ValueError(f'--dirty-notes takes REV-dirty=TEXT; got {item!r}')
        if revision in notes:
            raise ValueError(f'--dirty-notes explains {revision} twice')
        notes[revision] = text
    return notes


def parse_build_revisions(text):
    """Parse ``--build-revisions``.

    Args:
        text (str | None): ``REV@GRANULE_INDEX,...``.

    Returns:
        list | None: ``(granule index, revision)`` pairs, sorted by index.

    Raises:
        ValueError: If an item is malformed or an index repeats.
    """
    if not text:
        return None
    entries = []
    for item in text.split(','):
        revision, separator, index = item.strip().partition('@')
        if not separator or not revision or not index.isdigit():
            raise ValueError(f'--build-revisions takes REV@GRANULE_INDEX,...; got {item!r}')
        entries.append((int(index), revision))
    if len({index for index, _ in entries}) != len(entries):
        raise ValueError('--build-revisions names a granule index twice')
    return sorted(entries)


def resolve_revision(revision):
    """A supplied revision as this repository knows it.

    Args:
        revision (str): Any git revision.

    Returns:
        tuple: Its short hash and its commit time (UTC).

    Raises:
        ValueError: If it is not a commit of this repository.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        short, stamp = subprocess.run(
            ['git', 'show', '-s', '--format=%h %ct', f'{revision}^{{commit}}'],
            capture_output=True, text=True, check=True, cwd=here,
        ).stdout.split()
    except (subprocess.CalledProcessError, ValueError) as error:
        raise ValueError(f'{revision!r} is not a commit of this repository') from error
    return short, datetime.datetime.fromtimestamp(int(stamp), datetime.timezone.utc)


def build_segments(repository, ids, supplied):
    """A store's build commits, grouped into runs written by one code revision.

    Args:
        repository (icechunk.Repository): The store's repository.
        ids (numpy.ndarray): The store's ``granule_id``, in order.
        supplied (list | None): From ``parse_build_revisions``.

    Returns:
        list: Per run, a dict with ``first`` and ``last`` granule ids,
            ``start`` and ``end`` (UTC), ``revision``, ``supplied`` and
            ``commits``; oldest first.

    Raises:
        MissingRevisions: If a build commit names no revision and none was
            supplied for it.
        ValueError: If a commit message is not the build's, or a supplied
            revision is unused, off a commit boundary, unknown, or newer than
            the commits it is given for.
    """
    position = {str(granule): index for index, granule in enumerate(ids)}
    commits = []
    for snapshot in reversed(list(repository.ancestry(branch=BRANCH))):
        if snapshot.message in NON_BUILD_MESSAGES:
            continue
        match = COMMIT_RE.match(snapshot.message)
        if not match:
            raise ValueError(f'not a build commit: {snapshot.id} {snapshot.message!r}')
        commits.append({
            'first': match['first'], 'last': match['last'],
            'index': position[match['first']],
            'when': snapshot.written_at.astimezone(datetime.timezone.utc),
            'revision': match['revision'], 'supplied': False,
        })

    bare = [commit for commit in commits if commit['revision'] is None]
    if bare and not supplied:
        raise MissingRevisions(
            f'{len(bare)} build commits name no code revision; give them with '
            f'--build-revisions REV@GRANULE_INDEX,...'
        )
    if supplied and not bare:
        raise ValueError('--build-revisions given, but every build commit names its revision')
    if supplied:
        starts = {commit['index'] for commit in bare}
        resolved = []
        for index, revision in supplied:
            if index not in starts:
                raise ValueError(
                    f'--build-revisions: granule {index} does not start a build commit '
                    f'that names no revision'
                )
            resolved.append((index, *resolve_revision(revision)))
        for commit in bare:
            covering = [entry for entry in resolved if entry[0] <= commit['index']]
            if not covering:
                raise MissingRevisions(f'no supplied revision covers granule {commit["first"]}')
            _, short, committed = covering[-1]
            # the code has to exist before it can write anything
            if committed > commit['when']:
                raise ValueError(
                    f'revision {short} was committed {committed:%Y-%m-%d %H:%M:%S}Z, after '
                    f'the commit of granule {commit["first"]} at '
                    f'{commit["when"]:%Y-%m-%d %H:%M:%S}Z'
                )
            commit['revision'], commit['supplied'] = short, True

    segments = []
    for commit in commits:
        last = segments[-1] if segments else None
        if last and (last['revision'], last['supplied']) == (commit['revision'], commit['supplied']):
            last.update(last=commit['last'], end=commit['when'], commits=last['commits'] + 1)
        else:
            segments.append({
                'first': commit['first'], 'last': commit['last'],
                'start': commit['when'], 'end': commit['when'],
                'revision': commit['revision'], 'supplied': commit['supplied'], 'commits': 1,
            })
    return segments


def date_span(start, end):
    """``YYYY-MM-DD``, or ``start/end`` when the two dates differ."""
    first, last = start.date().isoformat(), end.date().isoformat()
    return first if first == last else f'{first}/{last}'


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


def build_history(repository, settings, evidence, current, ids, supplied, notes=None):
    """How the store was built and audited, from the repository itself.

    Args:
        repository (icechunk.Repository): The store's repository.
        settings (dict): The loaded configuration.
        evidence (dict): From ``verification_evidence``.
        current (dict): The store's attributes as they stand.
        ids (numpy.ndarray): The store's ``granule_id``.
        supplied (list | None): From ``parse_build_revisions``.
        notes (dict | None): From ``parse_dirty_notes``.

    Returns:
        tuple: The history string and the ISO 8601 UTC creation timestamp.

    Raises:
        MissingRevisions: From ``build_segments``, or for a dirty revision with
            no explanation, when a history is to be written.
        ValueError: If an explanation names a revision no build commit carries,
            or whose commit this repository does not have.
    """
    snapshots = list(repository.ancestry(branch=BRANCH))
    built = [s for s in snapshots if s.message not in NON_BUILD_MESSAGES]
    finished = built[0].written_at.astimezone(datetime.timezone.utc)
    started = built[-1].written_at.astimezone(datetime.timezone.utc)
    created = finished.strftime('%Y-%m-%dT%H:%M:%SZ')

    # once written, the history is kept: it names the revisions that built the
    # store, and regenerating it would churn on every unrelated commit here
    existing = current.get('history', '')
    if OUR_HISTORY_MARKER in existing:
        return existing, created
    notes = dict(notes or {})
    parts, used = [], set()
    for segment in build_segments(repository, ids, supplied):
        revision = segment['revision']
        note = ', supplied at finalization' if segment['supplied'] else ''
        dirty = revision == 'unknown' or revision.endswith('-dirty')
        if dirty and not settings.get('allow_dirty_tree'):
            if revision not in notes:
                raise MissingRevisions(
                    f'build revision {revision} was not a clean commit; explain what was '
                    f'uncommitted with --dirty-notes {revision}=TEXT'
                )
            if revision != 'unknown':
                revision = revision[:-len('-dirty')]
                resolve_revision(revision)
            note = (
                f'; the working tree was not a clean commit when this ran: '
                f'{notes[segment["revision"]]} (explained at finalization){note}'
            )
            used.add(segment['revision'])
        parts.append(
            f'granules {segment["first"]}..{segment["last"]} on '
            f'{date_span(segment["start"], segment["end"])} '
            f'(data_engineering_wiso-sat @ {revision}{note})'
        )
    unused = sorted(set(notes) - used)
    if unused:
        raise ValueError(
            f'--dirty-notes explains {unused}, which no build commit of this store carries'
        )
    history = (
        f'{date_span(started, finished)}: written from the {settings["product"]} '
        f'{settings["version"]} source files by wisosat_zarr.py in {len(built)} '
        f'commits, appending granules in source order: {"; ".join(parts)}. '
        f'{evidence["when"][:10]}: verified against those same files by '
        f'verify_wisosat_zarr.py, then finalized by finalize_wisosat_zarr.py '
        f'(@ {code_revision()}).'
    )
    return history, created


def resolve_attrs(repository, settings, store, evidence, supplied=None, strict=True,
                  notes=None):
    """The global attributes a store should carry.

    The store's own attributes are the base; derived coverage goes on top, and
    the provenance last, because ``verification`` must say what the verifier
    reported rather than what a config claims.

    Args:
        repository (icechunk.Repository): The store's repository.
        settings (dict): The loaded configuration.
        store (str): The store's variable slot.
        evidence (dict | None): From ``verification_evidence``.
        supplied (list | None): From ``parse_build_revisions``.
        strict (bool): Raise if the history cannot be written; otherwise
            leave it out (``--status`` reports, it does not refuse).

    Returns:
        tuple: The merged attributes, the current ones, and the reason the
            history was left out (None if it was not).

    Raises:
        MissingRevisions: If ``strict`` and the build revisions are unknown.
    """
    dataset = open_store(repository)
    current = dict(dataset.attrs)
    current.pop('coordinates', None)
    merged = dict(current)
    missing = None
    if evidence:
        ids = dataset['granule_id'].values
        try:
            history, created = build_history(
                repository, settings, evidence, current, ids, supplied, notes
            )
            provenance = {'history': history, 'date_created': created}
        except MissingRevisions as error:
            if strict:
                raise
            provenance, missing = {}, str(error)
        total = len(run_stores(settings))
        covered = len(evidence['stores'])
        scope = (
            f'over all {total} stores of this product' if covered == total else
            f'in a run over {covered} of the {total} stores of this product, '
            f'this one included'
        )
        # like the history, a verification record is kept once it describes
        # this verifier run: it names the product's store count at the time,
        # which grows when a store is added and must not rewrite the record
        existing = current.get('verification', '')
        same_run = existing.startswith(f'Verified {evidence["when"][:10]} ') and (
            f'{evidence["checks"]} checks, {evidence["failures"]} failures' in existing
        )
        merged |= coverage_attrs(dataset, evidence) | provenance | {
            'verification': existing if same_run else (
                f'Verified {evidence["when"][:10]} against the source files by '
                f'verify_wisosat_zarr.py: {evidence["checks"]} checks, '
                f'{evidence["failures"]} failures across '
                f'{", ".join(evidence["phases"])}, {scope}. Every observation was '
                f'compared, not a sample, bit for bit, with the raw side read through '
                f'h5py with no masking so the two sides cannot agree by construction.'
            ),
        }
    return merged, current, missing


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


def run_status(repository, settings, store, path, supplied=None, notes=None):
    """Report where one store stands.

    Args:
        repository (icechunk.Repository): The store's repository.
        settings (dict): The loaded configuration.
        store (str): The store's variable slot.
        path (str): Directory holding the store.
        supplied (list | None): From ``parse_build_revisions``.

    Returns:
        int: 0.
    """
    evidence = verification_evidence(settings, store)
    merged, current, missing = resolve_attrs(
        repository, settings, store, evidence, supplied, strict=False, notes=notes
    )
    if missing:
        LOG.warning(f'{store}: history cannot be written yet: {missing}')
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


def run_attrs(repository, settings, store, apply_changes, supplied=None, notes=None):
    """Write one store's global attributes.

    Args:
        repository (icechunk.Repository): The store's repository.
        settings (dict): The loaded configuration.
        store (str): The store's variable slot.
        apply_changes (bool): Whether to commit.
        supplied (list | None): From ``parse_build_revisions``.

    Returns:
        int: 0 on success, 1 if the store has not been verified or its build
            revisions are unknown.
    """
    evidence = verification_evidence(settings, store)
    if not evidence:
        LOG.error(
            f'{store}: refusing to write attributes: no passing, complete '
            f'verifier run covering this store in {log_path(settings, "verify_")}'
        )
        return 1
    try:
        merged, current, _ = resolve_attrs(
            repository, settings, store, evidence, supplied, notes=notes
        )
    except MissingRevisions as error:
        LOG.error(f'{store}: refusing to write attributes: {error}')
        return 1
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
    supplied = parse_build_revisions(args.build_revisions)
    notes = parse_dirty_notes(args.dirty_notes)
    if (supplied or notes) and not (args.attrs or args.status):
        raise ValueError('--build-revisions and --dirty-notes apply to --attrs and --status only')
    if not args.apply and not args.status:
        LOG.info('--apply not given: reporting only, nothing will be written')

    status = 0
    for store in stores:
        path = store_path(settings, store)
        # Repository.open rather than open_or_create, so a mistyped path fails
        # instead of producing an empty repository that every step agrees with
        repository = open_existing_repository(path)
        if args.status:
            result = run_status(repository, settings, store, path, supplied, notes)
        elif args.attrs:
            result = run_attrs(repository, settings, store, args.apply, supplied, notes)
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
