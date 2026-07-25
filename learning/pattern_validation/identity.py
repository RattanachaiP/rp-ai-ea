"""Domain-separated canonical identities for PR177 artifacts."""
from __future__ import annotations
import json
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid5

VALIDATION_RECORD_NAMESPACE = UUID("5de5f31b-7dd2-5e48-9068-475c86ad47cb")
VALIDATION_REPORT_NAMESPACE = UUID("30bd02f7-e10c-52f1-91be-afc5506854f2")
VALIDATION_SNAPSHOT_NAMESPACE = UUID("b45b60b5-a98a-5814-9e2c-3fd3b46e282e")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def validation_uuid(value: Any) -> str:
    return str(uuid5(VALIDATION_RECORD_NAMESPACE, digest(value)))


def validation_report_uuid(value: Any) -> str:
    return str(uuid5(VALIDATION_REPORT_NAMESPACE, digest(value)))


def validation_snapshot_uuid(value: Any) -> str:
    return str(uuid5(VALIDATION_SNAPSHOT_NAMESPACE, digest(value)))
