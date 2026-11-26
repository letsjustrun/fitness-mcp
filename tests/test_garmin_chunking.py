"""Garmin's range endpoints cap the window at 30 days. The provider has to
chunk longer ranges client-side and concatenate the results. This test pins
that behaviour without touching the network.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from fitness_mcp.providers.garmin import GarminProvider


class _FakeClient:
    """Minimal stand-in for GarminPersonalApiClient — only `get_daily_sleep_summaries`
    is exercised; it records every call so we can assert on chunking.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[date, date]] = []

    def get_daily_sleep_summaries(self, start_date: date, end_date: date):
        self.calls.append((start_date, end_date))
        out = []
        cur = start_date
        while cur <= end_date:
            out.append({"calendarDate": cur.isoformat(),
                        "sleepTimeSeconds": 7 * 3600})
            cur += timedelta(days=1)
        return out


@pytest.mark.asyncio
async def test_sleep_range_chunked_at_30_days(monkeypatch):
    p = GarminProvider(api_key="fake-key")
    fake = _FakeClient()

    # Pretend we've already authenticated — monkeypatch the lazy client.
    async def _get_client(force_refresh: bool = False):
        return fake
    monkeypatch.setattr(p, "_obtain_client", _get_client)

    # 75 days — should split into three chunks of 30/30/15.
    start = date(2026, 1, 1)
    end = date(2026, 3, 16)
    nights = await p.fetch_sleep(start, end)

    assert len(fake.calls) == 3, f"expected 3 chunks, got {len(fake.calls)}"
    # Each chunk is at most 30 days wide.
    for s, e in fake.calls:
        assert (e - s).days + 1 <= 30
    # No overlap, no gap: chunks cover exactly [start, end].
    fake.calls.sort()
    assert fake.calls[0][0] == start
    assert fake.calls[-1][1] == end
    for prev, nxt in zip(fake.calls, fake.calls[1:]):
        assert nxt[0] == prev[1] + timedelta(days=1)

    # Nights returned covers the full window (75 days).
    assert len(nights) == 75

    await p.close()


@pytest.mark.asyncio
async def test_sleep_range_under_30_days_still_one_call(monkeypatch):
    p = GarminProvider(api_key="fake-key")
    fake = _FakeClient()

    async def _get_client(force_refresh: bool = False):
        return fake
    monkeypatch.setattr(p, "_obtain_client", _get_client)

    start = date(2026, 1, 1)
    end = date(2026, 1, 15)
    await p.fetch_sleep(start, end)

    assert fake.calls == [(start, end)]

    await p.close()
