import datetime
import time

import python_test1.time_scheduler as ts


def _patch_time(monkeypatch, epoch_now):
    """Patch time.time to return a fixed epoch."""
    monkeypatch.setattr(time, "time", lambda: epoch_now)


def test_previous_epoch_time_with_positive_offset(monkeypatch):
    # Current UTC time: 2024-01-02 08:00:00
    now_epoch = int(datetime.datetime(2024, 1, 2, 8, 0, 0).timestamp())
    _patch_time(monkeypatch, now_epoch)

    # Target 10:00 local with timezone offset +1 hour (UTC+1)
    prev_epoch = ts.previous_epoch_time(10, 0, timezone_offset=3600)
    # Previous 10:00 local is yesterday at 10:00 local => UTC 09:00 on Jan 1
    expected = int(datetime.datetime(2024, 1, 1, 9, 0, 0).timestamp())
    assert prev_epoch == expected


def test_previous_epoch_time_with_negative_offset(monkeypatch):
    # Current UTC time: 2024-01-02 08:00:00
    now_epoch = int(datetime.datetime(2024, 1, 2, 8, 0, 0).timestamp())
    _patch_time(monkeypatch, now_epoch)

    # Target 10:00 local with timezone offset -5 hours (UTC-5)
    prev_epoch = ts.previous_epoch_time(10, 0, timezone_offset=-18000)
    # Previous 10:00 local is yesterday at 10:00 local => UTC 15:00 on Jan 1
    expected = int(datetime.datetime(2024, 1, 1, 15, 0, 0).timestamp())
    assert prev_epoch == expected


def test_previous_epoch_time_same_day_passed_offset_positive(monkeypatch):
    # Current UTC time: 2024-01-02 10:00:00
    now_epoch = int(datetime.datetime(2024, 1, 2, 10, 0, 0).timestamp())
    _patch_time(monkeypatch, now_epoch)

    # Local time is 11:00 (UTC+1). Target 10:00 local has already passed.
    prev_epoch = ts.previous_epoch_time(10, 0, timezone_offset=3600)
    # Previous should be today 10:00 local => UTC 09:00 on Jan 2
    expected = int(datetime.datetime(2024, 1, 2, 9, 0, 0).timestamp())
    assert prev_epoch == expected


def test_previous_epoch_time_day_of_week_same_day_passed(monkeypatch):
    # Current UTC time: 2024-01-02 10:00:00 (Monday)
    now_epoch = int(datetime.datetime(2024, 1, 1, 10, 0, 0).timestamp())
    _patch_time(monkeypatch, now_epoch)

    # Target Monday (day_of_week=0) 10:00 local has already passed.
    prev_epoch = ts.previous_epoch_time(10, 0, day_of_week=0)
    # Previous Monday should be last week Monday 10:00 local => UTC 10:00 on 2023-12-26
    expected = int(datetime.datetime(2023, 12, 25, 10, 0, 0).timestamp())
    assert prev_epoch == expected


def test_previous_epoch_time_day_of_week_future(monkeypatch):
    # Current UTC time: 2024-01-05 08:00:00 (Friday)
    now_epoch = int(datetime.datetime(2024, 1, 5, 8, 0, 0).timestamp())
    _patch_time(monkeypatch, now_epoch)

    # Target Monday (day_of_week=0) 09:00 local. Monday hasn't occurred yet this week.
    prev_epoch = ts.previous_epoch_time(9, 0, day_of_week=0)
    # Previous Monday is last week Monday 09:00 local => UTC 09:00 on 2024-01-01
    expected = int(datetime.datetime(2024, 1, 1, 9, 0, 0).timestamp())
    assert prev_epoch == expected
