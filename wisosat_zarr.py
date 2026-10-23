"""Build the icechunk zarr stores of one WISO-SAT Level 2 product from raw files.

One config drives one product. A run builds the product's ``geolocation``
store plus one store per variable the config lists, in a single pass over the
granules: each source file is opened once and its variables go to every store
that still needs them (decided 2026-10-14, to avoid reopening every TROPOMI
orbit once per store). Every store is still written from the raw files; none
is derived from another.

The pass, per batch of ``granules_per_commit`` granules:

1. read the granules in a pool of ``num_workers`` processes (HDF5 is not
   thread safe), prefetching the next batch while this one is written. The
   reader keeps only rows that are observations, with time, latitude and
   longitude all written (``RowRule`` in ``utils/granules.py``);
2. check that every granule declares the configured processor version and
   that time never decreases, within or across granules, unless the config
   keeps the source order of files that are not in time order
   (``time_order: source``, the style guide's exception; TROPESS), where no
   observation may repeat another's time, lat and lon instead. Rows a
   config declares as repeats of others (``declared_rows_left_out``) are
   left out by the reader, once their declared match is confirmed;
3. append each store's slice, data and granule index together, as one commit
   per store.

Each store resumes on its own from its granule index, so a run killed between
two stores' commits picks up exactly where each left off. Before anything is
read, the listing is checked: granules unique, and the days without one exactly
the config's ``expected_missing_days``.

**Stores with a process of their own** (``own_process_stores``, user decision
2026-10-19; TESTING.md finding 12). A store whose sources no other store reads,
such as TROPOMI's 50-layer kernels, gains nothing from the shared pass: its
~170 MB per orbit would be read by a worker only to be pickled, piped and
unpickled into this process, which cost more CPU than the reading. Each such
store runs the same pass in a process of its own, reading its sources there,
alongside the shared pass for the other stores. Its large sources are still
read once; only the small location sources (time, lat, lon) are read again
per store.
"""

import argparse
import concurrent.futures
import logging
import multiprocessing
import os

from utils.granules import check_coverage, check_order, check_repeats, check_time
from utils.log_utils import log_peak_memory, setup_logging
from utils.nomenclature import coordinates, variables
from utils.path_utils import (
    GEOLOCATION,
    listing_options,
    load_config,
    load_reader,
    log_path,
    run_stores,
    source_product,
    store_path,
)
from utils.zarr_utils import (
    COMMIT_MESSAGE,
    assemble,
    build_encoding,
    check_clean_tree,
    check_fill_config,
    code_revision,
    committed_state,
    configure_runtime,
    global_attrs,
    log_key,
    open_repository,
    resolve_chunks,
    resolve_compression,
    row_rule,
    store_sources,
    stored_seam_keys,
    time_order,
    time_source,
    write_append,
)

LOG = logging.getLogger(__name__)


def check_versions(datas, settings):
    """Fail unless every granule declares the configured version and platform.

    The version names every store, so a granule from another processor version
    would be filed under a name that misdescribes it. The product token does
    too where one reader serves several platforms (GOSAT and GOSAT-2): such a
    reader reports each granule's platform, and the config must declare it.
    Elsewhere both sides are None.

    Args:
        datas (list): GranuleData just read.
        settings (dict): The loaded configuration.

    Raises:
        ValueError: On any mismatch.
    """
    expected = str(settings['version'])
    wrong = [(data.granule.id, data.version) for data in datas if data.version != expected]
    if wrong:
        raise ValueError(
            f'{len(wrong)} granules declare a processor version other than the '
            f'configured {expected!r}: {wrong[:5]}'
        )
    platform = settings.get('platform')
    wrong = [(data.granule.id, data.platform) for data in datas if data.platform != platform]
    if wrong:
        raise ValueError(
            f'{len(wrong)} granules declare a platform other than the configured '
            f'{platform!r}: {wrong[:5]}'
        )


class Reader:
    """Reads batches of granules, in a process pool or in this process.

    Attributes:
        reader (module): The product's reader.
        sources (list): Source paths every read returns.
        time (str): The time coordinate's source path.
        rule (RowRule): Which rows are observations.
    """

    def __init__(self, reader, sources, time, rule, num_workers):
        self.reader = reader
        self.sources = sources
        self.time = time
        self.rule = rule
        # spawn rather than fork: by the time the pool starts, icechunk's own
        # threads are running in this process, and forking a threaded process
        # can deadlock the child
        self.pool = (
            concurrent.futures.ProcessPoolExecutor(
                max_workers=num_workers, mp_context=multiprocessing.get_context('spawn')
            )
            if num_workers > 1 else None
        )

    def submit(self, granules):
        """Start reading a batch.

        Args:
            granules (list): The batch.

        Returns:
            list: One future per granule, or the results directly without a pool.
        """
        if self.pool is None:
            return [
                self.reader.read_granule(g, self.sources, self.time, self.rule) for g in granules
            ]
        return [
            self.pool.submit(self.reader.read_granule, g, self.sources, self.time, self.rule)
            for g in granules
        ]

    def collect(self, pending):
        """Wait for a batch submitted with ``submit``.

        Args:
            pending (list): From ``submit``.

        Returns:
            list: GranuleData in submission order.
        """
        if self.pool is None:
            return pending
        return [future.result() for future in pending]

    def close(self):
        """Shut the pool down."""
        if self.pool is not None:
            self.pool.shutdown()


