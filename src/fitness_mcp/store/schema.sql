PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS activities (
    tenant_id     TEXT NOT NULL,
    source        TEXT NOT NULL,
    id            TEXT NOT NULL,
    day           TEXT NOT NULL,
    sport         TEXT,
    name          TEXT,
    start         TEXT,
    km            REAL,
    minutes       REAL,
    avg_hr        INTEGER,
    max_hr        INTEGER,
    elevation_m   REAL,
    training_load REAL,
    -- Running form (null outside running)
    avg_cadence                INTEGER,
    max_cadence                INTEGER,
    avg_ground_contact_ms      INTEGER,
    avg_vertical_oscillation_cm REAL,
    avg_vertical_ratio         REAL,
    avg_stride_length_cm       REAL,
    -- HR zone breakdown (seconds)
    hr_z1_sec     INTEGER,
    hr_z2_sec     INTEGER,
    hr_z3_sec     INTEGER,
    hr_z4_sec     INTEGER,
    hr_z5_sec     INTEGER,
    -- Training effect
    aerobic_te             REAL,
    anaerobic_te           REAL,
    training_effect_label  TEXT,
    -- Fastest splits during the workout
    fastest_1k_sec   REAL,
    fastest_mile_sec REAL,
    -- Power + laps
    avg_power     INTEGER,
    max_power     INTEGER,
    lap_count     INTEGER,
    raw           TEXT,
    PRIMARY KEY (tenant_id, source, id)
);
CREATE INDEX IF NOT EXISTS idx_activities_tenant_day ON activities(tenant_id, day);
CREATE INDEX IF NOT EXISTS idx_activities_tenant_sport ON activities(tenant_id, sport);

CREATE TABLE IF NOT EXISTS sleep (
    tenant_id   TEXT NOT NULL,
    source      TEXT NOT NULL,
    day         TEXT NOT NULL,
    hours       REAL,
    deep_min    INTEGER,
    rem_min     INTEGER,
    light_min   INTEGER,
    awake_min   INTEGER,
    score       INTEGER,
    raw         TEXT,
    PRIMARY KEY (tenant_id, source, day)
);

CREATE TABLE IF NOT EXISTS daily_wellness (
    tenant_id         TEXT NOT NULL,
    source            TEXT NOT NULL,
    day               TEXT NOT NULL,
    steps             INTEGER,
    resting_hr        INTEGER,
    stress_avg        INTEGER,
    body_battery_high INTEGER,
    body_battery_low  INTEGER,
    raw               TEXT,
    PRIMARY KEY (tenant_id, source, day)
);

CREATE TABLE IF NOT EXISTS metrics (
    tenant_id TEXT NOT NULL,
    source    TEXT NOT NULL,
    day       TEXT NOT NULL,
    metric    TEXT NOT NULL,
    value     REAL,
    raw       TEXT,
    PRIMARY KEY (tenant_id, source, day, metric)
);
CREATE INDEX IF NOT EXISTS idx_metrics_tenant_metric ON metrics(tenant_id, metric);

CREATE TABLE IF NOT EXISTS sync_log (
    tenant_id  TEXT NOT NULL,
    source     TEXT NOT NULL,
    kind       TEXT NOT NULL,
    day        TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, source, kind, day)
);

CREATE TABLE IF NOT EXISTS body_battery (
    tenant_id   TEXT NOT NULL,
    source      TEXT NOT NULL,
    day         TEXT NOT NULL,
    min_value   INTEGER,
    max_value   INTEGER,
    charged     INTEGER,
    drained     INTEGER,
    latest      INTEGER,
    raw         TEXT,
    PRIMARY KEY (tenant_id, source, day)
);

CREATE TABLE IF NOT EXISTS stress (
    tenant_id    TEXT NOT NULL,
    source       TEXT NOT NULL,
    day          TEXT NOT NULL,
    avg_level    INTEGER,
    max_level    INTEGER,
    rest_sec     INTEGER,
    activity_sec INTEGER,
    low_sec      INTEGER,
    medium_sec   INTEGER,
    high_sec     INTEGER,
    raw          TEXT,
    PRIMARY KEY (tenant_id, source, day)
);

CREATE TABLE IF NOT EXISTS weight (
    tenant_id       TEXT NOT NULL,
    source          TEXT NOT NULL,
    day             TEXT NOT NULL,
    taken_at        TEXT,
    weight_kg       REAL,
    bmi             REAL,
    body_fat_pct    REAL,
    muscle_mass_kg  REAL,
    bone_mass_kg    REAL,
    body_water_pct  REAL,
    raw             TEXT,
    PRIMARY KEY (tenant_id, source, day)
);

CREATE TABLE IF NOT EXISTS hydration (
    tenant_id   TEXT NOT NULL,
    source      TEXT NOT NULL,
    day         TEXT NOT NULL,
    consumed_ml INTEGER,
    goal_ml     INTEGER,
    raw         TEXT,
    PRIMARY KEY (tenant_id, source, day)
);
