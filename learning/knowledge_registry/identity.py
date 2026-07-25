"""Domain-separated canonical identities for PR179 registry artifacts."""
import json
from hashlib import sha256
from uuid import UUID, uuid5

KNOWLEDGE_REGISTRY_NAMESPACE = UUID("e4b9cf05-91ab-53ce-bc2d-b3b1946d37b4")
KNOWLEDGE_REGISTRY_REPORT_NAMESPACE = UUID("681aa922-99be-5db9-aec6-7a8bd8dc616e")
KNOWLEDGE_REGISTRY_SNAPSHOT_NAMESPACE = UUID("705196bb-af54-56d2-8754-e1384a42f267")
KNOWLEDGE_REGISTRY_POLICY_NAMESPACE = UUID("ec143195-c68e-54b6-b222-3a1087453a65")


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return sha256(canonical_bytes(value)).hexdigest()


def _identifier(namespace, value):
    return str(uuid5(namespace, digest(value)))


def registry_uuid(value): return _identifier(KNOWLEDGE_REGISTRY_NAMESPACE, value)
def registry_report_uuid(value): return _identifier(KNOWLEDGE_REGISTRY_REPORT_NAMESPACE, value)
def registry_snapshot_uuid(value): return _identifier(KNOWLEDGE_REGISTRY_SNAPSHOT_NAMESPACE, value)
def registry_policy_uuid(value): return _identifier(KNOWLEDGE_REGISTRY_POLICY_NAMESPACE, value)
