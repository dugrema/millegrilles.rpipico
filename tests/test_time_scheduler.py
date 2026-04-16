import datetime
import time

import python_test1.time_scheduler as ts


def _patch_time(monkeypatch, epoch_now):
    """Patch time.time and time.localtime to return a fixed epoch and its struct_time."""
    monkeypatch.setattr(time, "time", lambda: epoch_now)
    now_struct = time.localtime(epoch_now)
    monkeypatch.setattr(time, "localtime", lambda epoch=None: now_struct)


def test_next_epoch_time_future(monkeypatch):
    epoch_now = int(datetime.datetime(2024, 1, 1, 10, 0, 0).timestamp())
    _patch_time(monkeypatch, epoch_now)
    target_epoch = ts.next_epoch_time(10, 15)
    expected = int(time.mktime(datetime.datetime(2024, 1, 1, 10, 15, 0).timetuple()))
    assert isinstance(target_epoch, int)
    assert target_epoch == expected


def test_next_epoch_time_past(monkeypatch):
    epoch_now = int(datetime.datetime(2024, 1, 1, 10, 0, 0).timestamp())
    _patch_time(monkeypatch, epoch_now)
    target_epoch = ts.next_epoch_time(9, 30)
    expected = int(time.mktime(datetime.datetime(2024, 1, 2, 9, 30, 0).timetuple()))
    assert target_epoch == expected


def test_next_epoch_time_exact(monkeypatch):
    epoch_now = int(datetime.datetime(2024, 1, 1, 10, 0, 0).timestamp())
    _patch_time(monkeypatch, epoch_now)
    target_epoch = ts.next_epoch_time(10, 0)
    expected = int(time.mktime(datetime.datetime(2024, 1, 2, 10, 0, 0).timetuple()))
    assert target_epoch == expected


def test_next_epoch_time_midnight(monkeypatch):
    epoch_now = int(datetime.datetime(2024, 1, 1, 23, 59, 59).timestamp())
    _patch_time(monkeypatch, epoch_now)
    target_epoch = ts.next_epoch_time(0, 0)
    expected = int(time.mktime(datetime.datetime(2024, 1, 2, 0, 0, 0).timetuple()))
    assert target_epoch == expected


def test_next_epoch_time_returns_future(monkeypatch):
    epoch_now = int(datetime.datetime(2024, 1, 1, 12, 30, 15).timestamp())
    _patch_time(monkeypatch, epoch_now)
    target_epoch = ts.next_epoch_time(12, 31)
    assert target_epoch > epoch_now
