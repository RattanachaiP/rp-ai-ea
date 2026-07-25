"""Domain-separated canonical identities for PR178 governance artifacts."""
import json
from hashlib import sha256
from uuid import UUID, uuid5

PROMOTION_RECORD_NAMESPACE = UUID("99ad31f6-05ab-5ff0-9b20-53a654be625a")
PROMOTION_REPORT_NAMESPACE = UUID("7e9daf91-8700-51ce-91ab-b6ae79d9aa83")
PROMOTION_SNAPSHOT_NAMESPACE = UUID("f57cbd88-3c40-514d-a9e6-f6fe940b30be")
PROMOTION_POLICY_NAMESPACE = UUID("ae64a989-a590-5321-acbc-3a275856b20c")


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return sha256(canonical_bytes(value)).hexdigest()


def _uuid(namespace, value):
    return str(uuid5(namespace, digest(value)))


def promotion_uuid(value): return _uuid(PROMOTION_RECORD_NAMESPACE, value)
def promotion_report_uuid(value): return _uuid(PROMOTION_REPORT_NAMESPACE, value)
def promotion_snapshot_uuid(value): return _uuid(PROMOTION_SNAPSHOT_NAMESPACE, value)
def promotion_policy_uuid(value): return _uuid(PROMOTION_POLICY_NAMESPACE, value)
