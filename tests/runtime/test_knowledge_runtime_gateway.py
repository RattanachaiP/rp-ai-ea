from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

import pytest

from learning.active_registry import ActiveKnowledgeRegistry
from runtime import KnowledgeRuntimeGateway, RuntimeKnowledgeDescriptor


def receipt(*, schema="1.0.0", configuration="1.0.0", semantic="family/xau", sequence=1):
    value = {
        "receipt_uuid": str(uuid4()), "event_type": "ACTIVATION", "knowledge_uuid": str(uuid4()),
        "semantic_identity": semantic, "effective_at": "2026-01-01T00:00:00Z", "sequence": sequence,
        "source_event_uuid": str(uuid4()), "source_authority": "PromotionAuthority", "source_version": "1.0",
        "schema_version": schema, "configuration_version": configuration, "lineage_reference": str(uuid4()),
        "reason": "promoted", "metadata": {"runtime_key": semantic},
    }
    value["signature"] = sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return value


def registry(tmp_path, item):
    value = ActiveKnowledgeRegistry(
        root=tmp_path,
        trusted_receipts={item["receipt_uuid"]: item["signature"]},
        clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    value.register(item)
    return value


class Reader:
    def __init__(self, entries):
        self.entries = tuple(entries)

    def list_active(self):
        return self.entries


def test_gateway_exposes_runtime_dto_metadata_and_identity_cache(tmp_path):
    item = receipt()
    gateway = KnowledgeRuntimeGateway(registry(tmp_path, item), clock=lambda: "2026-01-01T00:00:01Z")
    first, second = gateway.snapshot(), gateway.snapshot()
    assert first is second
    assert isinstance(first.entries[0], RuntimeKnowledgeDescriptor)
    assert first.entries[0].__class__.__module__ == "runtime.knowledge_gateway"
    assert gateway.lookup(item["knowledge_uuid"]) == first.entries[0]
    assert gateway.resolve("family/xau") == first.entries[0]
    assert first.highest_registry_sequence == 1
    assert first.source_event_count == 1
    assert first.gateway_contract_version == "1.0.0"
    assert first.compatibility_policy_version == "1.0.0"
    assert first.generated_at == "2026-01-01T00:00:01Z"
    assert first.rejected == {}
    with pytest.raises(TypeError, match="READER_REQUIRED"):
        KnowledgeRuntimeGateway(object())


def test_gateway_rejects_schema_configuration_and_malformed_semver(tmp_path):
    cases = [
        ("2.0.0", "1.0.0", "UNSUPPORTED_KNOWLEDGE_SCHEMA_VERSION"),
        ("1.0.0", "2.0.0", "UNSUPPORTED_KNOWLEDGE_CONFIGURATION_VERSION"),
        ("01.0.0", "1.0.0", "UNSUPPORTED_KNOWLEDGE_SCHEMA_VERSION"),
        ("١.0.0", "1.0.0", "UNSUPPORTED_KNOWLEDGE_SCHEMA_VERSION"),
        ("1.0", "1.0.0", "UNSUPPORTED_KNOWLEDGE_SCHEMA_VERSION"),
    ]
    for index, (schema, configuration, reason) in enumerate(cases):
        item = receipt(schema=schema, configuration=configuration, semantic=f"family/{index}")
        snapshot = KnowledgeRuntimeGateway(registry(tmp_path / str(index), item)).snapshot()
        assert snapshot.entries == ()
        assert snapshot.rejected == {item["knowledge_uuid"]: reason}


def test_policy_configuration_changes_snapshot_digest(tmp_path):
    item = receipt()
    source = registry(tmp_path, item)
    first = KnowledgeRuntimeGateway(source, supported_schema_majors=(1,)).snapshot()
    second = KnowledgeRuntimeGateway(source, supported_schema_majors=(1, 2)).snapshot()
    assert first.registry_digest == second.registry_digest
    assert first.snapshot_digest != second.snapshot_digest
    assert first.supported_schema_majors == (1,)
    assert second.supported_schema_majors == (1, 2)


def test_gateway_propagates_registry_corruption_instead_of_serving_cache(tmp_path):
    item = receipt()
    source = registry(tmp_path, item)
    gateway = KnowledgeRuntimeGateway(source)
    gateway.snapshot()
    (source.storage.directory / "entry_broken.json").write_text("{", encoding="utf-8")
    with pytest.raises(RuntimeError, match="ACTIVE_REGISTRY_CORRUPTED"):
        gateway.snapshot()


def test_gateway_rejects_duplicate_projection_invariants(tmp_path):
    item = receipt()
    active = registry(tmp_path, item).list_active()[0]
    duplicate_semantic = replace(active, knowledge_uuid=str(uuid4()), activation_uuid=str(uuid4()), sequence=2)
    with pytest.raises(RuntimeError, match="PROJECTION_INVALID"):
        KnowledgeRuntimeGateway(Reader((active, duplicate_semantic))).snapshot()
    duplicate_knowledge = replace(active, semantic_identity="family/other", activation_uuid=str(uuid4()), sequence=2)
    with pytest.raises(RuntimeError, match="PROJECTION_INVALID"):
        KnowledgeRuntimeGateway(Reader((active, duplicate_knowledge))).snapshot()
    duplicate_activation = replace(active, knowledge_uuid=str(uuid4()), semantic_identity="family/other", sequence=2)
    with pytest.raises(RuntimeError, match="PROJECTION_INVALID"):
        KnowledgeRuntimeGateway(Reader((active, duplicate_activation))).snapshot()
    duplicate_sequence = replace(active, knowledge_uuid=str(uuid4()), semantic_identity="family/other", activation_uuid=str(uuid4()))
    with pytest.raises(RuntimeError, match="PROJECTION_INVALID"):
        KnowledgeRuntimeGateway(Reader((active, duplicate_sequence))).snapshot()


def test_gateway_detects_registry_rollback(tmp_path):
    first_item = receipt()
    first = registry(tmp_path, first_item).list_active()[0]
    advanced = replace(first, sequence=2)
    reader = Reader((advanced,))
    gateway = KnowledgeRuntimeGateway(reader)
    assert gateway.snapshot().highest_registry_sequence == 2
    reader.entries = ()
    with pytest.raises(RuntimeError, match="ROLLBACK_DETECTED"):
        gateway.snapshot()


def test_empty_registry_is_valid_and_deterministic():
    gateway = KnowledgeRuntimeGateway(Reader(()), clock=lambda: "2026-01-01T00:00:00Z")
    first = gateway.snapshot()
    assert first.entries == ()
    assert first.rejected == {}
    assert first.highest_registry_sequence == 0
    assert first.source_event_count == 0
    assert gateway.snapshot() is first
