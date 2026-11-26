"""Runtime settings.

Env is loaded from, in order of precedence:
  1. process environment
  2. ./.env in the working directory
  3. ~/.fitness_mcp/.env  (useful when the MCP client spawns us from a weird cwd)
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DB = Path.home() / ".fitness_mcp" / "data.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", str(Path.home() / ".fitness_mcp" / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Only used in stdio mode (single-user local install). HTTP mode gets the
    # key from the per-request Authorization header instead.
    garmin_personal_api_key: str | None = Field(default=None, alias="GARMIN_PERSONAL_API_KEY")

    db_path: Path = Field(default=DEFAULT_DB, alias="FITNESS_MCP_DB_PATH")
    log_level: str = Field(default="INFO", alias="FITNESS_MCP_LOG_LEVEL")
    http_timeout_seconds: float = Field(default=30.0, alias="FITNESS_MCP_HTTP_TIMEOUT")
    max_range_days: int = Field(default=90, alias="FITNESS_MCP_MAX_RANGE_DAYS")

    # Optional: path to a custom CA bundle for upstream HTTPS calls. Needed
    # on networks with TLS inspection (Zscaler, Netskope, Blue Coat, etc.)
    # where the proxy re-signs certs with a root the system doesn't ship.
    # If unset, httpx uses its default (certifi).
    ca_bundle: Path | None = Field(default=None, alias="FITNESS_MCP_CA_BUNDLE")

    # --- Transport ----------------------------------------------------------
    # "stdio" (default — Claude Desktop/Code spawn one child process per
    # client and talk JSON-RPC over the pipe; this is what DXT installs use)
    # or "http" (one long-running server that many clients share, served over
    # Streamable HTTP at FITNESS_MCP_HTTP_PATH). CLI flag `--http` wins over
    # the env var.
    transport: str = Field(default="stdio", alias="FITNESS_MCP_TRANSPORT")

    # --- HTTP server (used when transport=http) ----------------------------
    http_host: str = Field(default="127.0.0.1", alias="FITNESS_MCP_HTTP_HOST")
    http_port: int = Field(default=8000, alias="FITNESS_MCP_HTTP_PORT")
    http_path: str = Field(default="/mcp", alias="FITNESS_MCP_HTTP_PATH")

    # Comma-separated list of allowed origins for CORS. claude.ai web / iOS
    # needs the appropriate value here. Default is empty (no CORS headers).
    http_cors_origins: str = Field(default="", alias="FITNESS_MCP_HTTP_CORS_ORIGINS")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.http_cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.db_path = Path(s.db_path).expanduser()
    s.db_path.parent.mkdir(parents=True, exist_ok=True)
    return s


def reset_settings_cache() -> None:
    """Used by tests to pick up monkey-patched env."""
    get_settings.cache_clear()
