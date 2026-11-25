"""Check that one gridded set is a subset of another, in every cell of every period.

Written for request W3 (isotopes_transpiration, 2026-11-25): the TROPOMI
``clear`` set is ``clear_or_low_cloud`` without its low-cloud row, so on the
same grid and day each of its non-negative sums and its ``observation_count``
is at most the other set's. From gridding/, as a batch job (it reads every
chunk of 10 spatial stores per grid and set, ~200 GiB at 0.25 deg):

    uv run python tools/verify_subset.py --subset config/tropomi/config_grid_clear.yaml \\
        --superset config/tropomi/config_grid.yaml --superset config/tropomi/config_grid_0p5_1p0.yaml \\
        [--subset-tag TAG] [--superset-tag TAG] [--workers N]

Read only. Grids are matched by name: each grid of the subset config must be
in one superset config. Both stores must hold the same time axis.

Checked per (grid, quantity), over every cell and period:

- ``observation_count``: subset <= superset exactly (integers);
- the sums Σa, Σw, Σwδ², Σw², Σw²σ², ΣwA, ΣwW, ΣwWσ²: subset <= superset,
  to a relative tolerance (``RTOL``). Σwδ is not ordered (δD is mostly
  negative). The engine sums with ``np.bincount`` in batches of
  ``max_pairs`` pairs, and the batch boundaries differ between two
  selections, so a sum can exceed its superset's by rounding; the number of
  exact excesses and the largest relative excess are reported either way;
- no cell occupied in the subset and empty in the superset (follows from the
  count, reported on its own).
"""
import argparse
import multiprocessing
import os
import sys

import icechunk  # type: ignore
import numpy as np
import zarr  # type: ignore

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import config, stores  # noqa: E402
from utils.grids import from_spec  # noqa: E402

icechunk.set_logs_filter('error')
COUNT = 'observation_count'
ORDERED_SUMS = ('footprint_overlap_area_sum', 'gridding_weight_sum', 'gridding_weight_delta_d_squared_sum',
                'gridding_weight_squared_sum', 'gridding_weight_squared_delta_d_variance_sum',
                'gridding_weight_footprint_area_sum', 'gridding_weight_footprint_weight_sum',
                'gridding_weight_footprint_weight_delta_d_variance_sum')
RTOL = 1e-10


def open_array(path, variable, tag):
    repository = stores.open_repository(path)
    session = repository.readonly_session(tag=tag) if tag else repository.readonly_session(branch=stores.BRANCH)
    group = zarr.open_group(session.store, mode='r')
    return group[variable], group['time'][:]


def check(task):
    """One (grid, variable): stream both spatial stores chunk by chunk along time."""
    grid_name, variable, sub_path, sup_path, sub_tag, sup_tag = task
    sub, sub_time = open_array(sub_path, variable, sub_tag)
    sup, sup_time = open_array(sup_path, variable, sup_tag)
    if sub.shape != sup.shape or not np.array_equal(sub_time, sup_time):
        return {'grid': grid_name, 'variable': variable, 'error': f'shapes {sub.shape} / {sup.shape} or time differ'}
    step = sub.chunks[0]
    result = {'grid': grid_name, 'variable': variable, 'values': 0, 'exact_excess': 0, 'max_rel_excess': 0.0,
              'tolerance_excess': 0, 'occupied_only_in_subset': 0, 'nonfinite': 0,
              'subset_total': 0.0, 'superset_total': 0.0}
    for t0 in range(0, sub.shape[0], step):
        a = sub[t0:t0 + step]
        b = sup[t0:t0 + step]
        result['values'] += a.size
        result['subset_total'] += float(a.sum(dtype='float64'))
        result['superset_total'] += float(b.sum(dtype='float64'))
        result['nonfinite'] += int((~np.isfinite(a)).sum() + (~np.isfinite(b)).sum()) if a.dtype.kind == 'f' else 0
        excess = a > b
        result['exact_excess'] += int(excess.sum())
        if variable == COUNT:
            result['tolerance_excess'] += int(excess.sum())
            result['occupied_only_in_subset'] += int(((a > 0) & (b == 0)).sum())
        elif excess.any():
            rel = (a[excess] - b[excess]) / np.maximum(np.abs(b[excess]), np.finfo('float64').tiny)
            result['max_rel_excess'] = max(result['max_rel_excess'], float(rel.max()))
            result['tolerance_excess'] += int((rel > RTOL).sum())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--subset', required=True)
    parser.add_argument('--superset', required=True, action='append')
    parser.add_argument('--subset-tag')
    parser.add_argument('--superset-tag')
    parser.add_argument('--workers', type=int, default=len(os.sched_getaffinity(0)))
    args = parser.parse_args()
    # each config is loaded for its paths only; every config here uses the same key
    sub_settings = config.load_config(args.subset)
    sup_by_grid = {}
    for path in args.superset:
        settings = config.load_config(path)
        for spec in settings['grids']:
            sup_by_grid[from_spec(spec).name] = settings
    tasks = []
    for spec in sub_settings['grids']:
        grid = from_spec(spec)
        if grid.name not in sup_by_grid:
            sys.exit(f'grid {grid.name} is in no superset config')
        for variable in (COUNT, *ORDERED_SUMS):
            tasks.append((grid.name, variable,
                          config.store_path(sub_settings, 'spatial', 'day', grid.name, variable),
                          config.store_path(sup_by_grid[grid.name], 'spatial', 'day', grid.name, variable),
                          args.subset_tag, args.superset_tag))
    print(f'{len(tasks)} (grid, variable) pairs, {args.workers} workers; RTOL {RTOL}', flush=True)
    failures = 0
    with multiprocessing.get_context('spawn').Pool(min(args.workers, len(tasks))) as pool:
        for result in pool.imap_unordered(check, tasks):
            bad = ('error' in result or result['tolerance_excess'] or result['occupied_only_in_subset']
                   or result['nonfinite'])
            failures += bool(bad)
            print(f'{"FAIL" if bad else "ok"} {result}', flush=True)
    print(f'{len(tasks)} pairs checked, {failures} failures')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
