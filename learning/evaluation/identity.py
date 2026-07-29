"""Content identities owned exclusively by the PR272 evaluation boundary."""
import hashlib
import json


def identity_for(kind: str, payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(b"RP-AI-EA/PR272/" + kind.encode() + b"/V1\0" + encoded).hexdigest()
