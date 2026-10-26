"""End-to-end test of the shared pipeline against every product's fixture.

Design condition 2 (2026-10-14): every product keeps a tiny fixture, and this
runs all of them after any change to shared code. A product is in the test as
soon as it has a ``config/<product>/config_zarr_fixture.yaml``.

The entry points run as **subprocesses**, as in ``data_engineering_gleam``:
that tests the real command line, exit status and log. Cases that matter assert
on what the run said, not only on its exit code, since a phase that silently
did nothing would exit 0 too.

Per product:

1. a clean build, then a full verification;
2. a re-run, which must be a no-op;
3. resume: one store reset to empty and one to its first commit, as a run
   killed partway would leave them, then rebuilt and re-verified;
4. the verifier must fail on a tampered value, naming the store, on a
   store compressed other than as its config says, (where the config
   declares one) on a platform the files do not declare, (where it
   declares rows left out) on a declaration that does not match raw, and
   (CrIS) on a defective file whose day is not declared;
5. guards: an undeclared missing day (or month), a wrong processor version
   or platform, declared rows that are missing, do not match, or are given
   to a reader that cannot apply them, declared defect values that do not
   match raw or are given to a reader that cannot apply them, a run that
   omits the quality flags (where the product has any), an unknown variable,
   compression of an unknown array, and (where the product has them) an
   undeclared empty granule directory or unreadable file, an undeclared
   one-sided granule, or a claim that unordered files are in time order;
   and (CrIS) repeated footprints undeclared or miscounted, a replaced file
   undeclared, and a whole-file defect declared on a file that is not;
   A build without the fixture's ``allow_dirty_tree`` must refuse a working
   tree that is not a clean commit (an untracked probe file makes it dirty).
6. finalize: ``--attrs`` refuses without verification evidence, and
   ``--expire`` an untagged sharded store; the full ``--attrs``, ``--tag``,
   ``--expire``, ``--gc`` sequence, after which a sharded store keeps only
   its tip and every store reports finalized; then the verifier still passes.

Run from the repo root after staging each fixture:

    uv run python validation/stage_tropomi.py
    uv run python validation/stage_gosat.py      # GOSAT and GOSAT-2
    uv run python validation/stage_sciamachy.py
    uv run python validation/stage_tropess.py    # AIRS RS and FS, the three CrIS
    uv run python validation/test_pipeline.py

About a minute per product on a login node; no allocation spent. Failures are
collected rather than raised, so one run reports everything that is wrong.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile

import icechunk
import xarray as xr
import numpy as np
import yaml # type: ignore
import zarr

from utils.granules import COVERAGE_KEYS, check_repeats
from utils.nomenclature import coordinates
from utils.nomenclature import variable as key_variable
from utils.path_utils import (
    GEOLOCATION, listing_options, load_config, load_reader, run_stores, source_product,
    store_path,
)
from utils.zarr_utils import (
    BRANCH, COMMIT_PREFIX, COMMIT_RE, repeat_look_back, row_rule, sharded_stores,
    stored_seam_keys, time_source,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Results:
    """Collects case outcomes so one run reports every failure.

    Attributes:
        failures (list): Names of the cases that failed.
        n (int): How many cases ran.
    """

    def __init__(self):
        self.failures = []
        self.n = 0

    def check(self, name, ok, detail=''):
        """Record one case.

        Args:
            name (str): What was checked.
            ok (bool): Whether it held.
            detail (str): What was measured, shown either way.

        Returns:
            bool: The ``ok`` passed in.
        """
        self.n += 1
        print(f'{"PASS" if ok else "FAIL"}  {name}{"  " + detail if detail else ""}', flush=True)
        if not ok:
            self.failures.append(name)
        return ok


def run(*args):
    """Run one entry point from the repo root.

    Args:
        *args: The command line after the interpreter.

    Returns:
        tuple: The exit status and both output streams joined.
    """
    done = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)
    return done.returncode, f'{done.stdout}\n{done.stderr}'


def last_line(output, needle):
    """The last output line containing a string, for a failure message.

    Args:
        output (str): A run's output.
        needle (str): What to look for.

    Returns:
        str: The line, or '' if none.
    """
    lines = [line for line in output.splitlines() if needle in line]
    return lines[-1].strip()[-160:] if lines else ''


def write_config(settings, directory, name, **changes):
    """Write a variant of a config into a scratch directory.

    Args:
        settings (dict): The base configuration.
        directory (str): Where to write it.
        name (str): File name.
        **changes: Top-level keys to replace.

    Returns:
        str: The path written.
    """
    variant = dict(settings) | changes
    path = os.path.join(directory, name)
    with open(path, 'w', encoding='utf-8') as handle:
        yaml.safe_dump(variant, handle, sort_keys=False)
    return path


def repository(settings, store):
    """Open one fixture store's repository.

    Args:
        settings (dict): The configuration.
        store (str): The store's variable slot.

    Returns:
        icechunk.Repository: The repository.
    """
    return icechunk.Repository.open(icechunk.local_filesystem_storage(store_path(settings, store)))


def history(settings, store):
    """A store's snapshots, oldest first.

    Args:
        settings (dict): The configuration.
        store (str): The store's variable slot.

    Returns:
        list: Snapshot infos.
    """
    return list(repository(settings, store).ancestry(branch=BRANCH))[::-1]


def test_product(results, config, scratch):
    """Run every case against one product's fixture.

    Args:
        results (Results): Where to record cases.
        config (str): The fixture config, relative to the repo root.
        scratch (str): A scratch directory for variant configs and logs.
    """
    settings = load_config(os.path.join(ROOT, config))
    product = settings['product']
    # logs in scratch, so verifier evidence from earlier runs cannot satisfy
    # finalize here
    settings['directories'] = dict(settings['directories'], logs=os.path.join(scratch, 'logs'))
    base = write_config(settings, scratch, f'{product}.yaml')
    stores = run_stores(settings)
    print(f'--- {product}: {config}', flush=True)

    if not os.path.isdir(settings['directories']['raw']):
        results.check(f'{product}: fixture is staged', False,
                      f'run validation/stage_{source_product(settings)}.py first')
        return
    shutil.rmtree(settings['directories']['zarr'], ignore_errors=True)

    # 1. clean build and full verification
    status, output = run('wisosat_zarr.py', '--config', base)
    results.check(f'{product}: clean build', status == 0, last_line(output, 'Error') or last_line(output, 'done'))
    status, output = run('verify_wisosat_zarr.py', '--config', base)
    results.check(f'{product}: clean build verifies', status == 0 and 'stores verified' in output,
                  last_line(output, 'checks,'))

    # the index accounts for every source row: stored, or left out as never
    # processed, and never more stored than the files hold
    index = xr.open_zarr(
        repository(settings, GEOLOCATION).readonly_session(BRANCH).store, consolidated=False
    )
    counts = index['granule_obs_count'].values
    rows = index['granule_source_rows'].values
    results.check(
        f'{product}: granule_source_rows covers every stored observation',
        bool((rows >= counts).all()),
        f'{int(counts.sum())} stored of {int(rows.sum())} source rows, '
        f'{int((counts == 0).sum())} granules with none',
    )

    # 2. a re-run writes nothing
    status, output = run('wisosat_zarr.py', '--config', base)
    results.check(f'{product}: re-run is a no-op', status == 0 and 'already complete' in output)

    # 3. resume, as a killed run leaves things: one store empty, one store a
    # commit in, everything else complete
    victims = (stores[1], stores[-1])
    snapshots = history(settings, victims[0])
    repository(settings, victims[0]).reset_branch(BRANCH, snapshots[0].id)
    snapshots = history(settings, victims[1])
    repository(settings, victims[1]).reset_branch(BRANCH, snapshots[1].id)
    status, output = run('wisosat_zarr.py', '--config', base)
    results.check(f'{product}: resume after a partial build', status == 0,
                  last_line(output, 'batches from granule'))
    status, output = run('verify_wisosat_zarr.py', '--config', base)
    results.check(f'{product}: resumed stores verify', status == 0 and 'stores verified' in output,
                  last_line(output, 'checks,'))

    # 4. the verifier must catch a single changed value
    target = stores[1]
    repo = repository(settings, target)
    tip = next(iter(repo.ancestry(branch=BRANCH))).id
    session = repo.writable_session(BRANCH)
    array = zarr.open_group(session.store, mode='r+')[target]
    # one element of observation 5, whatever the store's secondary dimensions
    value = np.array(array[5])
    flat = value.reshape(-1)
    flat[0] = flat[0] + 1 if np.isfinite(flat[0]) else 1
    array[5] = value
    session.commit('write granules tamper')
    status, output = run('verify_wisosat_zarr.py', '--config', base, '--phases', 'values')
    results.check(
        f'{product}: verifier fails on one changed value',
        status != 0 and f'FAIL  {target}/{target}: every observation matches raw' in output,
        last_line(output, f'{target}/{target}: every'),
    )
    repo.reset_branch(BRANCH, tip)

    # ... and, where the files are not in time order, an observation that
    # repeats another, the check that takes the time order's place: obs 1 made
    # a copy of obs 0, then the third granule's first a copy of the second's
    # last, which is also a seam between the verifier's ranges
    if settings.get('time_order') == 'source':
        geolocation = repository(settings, GEOLOCATION)
        tip = next(iter(geolocation.ancestry(branch=BRANCH))).id
        starts = index['granule_obs_start'].values
        for where, (source, destination) in (
            ('within a granule', (int(starts[0]), int(starts[0]) + 1)),
            ('across a seam', (int(starts[2]) - 1, int(starts[2]))),
        ):
            session = geolocation.writable_session(BRANCH)
            group = zarr.open_group(session.store, mode='r+')
            for name in ('time', 'lat', 'lon'):
                group[name][destination] = group[name][source]
            session.commit('write granules tamper')
            status, output = run(
                'verify_wisosat_zarr.py', '--config', base, '--phases', 'values',
                '--stores', GEOLOCATION,
            )
            results.check(
                f'{product}: verifier fails on an observation repeated {where}',
                status != 0 and 'FAIL  no observation repeats another' in output,
                last_line(output, 'no observation repeats'),
            )
            geolocation.reset_branch(BRANCH, tip)
        test_repeats(results, settings)

    # --stores compares only the stores it names: the geolocation store is
    # opened for the index, but its values are not compared again
    status, output = run('verify_wisosat_zarr.py', '--config', base, '--stores', target)
    results.check(
        f'{product}: verify --stores compares only the stores named',
        status == 0 and f"stores: ['{target}']" in output
        and f'{target}/{target}: every observation matches raw' in output
        and 'geolocation/lat: every observation' not in output,
        last_line(output, 'checks,'),
    )

    # ... and a store compressed other than as the config says: the config
    # loses its compression block, or gains one where it had none
    if settings.get('compression'):
        changes = {'compression': None}
    else:
        changes = {'compression': {'blosc': {'cname': 'zstd', 'clevel': 5, 'shuffle': 'shuffle'},
                                   'arrays': [target]}}
    path = write_config(settings, scratch, f'{product}_codec.yaml', **changes)
    status, output = run('verify_wisosat_zarr.py', '--config', path, '--phases', 'structure')
    results.check(
        f'{product}: verifier fails on a codec the config does not set',
        status != 0 and 'compressed and sharded as the config sets' in output,
        last_line(output, 'compressed and sharded as the config sets'),
    )

    # ... and files of another platform than the config declares, where the
    # reader reads one (GOSAT and GOSAT-2 share a reader)
    if settings.get('platform'):
        path = write_config(settings, scratch, f'{product}_platform.yaml', platform='NO_SUCH')
        status, output = run(
            'verify_wisosat_zarr.py', '--config', path, '--phases', 'values', '--stores', target
        )
        # a reader that lists by platform (TROPESS) refuses one it does not know
        message = (
            'this reader lists only' if getattr(load_reader(settings), 'LISTS_BY_PLATFORM', False)
            else "FAIL  every file declares platform 'NO_SUCH'"
        )
        results.check(
            f'{product}: verifier fails on a platform the files do not declare',
            status != 0 and message in output,
            last_line(output, 'every file declares platform') or last_line(output, message),
        )

    # ... and a standard_name the config declares that no source file uses
    named = [name for name, attrs in (settings.get('variable_attrs') or {}).items()
             if 'standard_name' in (attrs or {})]
    if named:
        wrong = {name: dict(attrs, standard_name='no_such_name') if name in named else attrs
                 for name, attrs in settings['variable_attrs'].items()}
        path = write_config(settings, scratch, f'{product}_standard_name.yaml', variable_attrs=wrong)
        status, output = run(
            'verify_wisosat_zarr.py', '--config', path, '--phases', 'values', '--stores', ','.join(named)
        )
        results.check(
            f'{product}: verifier fails on a declared standard_name no source file uses',
            status != 0 and 'failed: ' in last_line(
                output, 'standard_name is the source one the config declares'
            ),
            last_line(output, 'standard_name is the source one the config declares'),
        )

    # ... and declared rows that do not match raw: the repeat's block halved,
    # so the same rows are left out (the index still lines up) but the
    # second half of each copy no longer equals the block
    declared = settings.get('declared_rows_left_out') or []
    repeats = [entry for entry in declared if entry.get('repeat_of')]
    if repeats:
        first, last = repeats[0]['repeat_of']
        wrong = [dict(entry, repeat_of=[first, first + (last - first) // 2]) if entry is repeats[0]
                 else entry for entry in declared]
        path = write_config(settings, scratch, f'{product}_declared.yaml',
                            declared_rows_left_out=wrong)
        status, output = run(
            'verify_wisosat_zarr.py', '--config', path, '--phases', 'values', '--stores', target
        )
        results.check(
            f'{product}: verifier fails on declared rows that do not match raw',
            status != 0 and 'FAIL  declared rows left out' in output,
            last_line(output, 'declared rows left out'),
        )

    # ... and, under a whole-file declared mask (CrIS R36), a defective day the
    # config does not declare: the verifier checks undeclared days too (Q1)
    whole = [entry for entry in settings.get('declared_masked_values') or []
             if entry.get('where') == 'every_row_of_listed_days']
    if whole:
        wrong = [dict(entry, days=[]) if entry is whole[0] else entry
                 for entry in settings['declared_masked_values']]
        path = write_config(settings, scratch, f'{product}_undeclared_mask.yaml', declared_masked_values=wrong)
        status, output = run('verify_wisosat_zarr.py', '--config', path, '--phases', 'values')
        results.check(
            f'{product}: verifier fails on a defective file whose day is not declared',
            status != 0 and 'but its day is not declared' in output,
            last_line(output, 'documented layout'),
        )

    # 5. guards that must stop a build before it writes
    coverage_key, _ = COVERAGE_KEYS[getattr(load_reader(settings), 'COVERAGE_FREQUENCY', 'D')]
    guards = {
        'an undeclared missing period': ({coverage_key: []}, 'not declared'),
        'a wrong processor version': ({'version': '0.0'}, 'processor version'),
        'an unknown variable': ({'variables': settings['variables'] + ['no_such_variable']}, 'has no row'),
        'a shard that is not a multiple of chunks.obs': (
            {'compression': {'blosc': {'cname': 'zstd', 'clevel': 5, 'shuffle': 'shuffle'},
                             'shard_obs': settings['chunks']['obs'] + 1,
                             'arrays': [settings['variables'][0]]}},
            'positive multiple of chunks.obs',
        ),
        'a process of its own for the geolocation store': (
            {'own_process_stores': ['geolocation']}, 'own_process_stores must name',
        ),
        'compression of an unknown array': (
            {'compression': {'blosc': {'cname': 'zstd', 'clevel': 5, 'shuffle': 'shuffle'},
                             'arrays': ['no_such_array']}},
            'no store of this config holds',
        ),
    }
    if any(v.startswith('quality_flags') for v in settings['variables']):
        # TROPESS publishes no quality flag, so there is none to omit
        guards['omitted quality flags'] = (
            {'variables': [v for v in settings['variables'] if not v.startswith('quality_flags')]},
            'quality flags',
        )
    if settings.get('platform'):
        guards['a wrong platform'] = (
            {'platform': 'NO_SUCH'},
            'this reader lists only' if getattr(load_reader(settings), 'LISTS_BY_PLATFORM', False)
            else 'platform other than',
        )
    if settings.get('expected_partial_granules'):
        guards['an undeclared one-sided granule'] = (
            {'expected_partial_granules': {}}, 'and is not declared so'
        )
    masks = settings.get('declared_masked_values') or []
    if masks:
        # the declared defect compared against another source: it must not match
        wrong = [dict(masks[0], equals='observation_ops/xa')] + masks[1:]
        guards['a declared defect that is not what it says'] = (
            {'declared_masked_values': wrong}, 'as declared'
        )
    elif not getattr(load_reader(settings), 'DECLARED_MASKS', False):
        guards['declared masks for a reader that cannot apply them'] = (
            {'declared_masked_values': [{
                'source': key_variable(source_product(settings), settings['variables'][0]).original,
                'reason': 'test',
            }]},
            'does not apply declared masks',
        )
    rule = settings.get('repeated_footprints')
    if rule:
        # CrIS R37: footprints in two files are left out only as declared, and
        # only exactly as many as declared
        guards['footprints repeated in two files, undeclared'] = (
            {'repeated_footprints': None}, 'observations of the granule'
        )
        guards['a count of repeated footprints other than the rule finds'] = (
            {'repeated_footprints': dict(rule, expected_left_out=int(rule['expected_left_out']) + 1)},
            'but the config declares expected_left_out',
        )
    if settings.get('superseded_files'):
        guards['a replaced file not declared'] = ({'superseded_files': {}}, 'Standard files for')
    if whole:
        # a day declared defective whose files are not: one staged day the
        # first whole-file mask leaves out, added to it
        reader = load_reader(settings)
        listed = reader.listed_days(whole[0])
        options = dict(listing_options(settings, reader), repeated_footprints=None)
        clean = [g.id for g in reader.list_granules(settings['directories']['raw'], **options)
                 if g.id not in listed]
        if clean:
            wrong = [dict(entry, days=list(entry['days']) + [clean[0]]) if entry is whole[0] else entry
                     for entry in settings['declared_masked_values']]
            guards['a whole-file defect declared on a file that is not defective'] = (
                {'declared_masked_values': wrong}, 'on every row, as declared'
            )
    if settings.get('time_order') == 'source':
        # the source order is kept only because the files are not in time
        # order; claiming they are must fail the build
        guards['a time order the files do not have'] = ({'time_order': 'sorted'}, 'time decreases')
    if settings.get('expected_unreadable_granules'):
        # only the last declared file is undeclared: a file that crashes HDF5
        # (TROPOMI 3335) would take the build down with no message to match
        guards['an undeclared unreadable file'] = (
            {'expected_unreadable_granules': settings['expected_unreadable_granules'][:-1]},
            'HDF error',
        )
    if settings.get('allowed_on_rows_left_out'):
        guards['a value on a row left out that is not allowed'] = (
            {'allowed_on_rows_left_out': []}, 'cannot be left out'
        )
    if settings.get('expected_empty_granules'):
        guards['an undeclared empty granule directory'] = (
            {'expected_empty_granules': []}, 'holds 0 orbit files'
        )
    if declared:
        guards['undeclared repeated rows'] = ({'declared_rows_left_out': []}, 'time decreases')
        for entry in declared:
            if entry.get('repeat_of'):
                first, last = entry['repeat_of']
                change = {'repeat_of': [first, first + (last - first) // 2]}
                message = 'are not copies of rows'
            else:
                other = entry['same_location_as']
                start, stop = other['rows']
                change = {'same_location_as': dict(other, rows=[start + 1, stop + 1])}
                message = 'do not have the'
            wrong = [dict(item, **change) if item is entry else item for item in declared]
            guards[f'declared rows of {entry["granule"]} that do not match'] = (
                {'declared_rows_left_out': wrong}, message,
            )
    elif not getattr(load_reader(settings), 'DECLARED_ROWS', False):
        guards['declared rows for a reader that cannot apply them'] = (
            {'declared_rows_left_out': [{'granule': '0', 'rows': [0, 1], 'reason': 'test'}]},
            'does not apply declared rows',
        )
    # each guard builds into an empty zarr directory of its own, so it meets
    # the check it is aimed at rather than the resume check against the
    # stores built above
    for name, (changes, message) in guards.items():
        guard_zarr = os.path.join(scratch, 'guard_zarr')
        shutil.rmtree(guard_zarr, ignore_errors=True)
        directories = dict(settings['directories'], zarr=guard_zarr)
        path = write_config(
            settings, scratch, f'{product}_guard.yaml', directories=directories, **changes
        )
        status, output = run('wisosat_zarr.py', '--config', path)
        results.check(f'{product}: build refuses {name}', status != 0 and message in output,
                      last_line(output, message) or last_line(output, 'Error'))
        # both are checked on the first granule, before any repository exists
        for field in ('version', 'platform'):
            if field in changes:
                wrong = dict(settings, directories=directories, **changes)
                results.check(
                    f'{product}: a refused {field} created no store',
                    not os.path.exists(store_path(wrong, GEOLOCATION)),
                )

    # a build must start from a clean commit. The fixture config allows a
    # dirty tree (the test runs during development); without that, and with
    # an untracked file made here, the build must refuse before writing
    probe = os.path.join(ROOT, f'.dirty_tree_probe_{product}')
    guard_zarr = os.path.join(scratch, 'guard_zarr')
    shutil.rmtree(guard_zarr, ignore_errors=True)
    directories = dict(settings['directories'], zarr=guard_zarr)
    path = write_config(
        settings, scratch, f'{product}_clean.yaml', directories=directories,
        allow_dirty_tree=False,
    )
    try:
        open(probe, 'w').close()
        status, output = run('wisosat_zarr.py', '--config', path)
    finally:
        os.remove(probe)
    results.check(
        f'{product}: build refuses a working tree that is not a clean commit',
        status != 0 and 'not a clean commit' in output and not os.path.exists(guard_zarr),
        last_line(output, 'not a clean commit') or last_line(output, 'Error'),
    )

    # 6. finalize refuses without evidence, then the full sequence
    empty = dict(settings['directories'], logs=os.path.join(scratch, 'empty_logs'))
    path = write_config(settings, scratch, f'{product}_nolog.yaml', directories=empty)
    status, output = run('finalize_wisosat_zarr.py', '--config', path, '--attrs', '--apply')
    results.check(f'{product}: finalize --attrs refuses an unverified store',
                  status != 0 and 'refusing' in output)
    status, output = run('verify_wisosat_zarr.py', '--config', base)
    sharded = sharded_stores(settings)
    for action in (['--attrs'], ['--expire'], ['--tag', 'fixture'], ['--expire'], ['--gc']):
        status, output = run('finalize_wisosat_zarr.py', '--config', base, *action, '--apply')
        if action == ['--expire'] and sharded and 'fixture' not in repository(settings, sharded[0]).list_tags():
            # expiry before the tag would drop the build log with nothing named
            results.check(f'{product}: finalize --expire refuses an untagged store',
                          status != 0 and 'tag the tip first' in output, last_line(output, 'ERROR'))
            continue
        results.check(f'{product}: finalize {action[0]}', status == 0, last_line(output, 'ERROR'))
    if sharded:
        kept = {store: [s.message for s in history(settings, store)] for store in sharded}
        results.check(
            f'{product}: --expire leaves each sharded store its tip and root only',
            all(len(messages) == 2 and not any(m.startswith(COMMIT_PREFIX) for m in messages)
                for messages in kept.values()),
            f'{kept[sharded[0]]}',
        )
    status, output = run('finalize_wisosat_zarr.py', '--config', base, '--status')
    results.check(
        f'{product}: every store reports finalized',
        status == 0 and output.count('remaining nothing, finalized') == len(stores),
        last_line(output, 'remaining') if 'remaining --' not in output else last_line(output, 'remaining --'),
    )
    # the build log is read from a store never expired (geolocation is never
    # sharded), so the check cannot pass on an empty list of commits
    attrs = dict(zarr.open_group(
        repository(settings, stores[0]).readonly_session(BRANCH).store, mode='r'
    ).attrs)
    results.check(
        f'{product}: finalized stores carry coverage and provenance',
        all(key in attrs for key in ('verification', 'history', 'date_created',
                                     'time_coverage_start', 'geospatial_lat_min')),
    )
    built = [snapshot.message for snapshot in history(settings, stores[0])
             if snapshot.message.startswith(COMMIT_PREFIX)]
    revisions = {COMMIT_RE.match(message)['revision'] for message in built}
    results.check(
        f'{product}: every build commit names its code revision, and the history too',
        revisions and None not in revisions
        and all(f'data_engineering_wiso-sat @ {revision}' in attrs['history']
                for revision in revisions),
        f'{sorted(map(str, revisions))}; {attrs.get("history", "")[:160]}',
    )
    status, output = run('verify_wisosat_zarr.py', '--config', base)
    results.check(f'{product}: finalized stores still verify',
                  status == 0 and 'stores verified' in output, last_line(output, 'checks,'))


def test_repeats(results, settings):
    """The build's repeat check, on a real granule of the fixture.

    A build that meets a repeat would need a raw file written with one, so the
    check itself is called here, on one granule read as the build reads it:
    twice in a row (a seam), and with its observations doubled (within).

    Args:
        results (Results): Where to record cases.
        settings (dict): The fixture configuration.
    """
    product = settings['product']
    source_name = source_product(settings)
    reader = load_reader(settings)
    granules = reader.list_granules(settings['directories']['raw'], **listing_options(settings, reader))
    time = time_source(source_name)
    location = tuple(coordinates(source_name)[name].original for name in ('lat', 'lon'))
    data = reader.read_granule(granules[1], [time, *location], time, row_rule(settings, granules))
    doubled = data._replace(n_obs=2 * data.n_obs, arrays={
        source: array._replace(values=np.concatenate([array.values, array.values]))
        for source, array in data.arrays.items()
    })
    for where, datas, message in (
        ('across a seam', [data, data], 'observations of the granule before it'),
        ('within a granule', [doubled], 'repeat another of the granule'),
    ):
        try:
            check_repeats(datas, time, location)
            error = ''
        except ValueError as raised:
            error = str(raised)
        results.check(f'{product}: the build refuses an observation repeated {where}',
                      message in error, error)
    results.check(f'{product}: the build passes a granule without repeats',
                  check_repeats([data], time, location) is not None)
    # a resumed build reads the seam from the store: granule 1 as stored must
    # give the keys granule 1 gives as read, or a repeat across a restart
    # would pass unseen
    stored = stored_seam_keys(repository(settings, GEOLOCATION), 2, repeat_look_back(settings))
    try:
        check_repeats([data], time, location, stored, repeat_look_back(settings))
        error = ''
    except ValueError as raised:
        error = str(raised)
    results.check(
        f'{product}: a resumed build checks its seam against the stored granule',
        stored is not None and len(stored[-1]) == data.n_obs
        and 'observations of the granule before it' in error,
        error or f'{len(stored[-1]) if stored else 0} stored keys',
    )
    if repeat_look_back(settings) > 1:
        # a repeat two granules back passes a look-back of one, but not the
        # declared look-back (CrIS R37)
        other = reader.read_granule(granules[0], [time, *location], time, row_rule(settings, granules))
        try:
            check_repeats([data, other, data], time, location, None, 2)
            error = ''
        except ValueError as raised:
            error = str(raised)
        results.check(f'{product}: the build refuses an observation repeated two granules back',
                      'the granule 2 before it' in error, error)


def test_rules(results):
    """Checks that hold for the whole codebase rather than one fixture.

    Args:
        results (Results): Collects the outcomes.
    """
    from finalize_wisosat_zarr import parse_dirty_notes
    from utils.zarr_utils import check_clean_tree

    def refuses(revision, settings):
        try:
            check_clean_tree(revision, settings)
        except ValueError:
            return True
        return False

    results.check(
        'a build refuses a dirty or unknown revision, unless the config is a fixture',
        refuses('abc1234-dirty', {}) and refuses('unknown', {})
        and not refuses('abc1234', {}) and not refuses('abc1234-dirty', {'allow_dirty_tree': True}),
    )
    allowing = [
        os.path.relpath(path, ROOT)
        for path in sorted(glob.glob(os.path.join(ROOT, 'config', '*', '*.yaml')))
        if load_config(path).get('allow_dirty_tree') and not path.endswith('_fixture.yaml')
    ]
    results.check('only fixture configs allow a dirty tree', not allowing, f'{allowing}')

    malformed = []
    for item in ('abc1234=clean revision', 'abc1234-dirty=', 'abc1234-dirty'):
        try:
            parse_dirty_notes([item])
            malformed.append(item)
        except ValueError:
            pass
    results.check(
        'finalize --dirty-notes takes only REV-dirty=TEXT',
        not malformed and parse_dirty_notes(['abc1234-dirty=notes']) == {'abc1234-dirty': 'notes'},
        f'accepted {malformed}',
    )


def main():
    parser = argparse.ArgumentParser(description='end to end test over every product fixture.')
    parser.add_argument('--products', type=str, default=None,
                        help='Comma separated subset. Default: every product with a fixture.')
    args = parser.parse_args()

    configs = sorted(glob.glob(os.path.join(ROOT, 'config', '*', 'config_zarr_fixture.yaml')))
    configs = [os.path.relpath(config, ROOT) for config in configs]
    if args.products:
        wanted = set(args.products.split(','))
        configs = [config for config in configs if config.split(os.sep)[1] in wanted]

    results = Results()
    test_rules(results)
    scratch_root = os.environ.get('TMPDIR') or None
    for config in configs:
        with tempfile.TemporaryDirectory(dir=scratch_root) as scratch:
            test_product(results, config, scratch)

    print(f'{results.n} cases, {len(results.failures)} failures over {len(configs)} products')
    for name in results.failures:
        print(f'failed: {name}')
    return 1 if results.failures else 0


if __name__ == '__main__':
    sys.exit(main())
