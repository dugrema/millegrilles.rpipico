"""
MicroPython‑compatible time utilities with timezone offset support.

This module uses only the standard ``time`` module and
simple integer arithmetic.  All public functions return integer
epoch timestamps and can be used in a MicroPython environment.
"""

import time

__all__ = [
    "get_current_time",
    "now",
    "format_time",
    "next_epoch_time",
    "previous_epoch_time",
]


def get_current_time() -> int:
    """Return the current time as an integer number of seconds since the epoch."""
    return int(time.time())


def now() -> int:
    """Return the current local time as an integer epoch seconds."""
    return int(time.time())


def format_time(t: float | int | time.struct_time) -> int:
    """
    Convert a time value to an epoch timestamp.

    ``t`` can be a ``time.struct_time`` tuple or an epoch float/int.
    The returned value is the integer epoch time.
    """
    if isinstance(t, (float, int)):
        return int(t)
    return int(time.mktime(t))


# --------------------------------------------------------------------------- #
# Helper functions – all work with UTC epoch and simple integer math
# --------------------------------------------------------------------------- #
def _is_leap(year: int) -> bool:
    """Return True if ``year`` is a leap year."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _epoch_from_utc(
    year: int, month: int, day: int, hour: int, minute: int, second: int = 0
) -> int:
    """
    Compute the Unix epoch (seconds since 1970‑01‑01 00:00:00 UTC)
    for a given UTC date and time.  No external libraries are used.
    """
    # Days from 1970‑01‑01 to the start of ``year``.
    years_since_1970 = year - 1970
    # Leap days between 1970 and year‑1 inclusive.
    leaps = (
        (year - 1) // 4
        - 1969 // 4
        - ((year - 1) // 100 - 1969 // 100)
        + ((year - 1) // 400 - 1969 // 400)
    )
    days = years_since_1970 * 365 + leaps

    # Days in months before ``month``.
    month_days = [
        31,
        29 if _is_leap(year) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]
    days += sum(month_days[: month - 1]) + (day - 1)

    return days * 86400 + hour * 3600 + minute * 60 + second


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def next_epoch_time(
    hour: int,
    minute: int,
    day_of_week: int = None,
    timezone_offset: int = 0,
) -> int:
    """
    Return the epoch timestamp for the next occurrence of the specified hour
    and minute, optionally restricted to a specific day of the week.

    Parameters
    ----------
    hour : int
        Desired hour (0–23).
    minute : int
        Desired minute (0–59).
    day_of_week : Optional[int]
        Desired day of week where Monday is 0 and Sunday is 6.
        If None, the next occurrence of the hour/minute is returned.
    timezone_offset : int, optional
        Time zone offset in seconds relative to UTC.
        Positive values mean local time is ahead of UTC
        (e.g., +2 h = 7200 s).  Defaults to 0 (UTC).

    Returns
    -------
    int
        The UTC epoch timestamp of the next occurrence of the
        requested local time.
    """
    # Current UTC epoch.
    utc_now_epoch = int(time.time())

    # Epoch of the current *local* time (offset from UTC).
    local_now_epoch = utc_now_epoch + timezone_offset

    # Break the local epoch into date/time components.
    # ``time.gmtime`` is used because ``local_now_epoch`` already
    # contains the time‑zone offset.
    # local_now = time.gmtime(local_now_epoch)
    tm_year, tm_mon, tm_mday, hour_now, minute_now, second_now, tm_wday, yd_now = time.gmtime(local_now_epoch)

    # Compute the epoch that corresponds to the target local date/time
    # assuming the given date/time is expressed in UTC.  That epoch
    # equals the *local* epoch for the target.
    target_local_epoch = _epoch_from_utc(
        tm_year,
        tm_mon,
        tm_mday,
        hour,
        minute,
    )

    if day_of_week is None or not isinstance(day_of_week, int):
        # If the target time has already passed today, move to tomorrow.
        if target_local_epoch <= local_now_epoch:
            target_local_epoch += 86400  # add one day in seconds
    else:
        # Calculate days until the desired weekday.
        days_ahead = (day_of_week - tm_wday + 7) % 7
        if days_ahead == 0 and target_local_epoch <= local_now_epoch:
            days_ahead = 7
        target_local_epoch += days_ahead * 86400

    # Convert the local target epoch back to UTC epoch seconds.
    return target_local_epoch - timezone_offset


def previous_epoch_time(
    hour: int,
    minute: int,
    day_of_week: int = None,
    timezone_offset: int = 0,
) -> int:
    """
    Return the epoch timestamp for the previous occurrence of the specified hour
    and minute, optionally restricted to a specific day of the week.
    """
    # Current UTC epoch.
    utc_now_epoch = int(time.time())
    # Epoch of the current *local* time (offset from UTC).
    local_now_epoch = utc_now_epoch + timezone_offset
    # Break the local epoch into date/time components.
    # local_now = time.gmtime(local_now_epoch)
    tm_year, tm_mon, tm_mday, hour_now, minute_now, second_now, tm_wday, yd_now = time.gmtime(local_now_epoch)
    # Compute the epoch that corresponds to the target local date/time
    target_local_epoch = _epoch_from_utc(
        tm_year,
        tm_mon,
        tm_mday,
        hour,
        minute,
    )
    if day_of_week is None:
        # If the target time has already been today, move to yesterday.
        if target_local_epoch >= local_now_epoch:
            target_local_epoch -= 86400  # subtract one day in seconds
    else:
        # Calculate days until the desired weekday in the past.
        days_behind = (tm_wday - day_of_week + 7) % 7
        # If the target day is today and the time is still in the future
        # relative to the current local time, we need to skip back one week.
        if days_behind == 0 and target_local_epoch >= local_now_epoch:
            days_behind = 7
        target_local_epoch -= days_behind * 86400

    # Convert the local target epoch back to UTC epoch seconds.
    return target_local_epoch - timezone_offset
