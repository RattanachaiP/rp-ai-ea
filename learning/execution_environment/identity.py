"""Canonical, domain-separated identities for PR187 artifacts."""

import json
from hashlib import sha256
from uuid import UUID, uuid5

RECORD_NAMESPACE = UUID("f1870001-0000-5000-8000-000000000001")
SNAPSHOT_NAMESPACE = UUID("f1870002-0000-5000-8000-000000000002")
REPORT_NAMESPACE = UUID("f1870003-0000-5000-8000-000000000003")
POLICY_NAMESPACE = UUID("f1870004-0000-5000-8000-000000000004")
EVIDENCE_NAMESPACE = UUID("f1870005-0000-5000-8000-000000000005")


def canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value):
    return sha256(canonical_bytes(value)).hexdigest()


def _uuid(namespace, value):
    return str(uuid5(namespace, digest(value)))


def environment_evidence_uuid(value):
    return _uuid(EVIDENCE_NAMESPACE, value)


def execution_environment_uuid(value):
    return _uuid(RECORD_NAMESPACE, value)


def snapshot_uuid(value):
    return _uuid(SNAPSHOT_NAMESPACE, value)


def report_uuid(value):
    return _uuid(REPORT_NAMESPACE, value)


def policy_uuid(value):
    return _uuid(POLICY_NAMESPACE, value)
