"""Time periods of a gridded store: days, n-day blocks, months, n-month blocks.

Every period is a whole number of UTC days, and every observation belongs to
exactly one day, so a period's sums are its days' sums added up
(gridding-method.md, Section 8).

**Anchoring** (user decision 2026-11-10): blocks are counted from the time
epoch, 1900-01-01, so every n-day period is exactly n days and its
boundaries are the same for every sensor and year. n-month periods start in
January 1900 and n must divide 12, so every block starts in January of each
year (3month: JFM, AMJ, JAS, OND).

Days are int64 day numbers since 1900-01-01 throughout, the unit the stores'
``time`` is written in (style guide: the coarsest unit that is exact).
"""
import re

import numpy as np

EPOCH = np.datetime64('1900-01-01', 'D')
FREQUENCY_RE = re.compile(r'^(?P<n>[1-9]\d*)?(?P<unit>day|month)$')


def parse(frequency):
    """``'3day'`` -> ``(3, 'day')``; ``'month'`` -> ``(1, 'month')``.

    Raises:
        ValueError: On any other token, or an n-month block that does not divide 12.
    """
    match = FREQUENCY_RE.match(frequency)
    if not match:
        raise ValueError(f'frequency must be day, <n>day, month or <n>month, got {frequency!r}')
    n, unit = int(match['n'] or 1), match['unit']
    if unit == 'month' and 12 % n:
        raise ValueError(f'{frequency}: n months must divide 12, so every block starts in January')
    return n, unit


def day_number(date):
    """Days since 1900-01-01 of a date (str, datetime64, Timestamp)."""
    return int((np.datetime64(date, 'D') - EPOCH).astype('int64'))


def day_date(number):
    """The datetime64[D] of a day number."""
    return EPOCH + np.timedelta64(int(number), 'D')


def _month_index(day):
    date = day_date(day).astype('datetime64[M]')
    return int((date - EPOCH.astype('datetime64[M]')).astype('int64'))


def _month_start(index):
    return day_number(EPOCH.astype('datetime64[M]') + np.timedelta64(int(index), 'M'))


def period_of(day, frequency):
    """The period holding a day, as its ``(start, end)`` day numbers, end exclusive."""
    n, unit = parse(frequency)
    if unit == 'day':
        start = (day // n) * n
        return start, start + n
    block = _month_index(day) // n
    return _month_start(block * n), _month_start((block + 1) * n)


def periods(first_day, last_day, frequency):
    """Every period from the one holding ``first_day`` to the one holding ``last_day``.

    Args:
        first_day, last_day (int): Day numbers, inclusive.
        frequency (str): The token.

    Returns:
        numpy.ndarray: int64 ``(n_periods, 2)``: start and exclusive end day.
    """
    bounds = [period_of(first_day, frequency)]
    while bounds[-1][1] <= last_day:
        bounds.append(period_of(bounds[-1][1], frequency))
    return np.array(bounds, dtype='int64')


def coverage_resolution(frequency):
    """ISO 8601 duration of one period ('P1D', 'P3D', 'P1M')."""
    n, unit = parse(frequency)
    return f'P{n}{"D" if unit == "day" else "M"}'
