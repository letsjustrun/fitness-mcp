PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS activities (
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
    raw           TEXT,
    PRIMARY KEY (source, id)
);
CREATE INDEX IF NOT EXISTS idx_activities_day   ON activities(day);
CREATE INDEX IF NOT EXISTS idx_activities_sport ON activities(sport);

CREATE TABLE IF NOT EXISTS sleep (
    source      TEXT NOT NULL,
    day         TEXT NOT NULL,
    hours       REAL,
    deep_min    INTEGER,
    rem_min     INTEGER,
    light_min   INTEGER,
    awake_min   INTEGER,
    score       INTEGER,
    raw         TEXT,
    PRIMARY KEY (source, day)
);

CREATE TABLE IF NOT EXISTS daily_wellness (
    source            TEXT NOT NULL,
    day               TEXT NOT NULL,
    steps             INTEGER,
    resting_hr        INTEGER,
    stress_avg        INTEGER,
    body_battery_high INTEGER,
    body_battery_low  INTEGER,
    raw               TEXT,
    PRIMARY KEY (source, day)
);

CREATE TABLE IF NOT EXISTS metrics (
    source TEXT NOT NULL,
    day    TEXT NOT NULL,
    metric TEXT NOT NULL,
    value  REAL,
    raw    TEXT,
    PRIMARY KEY (source, day, metric)
);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric);

CREATE TABLE IF NOT EXISTS sync_log (
    source     TEXT NOT NULL,
    kind       TEXT NOT NULL,
    day        TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (source, kind, day)
);
