"""MCP server entrypoint.

Exposes a small set of high-level tools that read from a local SQLite cache
and transparently refresh stale days from the registered provider (Garmin by
default).

Two transports:
  * stdio (default) — one process per MCP client, Claude Desktop/Code spawn
    the child themselves. This is what DXT installs use.
  * Streamable HTTP — long-running server that many clients share. Enable
    with `--http` or `FITNESS_MCP_TRANSPORT=http`. See `http_server.py`
    for the Starlette wrapping (bearer auth, CORS, /healthz).

Run it:
    fitness-mcp              # stdio
    fitness-mcp --http       # Streamable HTTP
    python -m fitness_mcp.server [--http]
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .config import get_settings
from .logging_setup import configure_logging
from .store.db import get_db
from .tools import activities as tool_activities
from .tools import recovery as tool_recovery
from .tools import singles as tool_singles
from .tools import sleep as tool_sleep
from .tools import trends as tool_trends
from .tools import wellness as tool_wellness
from .tools import wellness_extras as tool_wellness_extras


def create_app() -> MCPServer:
    settings = get_settings()
    configure_logging(settings.log_level)
    # Touch the DB so schema is applied at startup instead of first tool call.
    with get_db() as _:
        pass

    mcp = MCPServer("fitness-mcp")

    @mcp.tool()
    async def get_activities(
        start: str,
        end: str,
        sport: str | None = None,
        force_refresh: bool = False,
    ) -> dict:
        """List workouts between `start` and `end` (YYYY-MM-DD, inclusive).

        Returns a summary per activity: sport, name, start time, duration (min),
        distance (km), avg/max HR, elevation, training load. Use this to answer
        "what did I do last week?" or "show me every run since April".

        - `sport`: optional filter (e.g. "running", "cycling"). Matches case-insensitively.
        - `force_refresh`: skip the freshness cache and refetch every day in range.

        Use `get_activity_detail(activity_id)` for splits / HR zones of one activity.
        """
        return await tool_activities.list_activities(start, end, sport, force_refresh)

    @mcp.tool()
    async def get_activity_detail(activity_id: str) -> dict:
        """Full detail for one activity: splits, HR zones, elevation profile
        where the provider exposes them. Call after `get_activities` to drill in.
        """
        return await tool_activities.activity_detail(activity_id)

    @mcp.tool()
    async def get_sleep(start: str, end: str, force_refresh: bool = False) -> dict:
        """Per-night sleep in [start, end] (YYYY-MM-DD, inclusive).

        Returns hours slept, deep/REM/light/awake minutes, and sleep score per
        night. Recent nights may silently refresh — watches sync late and Garmin
        finalises sleep scoring the following morning.
        """
        return await tool_sleep.list_sleep(start, end, force_refresh)

    @mcp.tool()
    async def get_daily_summary(
        start: str, end: str, force_refresh: bool = False,
    ) -> dict:
        """One row per day combining wellness (steps, resting HR, stress, body
        battery) and sleep (hours, score). Use this for "how was my recovery
        last week?" style questions.
        """
        return await tool_wellness.daily_summary(start, end, force_refresh)

    @mcp.tool()
    async def get_trends(
        metric: str,
        start: str,
        end: str,
        bucket: str = "week",
    ) -> dict:
        """Aggregate a daily metric into day/week/month buckets.

        `metric` is one of:
            resting_hr, steps, stress_avg, body_battery_high, body_battery_low,
            sleep_score, sleep_hours, training_load, vo2max, hrv
        Sums are used for steps and training_load; everything else is averaged.
        `bucket` is "day", "week", or "month" (default "week").
        """
        return await tool_trends.trend(metric, start, end, bucket)

    @mcp.tool()
    async def get_body_battery(
        start: str, end: str, force_refresh: bool = False,
    ) -> dict:
        """Daily body-battery summary between `start` and `end` (YYYY-MM-DD,
        inclusive). Returns per-day min/max, charged/drained totals, and
        latest reading — the Garmin energy reserve you spend during the day."""
        return await tool_wellness_extras.body_battery(start, end, force_refresh)

    @mcp.tool()
    async def get_stress(start: str, end: str, force_refresh: bool = False) -> dict:
        """Per-day stress: average level, max level, and seconds spent in each
        stress band (rest / low / medium / high). Use for trend questions like
        'am I more stressed on work days than weekends?'."""
        return await tool_wellness_extras.stress(start, end, force_refresh)

    @mcp.tool()
    async def get_weight(start: str, end: str, force_refresh: bool = False) -> dict:
        """Weight + body-composition measurements between `start` and `end`.
        One record per manually logged or scale-synced weigh-in: kg, BMI,
        body fat %, muscle / bone mass, body water %."""
        return await tool_wellness_extras.weight(start, end, force_refresh)

    @mcp.tool()
    async def get_hydration(start: str, end: str, force_refresh: bool = False) -> dict:
        """Daily hydration between `start` and `end`: millilitres consumed
        and the goal that day. Null on days where nothing was logged."""
        return await tool_wellness_extras.hydration(start, end, force_refresh)

    @mcp.tool()
    async def get_fitness_age(day: str) -> dict:
        """Garmin's biological fitness age for one date (YYYY-MM-DD) — a
        single number derived from VO2 max, resting HR, body composition
        and activity."""
        return await tool_singles.fitness_age(day)

    @mcp.tool()
    async def get_hrv_night_detail(day: str) -> dict:
        """Detailed HRV for a single night (YYYY-MM-DD): 5-min samples,
        baseline bounds, and Garmin's interpretation. Use when you want
        the per-night story rather than the 7-day summary."""
        return await tool_singles.hrv_night_detail(day)

    @mcp.tool()
    async def get_activity_workouts(activity_id: str) -> dict:
        """Planned structured-workout blocks attached to an activity, if
        the device recorded one (intervals, warmup/cooldown etc.)."""
        return await tool_singles.activity_workouts(activity_id)

    @mcp.tool()
    async def get_recovery_signal(day: str) -> dict:
        """Composite recovery score for one date (YYYY-MM-DD) blending
        sleep score, HRV vs baseline, body battery, resting HR vs baseline,
        and yesterday's training load. Returns 0–100 + every input + a
        one-line advice hint so the model can explain the number."""
        return await tool_recovery.recovery_signal(day)

    return mcp


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="fitness-mcp",
        description="MCP server exposing Garmin Personal API fitness data.",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Serve Streamable HTTP instead of stdio (long-running URL endpoint).",
    )
    parser.add_argument("--host", default=None, help="HTTP host (default: FITNESS_MCP_HTTP_HOST or 127.0.0.1).")
    parser.add_argument("--port", type=int, default=None, help="HTTP port (default: FITNESS_MCP_HTTP_PORT or 8000).")
    args = parser.parse_args()

    settings = get_settings()
    env_http = (settings.transport or "").lower() in {"http", "streamable-http"}
    use_http = args.http or env_http

    app = create_app()
    if use_http:
        if args.host is not None:
            settings.http_host = args.host
        if args.port is not None:
            settings.http_port = args.port
        from .http_server import serve_http  # local import keeps stdio path lightweight
        serve_http(app, settings)
    else:
        # MCPServer.run() defaults to stdio — the behaviour Claude Desktop /
        # Claude Code / DXT installs expect when they spawn the child process.
        app.run()


if __name__ == "__main__":
    main()
