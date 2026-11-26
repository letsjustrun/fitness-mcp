"""Helpers shared by every tool module."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from ..errors import FitnessMcpError, ValidationError

log = logging.getLogger(__name__)


def parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError) as e:
        raise ValidationError(f"Invalid date {s!r}. Expected YYYY-MM-DD.") from e


def clamp_range(start: date, end: date, max_days: int) -> tuple[date, date, bool]:
    if start > end:
        raise ValidationError(f"start ({start}) must be on or before end ({end}).")
    if (end - start).days + 1 > max_days:
        return start, start + timedelta(days=max_days - 1), True
    return start, end, False


def error_payload(err: Exception) -> dict:
    """Shape errors so the model gets a readable message, not a stack trace."""
    if isinstance(err, FitnessMcpError):
        return {"error": {"type": err.__class__.__name__, "message": str(err)}}
    log.exception("Unexpected error in tool")
    return {"error": {"type": "InternalError",
                      "message": "Unexpected server error. Check logs on stderr."}}
