"""Canonical content identities for the PR274 promotion boundary."""
import hashlib
import json
from typing import Any

from learning.common.immutable import thaw


def identity_for(kind: str, payload: Any) -> str:
    encoded = json.dumps({"kind": kind, "payload": thaw(payload)}, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
