"""Secret-handling primitives for log redaction.

Secrets are stored as pydantic ``SecretStr`` so their ``repr`` is already
masked. ``redact`` produces a log-safe copy of a flat mapping by replacing
secret values with ``REDACTED``. Task 42 wires this into the structured
logger; until then this is the only redaction surface.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import SecretStr

REDACTED = "***"


def redact(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: (REDACTED if isinstance(val, SecretStr) else val) for key, val in values.items()}
