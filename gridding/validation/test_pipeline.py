"""End-to-end fixture test of the gridding pipeline.

    uv run python validation/stage_fixture.py      # once
    TMPDIR=<scratch> uv run python validation/test_pipeline.py

Drives the entry points as subprocesses on the TROPOMI fixture (the column
method: three orbits, 1° and EASE 25 km, day / 3day / month) and on the
AIRS v1 RS fixture (the profile method: five days, 1°, day / 3day), and
asserts on exit codes, log text and store contents. Every guard is watched
failing at least once (GLEAM finding 23), the verifier included: a build
with a different selection must fail verification. ~7 min on a login node.

Cases, in order (each depends on the ones before):
 1. unit: periods, grid tokens, nomenclature guard, the TROPOMI optical-thickness boundary (T24)
 2. config guard: only fixture configs allow a dirty tree
 3. build from nothing
 4. rebuild is a no-op
 5. resume: one target rewound to its first commit rebuilds to the same values
 6. verify spatial passes; a build it did not make fails it
 7. finalize spatial: --tag refused before --attrs; --attrs, --tag, --gc
 8. rechunk to temporal; again is a no-op; verify temporal; finalize temporal
 9. relocate: the stores moved to another root, --relocate rewrites their
    path attributes (tags and values kept, a second run a no-op), then back
10. unit, profile method: the column operator against a fine-grid integral,
    the TROPESS Summary boundary (DOF exactly 1.1), store-set names, L2
    tags per store
11. AIRS build from nothing (32 stores per frequency, a level dimension);
    the tiny days take a neighbour's orbit phase; rebuild is a no-op
12. AIRS verify spatial passes; the daytime selection fails it
13. AIRS finalize spatial, rechunk, verify and finalize temporal
14. AIRS daytime store set: its own names beside the full set, verified
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

from products import tropess, tropomi
from utils import airs_fov, columns, config, l2 as l2_utils, nomenclature, periods, stores
from utils.grids import Ease2Grid, LatLonGrid

GRIDDING = config.GRIDDING_ROOT
FIXTURE = GRIDDING / 'config' / 'tropomi' / 'config_grid_fixture.yaml'
AIRS_FIXTURE = GRIDDING / 'config' / 'airs_rs' / 'config_grid_fixture.yaml'
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


def airs_settings():
    """The AIRS fixture's settings; loading them makes its gridding key the one in use."""
    return config.load_config(AIRS_FIXTURE)


def airs_paths(layout, frequency, loaded=None):
    loaded = loaded or airs_settings()
    return [config.store_path(loaded, layout, frequency, 'latlon_1p0x1p0', row['canonical_name'])
            for row in nomenclature.quantities().values()]


def open_variable(path):
    """A store's data variable at main, by the store's variable slot."""
    name = os.path.basename(path).rsplit('.', 2)[-2]
    return zarr.open_group(stores.open_repository(path).readonly_session(branch='main').store, mode='r')[name]


def derived_config(directory, base=FIXTURE, **changes):
    """A fixture config with some keys replaced, written to a temporary file."""
    data = yaml.safe_load(base.read_text())
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
    # only the layouts, never the root: it is <product>/l3/, whose parent holds the fixture's L2 stores
    for layout in config.LAYOUTS:
        shutil.rmtree(os.path.join(settings()['directories']['zarr'], layout), ignore_errors=True)
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


