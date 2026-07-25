"""Canonical, domain-separated identities for PR180 runtime artifacts."""

import json
from hashlib import sha256
from uuid import UUID, uuid5


RUNTIME_PACKAGE_NAMESPACE = UUID("9ae211f4-2992-59f0-aedd-6d2297d95ba5")
RUNTIME_SNAPSHOT_NAMESPACE = UUID("605970ca-ee97-59bb-b7bf-a755ed35ad2d")
RUNTIME_REPORT_NAMESPACE = UUID("aa8f1218-935a-5fa5-927b-8aad9c1b518d")


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return sha256(canonical_bytes(value)).hexdigest()


def identifier(namespace, value):
    return str(uuid5(namespace, digest(value)))


def package_uuid(value):
    return identifier(RUNTIME_PACKAGE_NAMESPACE, value)


def snapshot_uuid(value):
    return identifier(RUNTIME_SNAPSHOT_NAMESPACE, value)


def report_uuid(value):
    return identifier(RUNTIME_REPORT_NAMESPACE, value)
