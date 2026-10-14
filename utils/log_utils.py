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

    # ru_maxrss is KiB on Linux
    own = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2
    children = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024**2
    logger.info(f'peak memory: {own:.2f} GiB main process, {children:.2f} GiB largest worker')
