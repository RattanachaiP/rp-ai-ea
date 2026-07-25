"""Canonical, domain-separated identities for PR181 artifacts."""

import json
from hashlib import sha256
from uuid import UUID, uuid5

SELECTION_NAMESPACE = UUID("162d28b9-cdf2-56c3-8f87-2eef8a94036f")
SNAPSHOT_NAMESPACE = UUID("92308e52-a683-5340-848c-e6c462087723")
REPORT_NAMESPACE = UUID("2171e9c7-e19c-5ceb-9b93-d872409232be")
POLICY_NAMESPACE = UUID("0b405f51-0a8b-516d-a5ef-d2d947ff44c8")


def canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value):
    return sha256(canonical_bytes(value)).hexdigest()


def identifier(namespace, value):
    return str(uuid5(namespace, digest(value)))


def selection_uuid(value):
    return identifier(SELECTION_NAMESPACE, value)


def snapshot_uuid(value):
    return identifier(SNAPSHOT_NAMESPACE, value)


def report_uuid(value):
    return identifier(REPORT_NAMESPACE, value)


def policy_uuid(value):
    return identifier(POLICY_NAMESPACE, value)
