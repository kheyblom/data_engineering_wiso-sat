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
4. the verifier must fail on a tampered value, naming the store;
5. guards: an undeclared missing day, a wrong processor version, a run that
   omits the quality flags, an unknown variable, and (where the product has
   them) an undeclared empty granule directory or unreadable file;
6. finalize: ``--attrs`` refuses without verification evidence; the full
   ``--attrs``, ``--tag``, ``--gc`` sequence; then the verifier still passes.

Run from the repo root after staging each fixture:

    uv run python validation/stage_tropomi.py
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

from utils.path_utils import GEOLOCATION, load_config, run_stores, store_path
from utils.zarr_utils import BRANCH

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
                      f'run validation/stage_{product}.py first')
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
    value = np.asarray(array[5])
    array[5] = value + 1 if np.isfinite(value) else 1
    session.commit('write granules tamper')
    status, output = run('verify_wisosat_zarr.py', '--config', base, '--phases', 'values')
    results.check(
        f'{product}: verifier fails on one changed value',
        status != 0 and f'FAIL  {target}/{target}: every observation matches raw' in output,
        last_line(output, f'{target}/{target}: every'),
    )
    repo.reset_branch(BRANCH, tip)

    # 5. guards that must stop a build before it writes
    guards = {
        'an undeclared missing day': ({'expected_missing_days': []}, 'not declared'),
        'a wrong processor version': ({'version': '0.0'}, 'processor version'),
        'omitted quality flags': (
            {'variables': [v for v in settings['variables'] if not v.startswith('quality_flags')]},
            'quality flags',
        ),
        'an unknown variable': ({'variables': settings['variables'] + ['no_such_variable']}, 'has no row'),
    }
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
        if 'version' in changes:
            wrong = dict(settings, version=changes['version'], directories=directories)
            results.check(
                f'{product}: a refused version created no store',
                not os.path.exists(store_path(wrong, GEOLOCATION)),
            )

    # 6. finalize refuses without evidence, then the full sequence
    empty = dict(settings['directories'], logs=os.path.join(scratch, 'empty_logs'))
    path = write_config(settings, scratch, f'{product}_nolog.yaml', directories=empty)
    status, output = run('finalize_wisosat_zarr.py', '--config', path, '--attrs', '--apply')
    results.check(f'{product}: finalize --attrs refuses an unverified store',
                  status != 0 and 'refusing' in output)
    status, output = run('verify_wisosat_zarr.py', '--config', base)
    for action in (['--attrs'], ['--tag', 'fixture'], ['--gc']):
        status, output = run('finalize_wisosat_zarr.py', '--config', base, *action, '--apply')
        results.check(f'{product}: finalize {action[0]}', status == 0, last_line(output, 'ERROR'))
    attrs = dict(zarr.open_group(
        repository(settings, stores[-1]).readonly_session(BRANCH).store, mode='r'
    ).attrs)
    results.check(
        f'{product}: finalized stores carry coverage and provenance',
        all(key in attrs for key in ('verification', 'history', 'date_created',
                                     'time_coverage_start', 'geospatial_lat_min')),
    )
    status, output = run('verify_wisosat_zarr.py', '--config', base)
    results.check(f'{product}: finalized stores still verify',
                  status == 0 and 'stores verified' in output, last_line(output, 'checks,'))


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