def own_process_stores(settings):
    """The stores the config builds each in a process of its own, checked.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        list: Store variable slots, in the config's order.

    Raises:
        ValueError: If one is not a variable store of this config, or is
            listed twice. The geolocation store always takes the shared pass,
            which the time checks run on.
    """
    own = list(settings.get('own_process_stores') or [])
    variable_stores = run_stores(settings)[1:]
    bad = [store for store in own if store not in variable_stores]
    if bad or len(set(own)) != len(own):
        raise ValueError(
            f'own_process_stores must name variable stores of this config, once '
            f'each; {bad or own} is not'
        )
    return own


def prepare(settings):
    """Check everything a pass relies on, once, before anything is written.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        tuple: The granule listing and the code revision.
    """
    source_name = source_product(settings)
    reader = load_reader(settings)
    configure_runtime(settings)
    resolve_chunks(settings)
    resolve_compression(settings)
    own_process_stores(settings)
    LOG.info(f'time order: {time_order(settings)}')
    log_key(source_name)
    # stamped on every commit, so finalize can say which code wrote what;
    # checked before anything is listed or written
    revision = code_revision()
    LOG.info(f'code revision {revision}')
    check_clean_tree(revision, settings)

    known = [entry.original for entry in variables(source_name).values()]
    known += [entry.original for entry in coordinates(source_name).values()]
    check_fill_config(settings, known)

    raw = settings['directories']['raw']
    LOG.info(f'listing granules under {raw}')
    granules = reader.list_granules(
        raw,
        expected_empty=settings.get('expected_empty_granules') or [],
        expected_unreadable=settings.get('expected_unreadable_granules') or [],
        **listing_options(settings, reader),
    )
    check_order(granules)
    missing = check_coverage(granules, settings, getattr(reader, 'COVERAGE_FREQUENCY', 'D'))
    LOG.info(
        f'{len(granules)} granules, {granules[0].day} to {granules[-1].day}; '
        f'{len(missing)} periods absent upstream, as declared'
    )

    # the version names every store, so it is checked on the first granule
    # before any repository is created under a name that may be wrong
    time = time_source(source_name)
    # declared rows are checked against the listing here, before any read
    rule = row_rule(settings, granules)
    for declared in rule.declared.values():
        LOG.info(
            f'granule {declared.granule}: rows {declared.start}-{declared.stop - 1} '
            f'left out as declared: {declared.reason}'
        )
    check_versions([reader.read_granule(granules[0], [time], time, rule)], settings)
    os.makedirs(settings['directories']['zarr'], exist_ok=True)
    return granules, revision


