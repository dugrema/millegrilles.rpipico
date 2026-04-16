import datetime
import time

import python_test1.time_scheduler as ts


def _patch_time(monkeypatch, epoch_now):
    """
    Patch time.time to return a fixed epoch.
    """
    monkeypatch.setattr(time, "time", lambda: epoch_now)


def test_next_epoch_time_with_positive_offset(monkeypatch):
    # Current UTC time: 2024-01-01 08:00:00
    now_epoch = int(datetime.datetime(2024, 1, 1, 8, 0, 0).timestamp())
    _patch_time(monkeypatch, now_epoch)

    # Target 10:00 local with timezone offset +1 hour (UTC+1)
    target_epoch = ts.next_epoch_time(10, 0, timezone_offset=3600)
    expected_epoch = int(datetime.datetime(2024, 1, 1, 9, 0, 0).timestamp())
    assert target_epoch == expected_epoch


def test_next_epoch_time_with_negative_offset(monkeypatch):
    # Current UTC time: 2024-01-01 08:0:00
    now_epoch = int(datetime.datetime(2024, 1, 1, 8, 0, 0).timestamp())
    _patch_time(monkeypatch, now_epoch)

    # Target 10:00 local with timezone offset -5 hours (UTC‑5)
    target_epoch = ts.next_epoch_time(10, 0, timezone_offset=-18000)
    expected_epoch = int(datetime.datetime(2024, 1, 1, 15, 0, 0).timestamp())
    assert target_epoch == expected_epoch


def test_next_epoch_time_day_of_week_same_day_future_offset_positive(monkeypatch):
    # Current UTC time: 2024-01-01 08:00:00
    now_epoch = int(datetime.datetime(2024, 1, 1, 8, 0, 0).timestamp())
    _patch_time(monkeypatch, now_epoch)

    # Target 10:00 local on Monday with timezone offset +2 hours (UTC+2)
    target_epoch = ts.next_epoch_time(10, 0, day_of_week=0, timezone_offset=7200)
    expected_epoch = int(datetime.datetime(2024, 1, 8, 8, 0, 0).timestamp())
    assert target_epoch == expected_epoch


def test_next_epoch_time_day_of_week_future_day_offset_negative(monkeypatch):
    # Current UTC time: 2024-01-05 08:00:00 (Friday)
    now_epoch = int(datetime.datetime(2024, 1, 5, 8, 0, 0).timestamp())
    _patch_time(monkeypatch, now_epoch)

    # Target 09:00 local on Monday with timezone offset -5 hours (UTC‑5)
    target_epoch = ts.next_epoch_time(9, 0, day_of_week=0, timezone_offset=-18000)
    expected_epoch = int(datetime.datetime(2024, 1, 8, 14, 0, 0).timestamp())
    assert target_epoch == expected_epoch


def test_next_epoch_time_day_of_week_same_day_offset_negative_current_over(monkeypatch):
    # Current UTC time: 2024-01-06 03:00:58 (Saturday)
    now_epoch = int(datetime.datetime(2024, 1, 6, 3, 0, 58).timestamp())
    _patch_time(monkeypatch, now_epoch)

    # Target 23:01:00 local on same day (EST still Friday) with timezone offset -5 hours (UTC‑5)
    target_epoch = ts.next_epoch_time(22, 1, day_of_week=4, timezone_offset=-18000)
    expected_epoch = int(datetime.datetime(2024, 1, 6, 3, 1, 0).timestamp())
    assert target_epoch == expected_epoch


def test_next_epoch_time_day_of_week_future_day_offset_negative_current_over(
    monkeypatch,
):
    # Current UTC time: 2024-01-06 03:01:00 (Saturday)
    now_epoch = int(datetime.datetime(2024, 1, 6, 3, 1, 0).timestamp())
    _patch_time(monkeypatch, now_epoch)

    # Target 23:01:00 local on same day (EST still Friday) with timezone offset -5 hours (UTC‑5)
    target_epoch = ts.next_epoch_time(22, 1, day_of_week=4, timezone_offset=-18000)
    expected_epoch = int(datetime.datetime(2024, 1, 13, 3, 1, 0).timestamp())
    assert target_epoch == expected_epoch
