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

    # Running form (null when not measured — swim, bike, strength, etc.)
    avg_cadence: int | None = None       # steps / minute
    max_cadence: int | None = None       # steps / minute
    avg_ground_contact_ms: int | None = None
    avg_vertical_oscillation_cm: float | None = None
    avg_vertical_ratio: float | None = None
    avg_stride_length_cm: float | None = None

    # HR zones — seconds spent in each zone (0 when not measured).
    hr_z1_sec: int | None = None
    hr_z2_sec: int | None = None
    hr_z3_sec: int | None = None
    hr_z4_sec: int | None = None
    hr_z5_sec: int | None = None

    # Garmin training effect (both out of ~5). Label captures Garmin's
    # overall categorisation (RECOVERY / BASE / TEMPO / THRESHOLD / VO2MAX /
    # ANAEROBIC / RECOVERY).
    aerobic_te: float | None = None
    anaerobic_te: float | None = None
    training_effect_label: str | None = None

    # Best effort splits inside the workout, if the device logged them.
    fastest_1k_sec: float | None = None
    fastest_mile_sec: float | None = None

    # Power + totals.
    avg_power: int | None = None
    max_power: int | None = None
    lap_count: int | None = None

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


class BodyBatteryDay(BaseModel):
    source: str
    day: date
    min_value: int | None = None
    max_value: int | None = None
    charged: int | None = None     # points gained over the day
    drained: int | None = None     # points lost
    latest: int | None = None      # value at end of logging
    raw: dict[str, Any] = Field(default_factory=dict)


class StressDay(BaseModel):
    source: str
    day: date
    avg_level: int | None = None
    max_level: int | None = None
    rest_sec: int | None = None
    activity_sec: int | None = None
    low_sec: int | None = None
    medium_sec: int | None = None
    high_sec: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class WeightMeasurement(BaseModel):
    source: str
    day: date
    taken_at: datetime | None = None
    weight_kg: float | None = None
    bmi: float | None = None
    body_fat_pct: float | None = None
    muscle_mass_kg: float | None = None
    bone_mass_kg: float | None = None
    body_water_pct: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class HydrationDay(BaseModel):
    source: str
    day: date
    consumed_ml: int | None = None
    goal_ml: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
