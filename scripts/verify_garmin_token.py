#!/usr/bin/env python3
"""Stand-alone health check for the Garmin Personal API credentials.

Run it from the repo root after setting up `.env`:
    python scripts/verify_garmin_token.py

It performs *only* the token exchange — no data endpoints are hit. A success
means the key is valid, the service is reachable, and the bearer cache works.
If this succeeds but a tool call fails later, that's a data-endpoint issue in
the official client, not an auth issue here.

Writes to stderr. Exits non-zero on failure.
"""
from __future__ import annotations

import sys

import requests
from garmin_personal_api import HttpError, PersonalApiAuthenticator

from fitness_mcp.config import get_settings
from fitness_mcp.logging_setup import configure_logging


def main() -> int:
    configure_logging("INFO")
    settings = get_settings()
    if not settings.garmin_personal_api_key:
        print("ERROR: GARMIN_PERSONAL_API_KEY is not set. See README.", file=sys.stderr)
        return 2

    session = requests.Session()
    if settings.ca_bundle:
        session.verify = str(settings.ca_bundle)

    auth = PersonalApiAuthenticator(
        timeout=settings.http_timeout_seconds,
        session=session,
    )
    try:
        bearer = auth.obtain_token(settings.garmin_personal_api_key)
    except HttpError as e:
        print(f"AUTH_FAIL: HTTP {getattr(e, 'status_code', '?')}: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"AUTH_FAIL: {e.__class__.__name__}: {e}", file=sys.stderr)
        return 1
    finally:
        auth.close()
        session.close()

    print(
        f"OK: exchanged key for a bearer token (len=REDACTED, "
        f"expires at unix {bearer.expires_at}).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
