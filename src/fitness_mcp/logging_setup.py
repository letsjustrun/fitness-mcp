"""Logging that ONLY writes to stderr.

Stdout is reserved for the MCP JSON-RPC stream under stdio transport. A stray
`print()` corrupts the protocol and the client silently disconnects. Any code
in this package that needs to say something at runtime must go through this
logger.
"""
from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    root = logging.getLogger()
    root.setLevel(level.upper())
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root.addHandler(handler)
    _CONFIGURED = True