@case('relocate: a moved root gets its path attributes rewritten, values and tags kept')
def test_relocate():
    root = settings()['directories']['zarr']
    spatial = target_paths('spatial', 'latlon_1p0x1p0', 'day')
    before = digest(spatial)
    with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
        moved = os.path.join(directory, 'moved')
        os.makedirs(moved)
        for layout in config.LAYOUTS:
            shutil.move(os.path.join(root, layout), os.path.join(moved, layout))
        try:
            data = yaml.safe_load(FIXTURE.read_text())
            elsewhere = derived_config(directory, directories={**data['directories'], 'zarr': moved},
                                       log_file='grid_tropomi_fixture_relocate.log')
            name = os.path.basename(spatial[0])
            for layout in config.LAYOUTS:
                base = ('finalize_grid_wisosat.py', '--layout', layout)
                assert 'stale paths none' not in script(*base, '--status', config_path=elsewhere)
                assert 'APPLY' not in script(*base, '--relocate', config_path=elsewhere)
                script(*base, '--relocate', '--apply', config_path=elsewhere)
                output = script(*base, '--relocate', config_path=elsewhere)
                assert 'APPLY' not in output and 'nothing to do' in output
                assert 'stale paths none' in script(*base, '--status', config_path=elsewhere)
            moved_spatial = os.path.join(moved, 'spatial', name)
            repository = stores.open_repository(moved_spatial)
            attrs = zarr.open_group(repository.readonly_session(branch='main').store, mode='r').attrs
            assert attrs['related_store'] == os.path.join(moved, 'temporal', name), attrs['related_store']
            assert attrs['source_l2_stores'] == settings()['l2']['directory']
            assert f'moved from {root}/spatial/ to {moved}/spatial/' in attrs['history'], attrs['history']
            # the tag still names the build's snapshot, with the old paths
            tagged = zarr.open_group(repository.readonly_session(tag='fixture-spatial').store, mode='r').attrs
            assert tagged['related_store'] == os.path.join(root, 'temporal', name)
            temporal = zarr.open_group(stores.open_repository(os.path.join(moved, 'temporal', name))
                                       .readonly_session(branch='main').store, mode='r').attrs
            assert temporal['rechunked_from'].startswith(f'{moved_spatial} at tag fixture-spatial, by ')
            assert temporal['related_store'] == moved_spatial
            output = script('verify_grid_wisosat.py', '--layout', 'spatial', '--phases', 'structure',
                            config_path=elsewhere)
            assert 'stores verified' in output and ', 0 failures' in output
        finally:
            for layout in config.LAYOUTS:
                shutil.move(os.path.join(moved, layout), os.path.join(root, layout))
    # moved back: the fixture config's paths again
    for layout in config.LAYOUTS:
        script('finalize_grid_wisosat.py', '--layout', layout, '--relocate', '--apply')
        assert 'stale paths none' in script('finalize_grid_wisosat.py', '--layout', layout, '--status')
    assert digest(spatial) == before


@case('unit, profile method: column operator, Summary boundary, store-set names, tags per store')
def test_profile_units():
    # the column operator: exact for a mole fraction linear in ln p, against a fine-grid integral
    pressure = np.array([[np.nan, 95000.0, 82540.0, 68129.0, 51090.0, 34807.0, 23714.0, 13335.0, 10.0]])
    q = np.array([[np.nan, 9e-3, 6e-3, 3e-3, 1e-3, 3e-4, 5e-5, 5e-6, 4e-6]])
    ratio = np.array([[np.nan, 2.9e-4, 2.8e-4, 2.7e-4, 2.5e-4, 2.2e-4, 1.9e-4, 1.5e-4, 2.5e-4]])
    h2o, column_ratio, shares = columns.partial_columns(pressure, q, ratio, 85000.0, 25000.0)
    ln_p = np.linspace(np.log(85000.0), np.log(25000.0), 200_001)
    valid = np.isfinite(pressure[0])
    fine_q = np.interp(-ln_p, -np.log(pressure[0][valid]), q[0][valid])
    fine_hdo = np.interp(-ln_p, -np.log(pressure[0][valid]), (ratio * q)[0][valid])
    dp = -np.diff(np.exp(ln_p))
    integral_q = (0.5 * (fine_q[1:] + fine_q[:-1]) * dp).sum()
    integral_hdo = (0.5 * (fine_hdo[1:] + fine_hdo[:-1]) * dp).sum()
    assert abs(h2o[0] / (integral_q * columns.MOL_M2_PER_PA) - 1) < 1e-8
    assert abs(column_ratio[0] / (integral_hdo / integral_q) - 1) < 1e-8
    whole, _, shares = columns.partial_columns(pressure, q, ratio)
    assert abs(np.nansum(shares) / whole[0] - 1) < 1e-13 and shares[0, 0] == 0
    # a cut above the surface starts at the surface; no layer between the cuts gives no column
    assert np.isfinite(columns.partial_columns(pressure, q, ratio, 99000.0, 25000.0)[0][0])
    assert np.isnan(columns.partial_columns(pressure, q, ratio, 5.0, 1.0)[0][0])
    # the Summary rule (D5): strictly above 1.1 at float32, or DOF missing and the marker written;
    # daytime (D7) also needs flag 1, and the flag's fill is not daytime. Build and verifier agree
    import verify_grid_wisosat as verifier
    above = np.nextafter(np.float32(1.1), np.float32(2))
    values = {tropess.DOF: np.array([1.1, above, np.nan, np.nan, 2.0, 2.0], dtype='float32'),
              tropess.SUMMARY_MARKER: np.array([-200, -200, -200, np.nan, -200, -200], dtype='float32'),
              tropess.DAY_NIGHT: np.int32([1, 1, 1, 1, 0, -999])}
    fills = {tropess.DOF: None, tropess.SUMMARY_MARKER: None, tropess.DAY_NIGHT: -999}
    frame = {**values, tropess.DAY_NIGHT: np.array([1, 1, 1, 1, 0, np.nan])}
    for level, expected in (('summary', [False, True, True, False, True, True]),
                            ('summary_daytime', [False, True, True, False, False, False])):
        assert list(tropess.select(values, fills, {'quality_level': level})) == expected, level
        assert list(verifier.tropess_passes(frame, level)) == expected, level
    # a store set goes after the version in the gridded names only (D7, 7.1); L2 names keep theirs
    loaded = airs_settings()
    daytime = {**loaded, 'store_set': 'daytime'}
    name = os.path.basename(config.store_path(daytime, 'spatial', 'day', 'latlon_1p0x1p0', 'observation_count'))
    assert name == 'wisosat.airs.v_1.rs.daytime.day.latlon_1p0x1p0.observation_count.zarr', name
    assert config.l2_store_path(daytime, 'pressure') == config.l2_store_path(loaded, 'pressure')
    # L2 at a tag per store
    assert config.l2_tag(loaded, 'scanline_index') == 'fixture-20261113-footprint'
    assert config.l2_tag(loaded, 'pressure') == 'fixture-20261113'
    assert 'scanline_index: fixture-20261113-footprint' in config.l2_tag_text(loaded)
    assert nomenclature.has_levels() and len(nomenclature.quantities()) == 32
    settings()
    assert not nomenclature.has_levels() and len(nomenclature.quantities()) == 17


