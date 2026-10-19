import logging
import os

def setup_logging(log_file, fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s'):
    """
    Configure logging to write to the specified file under ./logs/.
    Creates the log directory if it does not exist.
    """
    log_path = log_file
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_path, mode='a'),
            logging.StreamHandler(),
        ],
        force=True,
    )

def log_peak_memory(logger):
    """Log the peak resident memory of this process and of its workers.

    qhist reports what a job requested, not what it used (MSWEP TESTING.md
    finding 13), so the bench reads peak memory from here instead. Children
    are the read pool's processes; the figure is the largest single child,
    not their sum.

    Args:
        logger (logging.Logger): Where to log.
    """
    import resource

    main = resource.getrusage(resource.RUSAGE_SELF)
    pool = resource.getrusage(resource.RUSAGE_CHILDREN)
    # ru_maxrss is KiB on Linux
    logger.info(
        f'peak memory: {main.ru_maxrss / 1024**2:.2f} GiB main process, '
        f'{pool.ru_maxrss / 1024**2:.2f} GiB largest worker'
    )
    # what the job is billed for, split by where it went: PBS reports only
    # the total, and the TROPOMI 2-D bench (2026-10-19) used ~4x the CPU its
    # stages account for. sys is kernel time: page faults, I/O, pipes
    logger.info(
        f'cpu time: main {main.ru_utime / 3600:.2f} h user + {main.ru_stime / 3600:.2f} h sys; '
        f'workers {pool.ru_utime / 3600:.2f} h user + {pool.ru_stime / 3600:.2f} h sys'
    )
