"""End-to-end fixture test of the gridding pipeline.

    uv run python validation/stage_fixture.py      # once
    TMPDIR=<scratch> uv run python validation/test_pipeline.py

Drives the entry points as subprocesses on the TROPOMI fixture (three
orbits, 1° and EASE 25 km, day / 3day / month) and asserts on exit codes,
log text and store contents. Every guard is watched failing at least once
(GLEAM finding 23), the verifier included: a build with a different
selection must fail verification. ~5 min on a login node.

Cases, in order (each depends on the ones before):
 1. unit: periods, grid tokens, nomenclature guard, the TROPOMI optical-thickness boundary (T24)
 2. config guard: only fixture configs allow a dirty tree
 3. build from nothing
 4. rebuild is a no-op
 5. resume: one target rewound to its first commit rebuilds to the same values
 6. verify spatial passes; a build it did not make fails it
 7. finalize spatial: --tag refused before --attrs; --attrs, --tag, --gc
 8. rechunk to temporal; again is a no-op; verify temporal; finalize temporal
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import icechunk  # type: ignore
import numpy as np
import yaml  # type: ignore
import zarr  # type: ignore

from products import tropomi
from utils import config, nomenclature, periods, stores
from utils.grids import Ease2Grid, LatLonGrid

GRIDDING = config.GRIDDING_ROOT
FIXTURE = GRIDDING / 'config' / 'tropomi' / 'config_grid_fixture.yaml'
PYTHON = [sys.executable]
icechunk.set_logs_filter('error')
RESULTS = []


def case(name):
    def wrap(function):
        def run():
            print(f'--- {name}', flush=True)
            function()
            RESULTS.append(name)
            print(f'    ok', flush=True)
        return run
    return wrap


def script(*args, expect=0, config_path=FIXTURE):
    """Run an entry point from gridding/; assert its exit code; return its output."""
    command = [*PYTHON, *args, '--config', str(config_path)]
    result = subprocess.run(command, cwd=GRIDDING, capture_output=True, text=True)
    output = result.stdout + result.stderr
    if (result.returncode == 0) != (expect == 0):
        print(output[-4000:])
        raise AssertionError(f'{" ".join(args)}: exit {result.returncode}, expected {"0" if expect == 0 else "non-zero"}')
    return output


def settings():
    return config.load_config(FIXTURE)


def target_paths(layout, grid_name, frequency):
    return [config.store_path(settings(), layout, frequency, grid_name, row['canonical_name'])
            for row in nomenclature.quantities().values()]


def digest(paths):
    """A hash of every stored array of the stores, read at main."""
    h = hashlib.sha256()
    for path in paths:
        group = zarr.open_group(stores.open_repository(path).readonly_session(branch='main').store, mode='r')
        for name, array in sorted(group.arrays()):
            h.update(name.encode())
            h.update(np.ascontiguousarray(array[...]).tobytes())
    return h.hexdigest()


def derived_config(directory, **changes):
    """The fixture config with some keys replaced, written to a temporary file."""
    data = yaml.safe_load(FIXTURE.read_text())
    for key, value in changes.items():
        data[key] = value
    path = Path(directory) / 'config.yaml'
    path.write_text(yaml.safe_dump(data))
    return path


@case('unit: periods, grid tokens, nomenclature guard')
def test_units():
    day = periods.day_number('2020-06-30')
    assert periods.period_of(day, 'day') == (day, day + 1)
    start, end = periods.period_of(day, '3day')
    assert start % 3 == 0 and end - start == 3 and start <= day < end
    assert periods.period_of(day, 'month') == (periods.day_number('2020-06-01'), periods.day_number('2020-07-01'))
    assert periods.period_of(day, '3month') == (periods.day_number('2020-04-01'), periods.day_number('2020-07-01'))
    for bad in ('5month', 'week', '0day'):
        try:
            periods.parse(bad)
        except ValueError:
            continue
        raise AssertionError(f'{bad} accepted')
    assert LatLonGrid(0.25).name == 'latlon_0p25x0p25' and LatLonGrid(1).name == 'latlon_1p0x1p0'
    assert Ease2Grid('M25km').name == 'ease2_m25km' and Ease2Grid('M12.5km').name == 'ease2_m12p5km'
    try:
        LatLonGrid(0.7)
    except ValueError:
        pass
    else:
        raise AssertionError('0.7 degree accepted')
    # T24 (user decision 2026-11-10): optical thickness exactly 0.3 (float32) is low cloud, in the
    # build's selection and the verifier's, and just below it is clear: every value falls in a row
    import verify_grid_wisosat as verifier
    tau = np.array([0.3, np.nextafter(np.float32(0.3), np.float32(0))], dtype='float32')
    values = {'quality_flags_retrieval': np.int32([0, 0]), 'iterations_retrieval': np.int32([5, 5]),
              'solar_zenith_angle': np.float32([40, 40]), 'chi_squared_retrieval': np.float32([100, 100]),
              'spectral_point_count_retrieval': np.int32([300, 300]), 'chi_squared_prefit': np.float32([100, 100]),
              'spectral_point_count_prefit': np.int32([300, 300]), 'optical_thickness_scattering_layer': tau,
              'albedo_surface_2365nm': np.float32([0.05, 0.05]), 'height_scattering_layer': np.float32([1.0, 1.0])}
    fills = {name: (-2147483647 if array.dtype.kind == 'i' else None) for name, array in values.items()}
    assert tropomi.select(values, fills, {'quality_level': 'clear_or_low_cloud'}).all()
    assert list(tropomi.select(values, fills, {'quality_level': 'clear'})) == [False, True]
    frame = {name: (array.astype('float64') if array.dtype.kind == 'i' else array) for name, array in values.items()}
    assert verifier.tropomi_passes(frame, 'clear_or_low_cloud').all()
    assert list(verifier.tropomi_passes(frame, 'clear')) == [False, True]
    try:
        nomenclature.check(settings(), ['5day'])
    except ValueError as error:
        assert '5day' in str(error)
    else:
        raise AssertionError('a frequency without a nomenclature row was accepted')


@case('config guard: only fixture configs allow a dirty tree')
def test_config_guard():
    for path in (GRIDDING / 'config').glob('*/config_grid*.yaml'):
        allowed = bool(yaml.safe_load(path.read_text()).get('allow_dirty_tree'))
        assert allowed == ('fixture' in path.name), f'{path.name}: allow_dirty_tree={allowed}'
    if config.uncommitted_changes():
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            strict = derived_config(directory, allow_dirty_tree=False)
            output = script('grid_wisosat.py', expect=1, config_path=strict)
            assert 'uncommitted changes' in output
    else:
        print('    (tree is clean: the refusal itself was not exercised)')


@case('build from nothing')
def test_build():
    root = settings()['directories']['zarr']
    shutil.rmtree(root, ignore_errors=True)
    output = script('grid_wisosat.py')
    assert 'build complete' in output
    for grid_name in ('latlon_1p0x1p0', 'ease2_m25km'):
        for frequency in ('day', '3day', 'month'):
            assert all(os.path.isdir(path) for path in target_paths('spatial', grid_name, frequency))


@case('rebuild is a no-op')
def test_noop():
    before = digest(target_paths('spatial', 'latlon_1p0x1p0', 'day'))
    output = script('grid_wisosat.py')
    assert 'nothing to do' in output
    assert digest(target_paths('spatial', 'latlon_1p0x1p0', 'day')) == before


@case('resume: a rewound target rebuilds to the same values')
def test_resume():
    paths = target_paths('spatial', 'ease2_m25km', 'day')
    before = digest(paths)
    for path in paths:
        repository = stores.open_repository(path)
        commits = list(repository.ancestry(branch='main'))
        first_append = [snapshot for snapshot in commits if snapshot.message.startswith('write periods')][-1]
        repository.reset_branch('main', first_append.id)
    output = script('grid_wisosat.py')
    assert 'ease2_m25km day: 1 of 2 periods stored' in output, output[-2000:]
    assert digest(paths) == before


@case('verify spatial passes; a different build fails it')
def test_verify_spatial():
    output = script('verify_grid_wisosat.py', '--layout', 'spatial')
    assert 'stores verified' in output and ', 0 failures' in output
    # the same stores checked against a stricter selection: the recomputation differs
    with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
        data = yaml.safe_load(FIXTURE.read_text())
        mutant = derived_config(directory, log_file='grid_tropomi_fixture_mutant.log',
                                selection={**data['selection'], 'thresholds': {'water_vapor_column_h2o': {'max': 2000.0}}},
                                grids=[{'type': 'latlon', 'resolution': 1.0}], frequencies=['day'])
        output = script('verify_grid_wisosat.py', '--layout', 'spatial', '--phases', 'samples', expect=1,
                        config_path=mutant)
        assert 'FAIL' in output and 'stores verified' not in output


@case('finalize spatial')
def test_finalize_spatial():
    base = ('finalize_grid_wisosat.py', '--layout', 'spatial')
    output = script(*base, '--tag', 'fixture-spatial', '--apply', expect=1)
    assert 'run --attrs first' in output
    assert 'APPLY' not in script(*base, '--attrs')
    script(*base, '--attrs', '--apply')
    script(*base, '--tag', 'fixture-spatial', '--apply')
    output = script(*base, '--tag', 'fixture-spatial', '--apply', expect=1)
    assert 'exists' in output
    script(*base, '--gc')
    output = script(*base, '--status')
    assert "missing attrs none" in output and 'fixture-spatial' in output


@case('rechunk, verify and finalize temporal')
def test_temporal():
    shutil.rmtree(os.path.join(settings()['directories']['zarr'], 'temporal'), ignore_errors=True)
    script('rechunk_wisosat.py')
    paths = target_paths('temporal', 'latlon_1p0x1p0', 'month')
    commits = [len(list(stores.open_repository(path).ancestry(branch='main'))) for path in paths]
    script('rechunk_wisosat.py')
    assert commits == [len(list(stores.open_repository(path).ancestry(branch='main'))) for path in paths]
    output = script('verify_grid_wisosat.py', '--layout', 'temporal')
    assert 'stores verified' in output
    base = ('finalize_grid_wisosat.py', '--layout', 'temporal')
    script(*base, '--attrs', '--apply')
    script(*base, '--tag', 'fixture-temporal', '--apply')


def main():
    if not os.path.isdir(settings()['l2']['directory']):
        sys.exit('stage the fixture first: uv run python validation/stage_fixture.py')
    for test in (test_units, test_config_guard, test_build, test_noop, test_resume, test_verify_spatial,
                 test_finalize_spatial, test_temporal):
        test()
    print(f'{len(RESULTS)} cases passed')


if __name__ == '__main__':
    main()