def run_pass(settings, granules, revision, stores, num_workers):
    """One pass over the granules, writing a set of stores.

    Args:
        settings (dict): The loaded configuration.
        granules (list): From ``prepare``.
        revision (str): From ``prepare``, stamped on every commit.
        stores (list): The stores this pass writes.
        num_workers (int): Read processes; 1 reads in this process.

    Returns:
        dict: Store -> granules written by this pass.
    """
    source_name = source_product(settings)
    reader = load_reader(settings)
    _, per_commit = configure_runtime(settings)
    chunks = resolve_chunks(settings)
    codecs = resolve_compression(settings)
    time = time_source(source_name)
    rule = row_rule(settings, granules)
    repositories, states = {}, {}
    for store in stores:
        path = store_path(settings, store)
        repositories[store] = open_repository(path)
        states[store] = committed_state(repositories[store], granules, store)
        LOG.info(
            f'{store}: {states[store]["n_granules"]} of {len(granules)} granules '
            f'already committed -> {path}'
        )

    start = min(state['n_granules'] for state in states.values())
    label = ', '.join(stores) if len(stores) == 1 else f'{len(stores)} stores'
    if start >= len(granules):
        LOG.info(f'{label}: every store is already complete, nothing to write')
        return {store: 0 for store in stores}

    # the seam with what is already written is checked against the last time
    # committed by a store that stopped exactly at the restart point
    behind = [store for store in stores if states[store]['n_granules'] == start]
    previous_end = states[behind[0]]['last_time']
    # files not in time order are checked for repeats instead, on the pass
    # that writes the geolocation store, from the stored granule before it
    repeats = time_order(settings) == 'source' and GEOLOCATION in stores
    location = tuple(coordinates(source_name)[name].original for name in ('lat', 'lon'))
    previous_keys = stored_seam_keys(repositories[GEOLOCATION], start) if repeats else None

    batches = [
        (begin, min(begin + per_commit, len(granules)))
        for begin in range(start, len(granules), per_commit)
    ]
    LOG.info(f'{label}: {len(batches)} batches from granule {start}')

    # every source of every store not yet complete. A store ahead of the
    # restart point needs nothing from the first batches but everything after,
    # so the list is fixed for the whole pass rather than per batch
    incomplete = [store for store in stores if states[store]['n_granules'] < len(granules)]
    sources = sorted(
        {time} | (set(location) if repeats else set()) | {
            source for store in incomplete
            for source in store_sources(source_name, store).values()
        }
    )
    written = {store: 0 for store in stores}
    masked = {store: {} for store in stores}
    versions = None
    source_reader = Reader(reader, sources, time, rule, num_workers)
    try:
        pending = source_reader.submit(granules[batches[0][0]:batches[0][1]])
        for position, (begin, end) in enumerate(batches):
            needed = [store for store in stores if states[store]['n_granules'] < end]
            datas = source_reader.collect(pending)
            # the next batch is read while this one is written
            if position + 1 < len(batches):
                nxt = batches[position + 1]
                pending = source_reader.submit(granules[nxt[0]:nxt[1]])

            check_versions(datas, settings)
            if time_order(settings) == 'sorted':
                previous_end = check_time(datas, time, previous_end)
            elif repeats:
                previous_keys = check_repeats(datas, time, location, previous_keys)
            versions = versions or {'processor': datas[0].version}

            for store in needed:
                state = states[store]
                subset = datas[max(0, state['n_granules'] - begin):]
                observations, index, counts, fills = assemble(
                    store, subset, state['n_obs'], settings
                )
                encoding = None
                if state['n_granules'] == 0:
                    # the first commit creates the arrays, so it carries the
                    # encoding and the store's global attributes
                    observations.attrs = global_attrs(settings, store, versions)
                    encoding = build_encoding(
                        observations, index, chunks, fills, source_name, codecs
                    )
                message = COMMIT_MESSAGE.format(
                    first=subset[0].granule.id, last=subset[-1].granule.id,
                    count=len(subset), revision=revision,
                )
                snapshot = write_append(
                    repositories[store], observations, index, encoding, message
                )
                state['n_granules'] = end
                state['n_obs'] += observations.sizes['obs']
                written[store] += len(subset)
                for name, count in counts.items():
                    masked[store][name] = masked[store].get(name, 0) + count
                LOG.info(f'{store}: committed {message} as {snapshot}')
            LOG.info(
                f'{label}: batch {position + 1}/{len(batches)}: granules '
                f'{begin}-{end - 1} ({sum(data.n_obs for data in datas)} obs)'
            )
    finally:
        source_reader.close()

    for store in stores:
        LOG.info(
            f'{store}: wrote {written[store]} granules this run; masked '
            f'{masked[store] or "nothing"}'
        )
    return written


def own_pass(settings, granules, revision, store):
    """One store's pass, in a process of its own; see the module docstring.

    A top-level function of picklable arguments, so it runs in a spawned
    process. It logs to the run's log, as the main process does.

    Args:
        settings (dict): The loaded configuration.
        granules (list): From ``prepare``.
        revision (str): From ``prepare``.
        store (str): The store.

    Returns:
        dict: Store -> granules written.
    """
    setup_logging(log_path(settings))
    return run_pass(settings, granules, revision, [store], num_workers=1)


def build(settings):
    """Build every store of the config: the shared pass, and one process per
    store in ``own_process_stores``, all at once.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        dict: Store -> granules written by this run.

    Raises:
        Exception: The first failure of any pass, once every pass has ended.
    """
    granules, revision = prepare(settings)
    num_workers, _ = configure_runtime(settings)
    own = own_process_stores(settings)
    shared = [store for store in run_stores(settings) if store not in own]
    if own:
        LOG.info(f'{len(own)} stores in processes of their own: {own}')
    written, errors = {}, []
    pool = (
        concurrent.futures.ProcessPoolExecutor(
            max_workers=len(own), mp_context=multiprocessing.get_context('spawn')
        ) if own else None
    )
    try:
        futures = [pool.submit(own_pass, settings, granules, revision, store) for store in own]
        try:
            written |= run_pass(settings, granules, revision, shared, num_workers)
        except Exception as error:
            errors.append(error)
        for store, future in zip(own, futures):
            try:
                written |= future.result()
            except Exception as error:
                LOG.error(f'{store}: its pass failed: {error!r}')
                errors.append(error)
    finally:
        if pool is not None:
            pool.shutdown()
    if errors:
        raise errors[0]
    return written


def main(settings):

    os.makedirs(settings['directories']['logs'], exist_ok=True)
    setup_logging(log_path(settings))
    LOG.info(
        f'building WISO-SAT {settings["product"]} {settings["version"]} stores '
        f'from {settings["directories"]["raw"]}'
    )
    build(settings)
    log_peak_memory(LOG)
    LOG.info('done :-)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='build the icechunk zarr stores of one wiso-sat level 2 product.'
    )
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to YAML configuration file.',
    )
    args = parser.parse_args()
    settings = load_config(args.config)
    main(settings)
