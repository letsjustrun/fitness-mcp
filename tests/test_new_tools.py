"""Smoke tests for the tools added in the analysis pack: body battery,
stress, weight, hydration, fitness age, HRV-night detail, activity workouts,
and the recovery synthesis.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from fitness_mcp.tools import recovery, singles, wellness_extras


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


@pytest.mark.asyncio
async def test_body_battery(tmp_db, fake_provider):
    out = await wellness_extras.body_battery(_days_ago(3), _days_ago(1), force_refresh=False)
    assert len(out["body_battery"]) == 3
    for r in out["body_battery"]:
        assert r["min_value"] == 20
        assert r["max_value"] == 85


@pytest.mark.asyncio
async def test_stress(tmp_db, fake_provider):
    out = await wellness_extras.stress(_days_ago(3), _days_ago(1), force_refresh=False)
    assert len(out["stress"]) == 3
    assert all(r["avg_level"] == 25 for r in out["stress"])


@pytest.mark.asyncio
async def test_weight(tmp_db, fake_provider):
    out = await wellness_extras.weight(_days_ago(3), _days_ago(1), force_refresh=False)
    assert len(out["weight"]) == 3
    assert all(abs(r["weight_kg"] - 72.5) < 1e-9 for r in out["weight"])


@pytest.mark.asyncio
async def test_hydration(tmp_db, fake_provider):
    out = await wellness_extras.hydration(_days_ago(3), _days_ago(1), force_refresh=False)
    assert len(out["hydration"]) == 3
    assert all(r["consumed_ml"] == 2200 for r in out["hydration"])


@pytest.mark.asyncio
async def test_fitness_age(tmp_db, fake_provider):
    out = await singles.fitness_age(_days_ago(1))
    assert out["fitness_age"] == 35.0


@pytest.mark.asyncio
async def test_hrv_night_detail_passthrough(tmp_db, fake_provider):
    out = await singles.hrv_night_detail(_days_ago(1))
    assert out["detail"]["lastNightAvg"] == 95


@pytest.mark.asyncio
async def test_activity_workouts_passthrough(tmp_db, fake_provider):
    out = await singles.activity_workouts("abc-123")
    assert out["activity_id"] == "abc-123"
    assert "workouts" in out["workouts"]


@pytest.mark.asyncio
async def test_recovery_signal_shape(tmp_db, fake_provider):
    """We can't easily assert the composite score (depends on cache warm-up)
    but we can pin its shape and advisory output."""
    out = await recovery.recovery_signal(_days_ago(1))
    assert "composite_score" in out
    assert 0 <= out["composite_score"] <= 100
    for key in ("sleep", "hrv", "body_battery", "resting_hr", "training_load"):
        assert key in out["components"]
    assert isinstance(out["advice_hint"], str)