@case('AIRS build from nothing; tiny days take a neighbour\'s orbit phase; rebuild is a no-op')
def test_airs_build():
    loaded = airs_settings()
    for layout in config.LAYOUTS:
        shutil.rmtree(os.path.join(loaded['directories']['zarr'], layout), ignore_errors=True)
    output = script('grid_wisosat.py', config_path=AIRS_FIXTURE)
    assert 'build complete' in output and 'committed' in output
    # one row a day is the masked first profile of a Standard file (R22): no column, not gridded
    assert '2014-04-08: 2,659 rows, 1,604 pass quality, 0 over a threshold, 1 missing an input' in output, output[-3000:]
    for frequency in ('day', '3day'):
        paths = airs_paths('spatial', frequency, loaded)
        assert len(paths) == 32 and all(os.path.isdir(path) for path in paths)
    by_name = {os.path.basename(path).rsplit('.', 2)[-2]: path for path in airs_paths('spatial', 'day', loaded)}
    level = open_variable(by_name['water_vapor_delta_d'])
    assert level.metadata.dimension_names == ('time', 'level', 'lat', 'lon') and level.shape == (6, 16, 180, 360)
    assert open_variable(by_name['pressure_surface']).shape == (6, 180, 360)
    # every gridded retrieval has a surface; a level counts only above it, so counts fall towards the ground
    count = open_variable(by_name['observation_count'])[:]
    assert np.array_equal(open_variable(by_name['observation_count_surface'])[:], count)
    level_count = open_variable(by_name['observation_count_level'])[:]
    assert (level_count <= count[:, None]).all() and level_count[:, 0].sum() < level_count[:, 5].sum()
    assert np.array_equal(level_count[:, 5:], np.broadcast_to(count[:, None], level_count[:, 5:].shape))
    # 3day sums are their days' sums
    name = 'gridding_weight_level_delta_d_sum'
    three = open_variable({os.path.basename(p).rsplit('.', 2)[-2]: p for p in airs_paths('spatial', '3day', loaded)}[name])[:]
    days = open_variable(by_name[name])[:]
    assert np.allclose(three[1], days[2:5].sum(axis=0), rtol=1e-12, atol=0)
    # 2014-04-05 and -06 hold 12 and 13 retrievals: no sound fit of their own, so the nearest sound day's
    phases = l2_utils.AirsPhases(l2_utils.L2(loaded), loaded['footprint'])
    assert [airs_fov.is_sound(phases.own(k)) for k in range(5)] == [True, False, False, True, True]
    assert phases.resolve(1)[1] == 1 and phases.resolve(1)[0] is phases.own(0)
    assert phases.resolve(2)[1] == -1 and phases.resolve(2)[0] is phases.own(3)
    before = digest(airs_paths('spatial', 'day', loaded))
    assert 'nothing to do' in script('grid_wisosat.py', config_path=AIRS_FIXTURE)
    assert digest(airs_paths('spatial', 'day', loaded)) == before


