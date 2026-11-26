"""Error types surfaced to the model as a clear message, not a stack trace."""
from __future__ import annotations


class FitnessMcpError(Exception):
    """Base — any subclass is safe to show the model verbatim."""


class ConfigError(FitnessMcpError):
    """Setup problem (missing env var, unreadable DB path)."""


class ProviderAuthError(FitnessMcpError):
    """Credentials missing, rejected, or token exchange failed."""


class ProviderFetchError(FitnessMcpError):
    """Upstream provider returned a non-2xx or an unexpected shape."""


class ValidationError(FitnessMcpError):
    """Tool input failed validation (bad date, start > end, unknown metric)."""
