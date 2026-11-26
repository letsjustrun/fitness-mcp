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
