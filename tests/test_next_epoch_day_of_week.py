import datetime
import time

import python_test1.time_scheduler as ts


def _patch_time(monkeypatch, epoch_now):
    """Patch time.time and time.localtime to return a fixed epoch and its struct_time."""
    monkeypatch.setattr(time, "time", lambda: epoch_now)
    now_struct = time.localtime(epoch_now)
    monkeypatch.setattr(time, "localtime", lambda epoch=None: now_struct)


def test_next_epoch_time_day_of_week_same_day_future(monkeypatch):
    # Today is Monday, Jan 1, 2024 08:00:00
    epoch_now = int(datetime.datetime(2024, 1, 1, 8, 0, 0).timestamp())
    _patch_time(monkeypatch, epoch_now)

    # Target 10:00 on the same Monday
    target_epoch = ts.next_epoch_time(10, 0, day_of_week=0)
    expected = int(time.mktime(datetime.datetime(2024, 1, 1, 10, 0, 0).timetuple()))
    assert target_epoch == expected


def test_next_epoch_time_day_of_week_same_day_past(monkeypatch):
    # Today is Monday, Jan 1, 2024 12:00:00
    epoch_now = int(datetime.datetime(2024, 1, 1, 12, 0, 0).timestamp())
    _patch_time(monkeypatch, epoch_now)

    # Target 10:00 on the same Monday (past), should roll over to next week
    target_epoch = ts.next_epoch_time(10, 0, day_of_week=0)
    expected = int(time.mktime(datetime.datetime(2024, 1, 8, 10, 0, 0).timetuple()))
    assert target_epoch == expected


def test_next_epoch_time_day_of_week_future_day(monkeypatch):
    # Today is Friday, Jan 5, 2024 08:00:00
    epoch_now = int(datetime.datetime(2024, 1, 5, 8, 0, 0).timestamp())
    _patch_time(monkeypatch, epoch_now)

    # Target 09:00 on Monday (day_of_week=0) in the same week
    target_epoch = ts.next_epoch_time(9, 0, day_of_week=0)
    expected = int(time.mktime(datetime.datetime(2024, 1, 8, 9, 0, 0).timetuple()))
    assert target_epoch == expected


def test_next_epoch_time_day_of_week_previous_day(monkeypatch):
    # Today is Thursday, Jan 4, 2024 08:00:00
    epoch_now = int(datetime.datetime(2024, 1, 4, 8, 0, 0).timestamp())
    _patch_time(monkeypatch, epoch_now)

    # Target 09:00 on Sunday (day_of_week=6) later in the same week
    target_epoch = ts.next_epoch_time(9, 0, day_of_week=6)
    expected = int(time.mktime(datetime.datetime(2024, 1, 7, 9, 0, 0).timetuple()))
    assert target_epoch == expected


def test_next_epoch_time_day_of_week_today_edge(monkeypatch):
    # Today is Monday, Jan 1, 2024 10:00:00 (exact target time)
    epoch_now = int(datetime.datetime(2024, 1, 1, 10, 0, 0).timestamp())
    _patch_time(monkeypatch, epoch_now)

    # Target 10:00 on the same Monday should roll over to next week
    target_epoch = ts.next_epoch_time(10, 0, day_of_week=0)
    expected = int(time.mktime(datetime.datetime(2024, 1, 8, 10, 0, 0).timetuple()))
    assert target_epoch == expected
