"""Unit tests for the pure staleness rules in store.sync."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fitness_mcp.store.sync import (
    WINDOW_RECENT,
    WINDOW_TODAY,
    _contiguous_ranges,
    is_stale,
    staleness_window,
)


def test_window_today_is_30_min():
    today = date(2026, 11, 25)
    assert staleness_window(today, today) == WINDOW_TODAY


def test_window_recent_is_6_h():
    today = date(2026, 11, 25)
    for days_ago in (1, 2, 3):
        d = today - timedelta(days=days_ago)
        assert staleness_window(d, today) == WINDOW_RECENT


def test_window_old_is_none():
    today = date(2026, 11, 25)
    for days_ago in (4, 7, 30, 365):
        d = today - timedelta(days=days_ago)
        assert staleness_window(d, today) is None


def test_is_stale_without_entry_always_stale():
    today = date(2026, 11, 25)
    now = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)
    assert is_stale(None, today, today, now) is True
    assert is_stale(None, today - timedelta(days=10), today, now) is True


def test_is_stale_old_day_after_one_fetch_is_fresh_forever():
    today = date(2026, 11, 25)
    old = today - timedelta(days=30)
    fetched_long_ago = datetime(2020, 1, 1, tzinfo=UTC)
    now = datetime(2026, 11, 25, tzinfo=UTC)
    assert is_stale(fetched_long_ago, old, today, now) is False


def test_is_stale_today_within_window():
    today = date(2026, 11, 25)
    now = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)
    fresh = now - timedelta(minutes=10)
    stale = now - timedelta(minutes=45)
    assert is_stale(fresh, today, today, now) is False
    assert is_stale(stale, today, today, now) is True


def test_is_stale_yesterday_within_six_hours():
    today = date(2026, 11, 25)
    now = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)
    yesterday = today - timedelta(days=1)
    fresh = now - timedelta(hours=1)
    stale = now - timedelta(hours=7)
    assert is_stale(fresh, yesterday, today, now) is False
    assert is_stale(stale, yesterday, today, now) is True


def test_contiguous_ranges_single():
    d = date(2026, 11, 25)
    assert _contiguous_ranges([d]) == [(d, d)]


def test_contiguous_ranges_splits_on_gap():
    days = [
        date(2026, 11, 20),
        date(2026, 11, 21),
        date(2026, 11, 25),  # gap
        date(2026, 11, 26),
        date(2026, 11, 27),
    ]
    assert _contiguous_ranges(days) == [
        (date(2026, 11, 20), date(2026, 11, 21)),
        (date(2026, 11, 25), date(2026, 11, 27)),
    ]


def test_contiguous_ranges_empty():
    assert _contiguous_ranges([]) == []
