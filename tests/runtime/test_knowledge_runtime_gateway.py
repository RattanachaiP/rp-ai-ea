from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

import pytest

from learning.active_registry import ActiveKnowledgeRegistry
from runtime import KnowledgeRuntimeGateway


def receipt(*, schema="1.0.0", configuration="1.0.0"):
    value = {"receipt_uuid": str(uuid4()), "event_type": "ACTIVATION", "knowledge_uuid": str(uuid4()),
             "semantic_identity": "family/xau", "effective_at": "2026-01-01T00:00:00Z", "sequence": 1,
             "source_event_uuid": str(uuid4()), "source_authority": "PromotionAuthority", "source_version": "1.0",
             "schema_version": schema, "configuration_version": configuration, "lineage_reference": str(uuid4()),
             "reason": "promoted", "metadata": {}}
    value["signature"] = sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return value


def registry(tmp_path, item):
    value = ActiveKnowledgeRegistry(root=tmp_path, trusted_receipts={item["receipt_uuid"]: item["signature"]},
                                    clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    value.register(item)
    return value


def test_gateway_only_exposes_compatible_active_snapshot_and_caches(tmp_path):
    item = receipt(); gateway = KnowledgeRuntimeGateway(registry(tmp_path, item))
    first, second = gateway.snapshot(), gateway.snapshot()
    assert first is second
    assert gateway.lookup(item["knowledge_uuid"]) == first.entries[0]
    assert gateway.resolve("family/xau") == first.entries[0]
    assert first.rejected == {}
    with pytest.raises(TypeError, match="REGISTRY_REQUIRED"):
        KnowledgeRuntimeGateway(object())


def test_gateway_rejects_incompatible_entries_without_interpreting_them(tmp_path):
    item = receipt(schema="2.0.0"); gateway = KnowledgeRuntimeGateway(registry(tmp_path, item))
    snapshot = gateway.snapshot()
    assert snapshot.entries == ()
    assert snapshot.rejected == {item["knowledge_uuid"]: "UNSUPPORTED_KNOWLEDGE_SCHEMA_VERSION"}
    assert gateway.get_active(item["knowledge_uuid"]) is None


def test_gateway_propagates_registry_corruption_instead_of_serving_cache(tmp_path):
    item = receipt(); source = registry(tmp_path, item); gateway = KnowledgeRuntimeGateway(source)
    gateway.snapshot()
    (source.storage.directory / "entry_broken.json").write_text("{", encoding="utf-8")
    with pytest.raises(RuntimeError, match="ACTIVE_REGISTRY_CORRUPTED"):
        gateway.snapshot()
