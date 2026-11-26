"""Unified schema. Every provider normalizes raw responses to these shapes."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class Activity(BaseModel):
    source: str
    id: str
    day: date
    sport: str | None = None
    name: str | None = None
    start: datetime | None = None
    km: float | None = None
    minutes: float | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    elevation_m: float | None = None
    training_load: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class SleepNight(BaseModel):
    source: str
    day: date
    hours: float | None = None
    deep_min: int | None = None
    rem_min: int | None = None
    light_min: int | None = None
    awake_min: int | None = None
    score: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class DailyWellness(BaseModel):
    source: str
    day: date
    steps: int | None = None
    resting_hr: int | None = None
    stress_avg: int | None = None
    body_battery_high: int | None = None
    body_battery_low: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class MetricPoint(BaseModel):
    source: str
    day: date
    metric: str
    value: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
