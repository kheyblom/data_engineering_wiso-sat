"""Build the icechunk zarr stores of one WISO-SAT Level 2 product from raw files.

One config drives one product. A run builds the product's ``geolocation``
store plus one store per variable the config lists, in a single pass over the
granules: each source file is opened once and its variables go to every store
that still needs them (decided 2026-10-14, to avoid reopening every TROPOMI
orbit once per store). Every store is still written from the raw files; none
is derived from another.

The pass, per batch of ``granules_per_commit`` granules:

1. read the granules in a pool of ``num_workers`` processes (HDF5 is not
   thread safe), prefetching the next batch while this one is written;
2. check that every granule declares the configured processor version and
   that time never decreases, within or across granules;
3. append each store's slice, data and granule index together, as one commit
   per store.

Each store resumes on its own from its granule index, so a run killed between
two stores' commits picks up exactly where each left off. Before anything is
read, the listing is checked: granules unique, and the days without one exactly
the config's ``expected_missing_days``.
"""

import argparse
import concurrent.futures
import logging
import multiprocessing
import os

from utils.granules import check_coverage, check_order, check_time
from utils.log_utils import setup_logging
from utils.nomenclature import coordinates, variables
from utils.path_utils import (
    load_config,
    load_reader,
    log_path,
    run_stores,
    store_path,
)
from utils.zarr_utils import (
    COMMIT_MESSAGE,
    assemble,
    build_encoding,
    check_fill_config,
    committed_state,
    configure_runtime,
    global_attrs,
    log_key,
    open_repository,
    resolve_chunks,
    store_sources,
    time_source,
    write_append,
)

LOG = logging.getLogger(__name__)


def check_versions(datas, settings):
    """Fail unless every granule declares the configured processor version.

    The version names every store, so a granule from another processor version
    would be filed under a name that misdescribes it.

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


class Reader:
    """Reads batches of granules, in a process pool or in this process.

    Attributes:
        reader (module): The product's reader.
        sources (list): Source paths every read returns.
        time (str): The time coordinate's source path.
    """

    def __init__(self, reader, sources, time, num_workers):
        self.reader = reader
        self.sources = sources
        self.time = time
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
            return [self.reader.read_granule(g, self.sources, self.time) for g in granules]
        return [
            self.pool.submit(self.reader.read_granule, g, self.sources, self.time)
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


def build(settings):
    """Run the pass.

    Args:
        settings (dict): The loaded configuration.

    Returns:
        dict: Store -> granules written by this run.
    """
    product = settings['product']
    reader = load_reader(settings)
    num_workers, per_commit = configure_runtime(settings)
    chunks = resolve_chunks(settings)
    stores = run_stores(settings)
    log_key(product)

    known = [entry.original for entry in variables(product).values()]
    known += [entry.original for entry in coordinates(product).values()]
    check_fill_config(settings, known)

    raw = settings['directories']['raw']
    LOG.info(f'listing granules under {raw}')
    granules = reader.list_granules(raw)
    check_order(granules)
    missing = check_coverage(granules, settings)
    LOG.info(
        f'{len(granules)} granules, {granules[0].day} to {granules[-1].day}; '
        f'{len(missing)} days absent upstream, as declared'
    )

    # the version names every store, so it is checked on the first granule
    # before any repository is created under a name that may be wrong
    time = time_source(product)
    check_versions([reader.read_granule(granules[0], [time], time)], settings)

    os.makedirs(settings['directories']['zarr'], exist_ok=True)
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
    if start >= len(granules):
        LOG.info('every store is already complete, nothing to write')
        return {store: 0 for store in stores}

    # the seam with what is already written is checked against the last time
    # committed by a store that stopped exactly at the restart point
    behind = [store for store in stores if states[store]['n_granules'] == start]
    previous_end = states[behind[0]]['last_time']

    batches = [
        (begin, min(begin + per_commit, len(granules)))
        for begin in range(start, len(granules), per_commit)
    ]
    LOG.info(f'{len(batches)} batches from granule {start}')

    # every source of every store not yet complete. A store ahead of the
    # restart point needs nothing from the first batches but everything after,
    # so the list is fixed for the whole pass rather than per batch
    incomplete = [store for store in stores if states[store]['n_granules'] < len(granules)]
    sources = sorted(
        {time} | {
            source for store in incomplete
            for source in store_sources(product, store).values()
        }
    )
    written = {store: 0 for store in stores}
    masked = {store: {} for store in stores}
    versions = None
    source_reader = Reader(reader, sources, time, num_workers)
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
            previous_end = check_time(datas, time, previous_end)
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
                    encoding = build_encoding(observations, index, chunks, fills, product)
                message = COMMIT_MESSAGE.format(
                    first=subset[0].granule.id, last=subset[-1].granule.id, count=len(subset)
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
                f'batch {position + 1}/{len(batches)}: granules {begin}-{end - 1} '
                f'({sum(data.n_obs for data in datas)} obs)'
            )
    finally:
        source_reader.close()

    for store in stores:
        LOG.info(
            f'{store}: wrote {written[store]} granules this run; masked '
            f'{masked[store] or "nothing"}'
        )
    return written


def main(settings):

    os.makedirs(settings['directories']['logs'], exist_ok=True)
    setup_logging(log_path(settings))
    LOG.info(
        f'building WISO-SAT {settings["product"]} {settings["version"]} stores '
        f'from {settings["directories"]["raw"]}'
    )
    build(settings)
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