@case('AIRS verify spatial passes; the daytime selection fails it')
def test_airs_verify_spatial():
    output = script('verify_grid_wisosat.py', '--layout', 'spatial', config_path=AIRS_FIXTURE)
    assert 'stores verified' in output and ', 0 failures' in output
    with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
        data = yaml.safe_load(AIRS_FIXTURE.read_text())
        mutant = derived_config(directory, base=AIRS_FIXTURE, log_file='grid_airs_rs_fixture_mutant.log',
                                selection={**data['selection'], 'quality_level': 'summary_daytime'},
                                frequencies=['day'])
        output = script('verify_grid_wisosat.py', '--layout', 'spatial', '--phases', 'samples', expect=1,
                        config_path=mutant)
        assert 'FAIL' in output and 'stores verified' not in output


@case('AIRS finalize spatial, rechunk, verify and finalize temporal')
def test_airs_temporal():
    base = ('finalize_grid_wisosat.py', '--layout', 'spatial')
    script(*base, '--attrs', '--apply', config_path=AIRS_FIXTURE)
    script(*base, '--tag', 'fixture-spatial', '--apply', config_path=AIRS_FIXTURE)
    script('rechunk_wisosat.py', config_path=AIRS_FIXTURE)
    loaded = airs_settings()
    by_name = {os.path.basename(path).rsplit('.', 2)[-2]: path for path in airs_paths('temporal', 'day', loaded)}
    # the whole record per tile; one level per chunk in the temporal layout
    assert open_variable(by_name['water_vapor_delta_d']).chunks == (6, 1, 20, 20)
    assert open_variable(by_name['observation_count']).chunks == (6, 20, 20)
    output = script('verify_grid_wisosat.py', '--layout', 'temporal', config_path=AIRS_FIXTURE)
    assert 'stores verified' in output and ', 0 failures' in output
    base = ('finalize_grid_wisosat.py', '--layout', 'temporal')
    script(*base, '--attrs', '--apply', config_path=AIRS_FIXTURE)
    script(*base, '--tag', 'fixture-temporal', '--apply', config_path=AIRS_FIXTURE)
    assert 'missing attrs none' in script(*base, '--status', config_path=AIRS_FIXTURE)


@case('AIRS daytime store set: its own names beside the full set, verified')
def test_airs_daytime():
    with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
        data = yaml.safe_load(AIRS_FIXTURE.read_text())
        daytime = derived_config(directory, base=AIRS_FIXTURE, log_file='grid_airs_rs_fixture_daytime.log',
                                 store_set='daytime', frequencies=['day'],
                                 selection={**data['selection'], 'quality_level': 'summary_daytime'})
        output = script('grid_wisosat.py', config_path=daytime)
        assert 'build complete' in output
        loaded = config.load_config(daytime)
        paths = airs_paths('spatial', 'day', loaded)
        assert all('.v_1.rs.daytime.day.' in os.path.basename(path) and os.path.isdir(path) for path in paths)
        full = airs_paths('spatial', 'day', airs_settings())
        assert not set(paths) & set(full)
        pick = [os.path.basename(path).endswith('.observation_count.zarr') for path in paths].index(True)
        day_count, all_count = open_variable(paths[pick])[:], open_variable(full[pick])[:]
        assert (day_count <= all_count).all() and 0 < day_count.sum() < all_count.sum()
        output = script('verify_grid_wisosat.py', '--layout', 'spatial', config_path=daytime)
        assert 'stores verified' in output and ', 0 failures' in output


def main():
    for fixture in (settings(), airs_settings()):
        if not os.path.isdir(fixture['l2']['directory']):
            sys.exit('stage the fixtures first: uv run python validation/stage_fixture.py')
    settings()
    for test in (test_units, test_config_guard, test_build, test_noop, test_resume, test_verify_spatial,
                 test_finalize_spatial, test_temporal, test_relocate, test_profile_units, test_airs_build,
                 test_airs_verify_spatial, test_airs_temporal, test_airs_daytime):
        test()
    print(f'{len(RESULTS)} cases passed')


if __name__ == '__main__':
    main()
