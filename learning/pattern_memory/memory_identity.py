"""Canonical serialization and content-addressed PR176 identities."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any
from uuid import UUID, uuid5

from .exceptions import PatternMemoryError

MEMORY_NAMESPACE = UUID("70ef07db-8d83-5e42-9932-fe9826220d9e")
REPORT_NAMESPACE = UUID("58ca118b-9efe-58e7-a906-ec2c1df22d74")


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PatternMemoryError("INVALID_CANONICAL_MEMORY") from exc


def digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def memory_uuid(identity: dict[str, Any]) -> str:
    return str(uuid5(MEMORY_NAMESPACE, digest(identity)))


def report_uuid(identity: dict[str, Any]) -> str:
    return str(uuid5(REPORT_NAMESPACE, digest(identity)))
