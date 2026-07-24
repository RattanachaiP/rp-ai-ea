"""PR157 trusted Active Knowledge Registry regressions."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from uuid import uuid4

import pytest

from learning.active_registry import ActiveKnowledgeRegistry


def receipt(
    event_type="ACTIVATION",
    *,
    sequence=1,
    semantic="family/xau",
    knowledge=None,
    previous_knowledge_uuid="",
    previous_activation_uuid="",
    authority=None,
):
    receipt_uuid = str(uuid4())
    return {
        "receipt_uuid": receipt_uuid,
        "event_type": event_type,
        "knowledge_uuid": knowledge or str(uuid4()),
        "semantic_identity": semantic,
        "effective_at": f"2026-01-01T00:00:0{min(sequence, 9)}Z",
        "sequence": sequence,
        "source_event_uuid": str(uuid4()),
        "source_authority": authority or ("PromotionAuthority" if event_type in {"ACTIVATION", "SUPERSESSION"} else "LifecycleAuthority"),
        "source_version": "1.0",
        "schema_version": "1.0",
        "configuration_version": "1.0",
        "lineage_reference": str(uuid4()),
        "reason": event_type.lower(),
        "signature": uuid4().hex,
        "previous_knowledge_uuid": previous_knowledge_uuid,
        "previous_activation_uuid": previous_activation_uuid,
        "metadata": {},
    }


def registry(tmp_path, *receipts, now=None):
    trust = {item["receipt_uuid"]: item["signature"] for item in receipts}
    fixed = now or datetime(2026, 1, 1, tzinfo=timezone.utc)
    return ActiveKnowledgeRegistry(root=tmp_path, trusted_receipts=trust, clock=lambda: fixed)


def test_trusted_activation_lookup_history_and_idempotent_replay(tmp_path):
    activation = receipt()
    instance = registry(tmp_path, activation)
    entry = instance.register(activation)
    assert instance.register(activation) == entry
    assert instance.get_active(entry.knowledge_uuid) == entry
    assert instance.lookup(entry.semantic_identity) == entry
    assert instance.list_active() == (entry,)
    assert instance.history() == (entry,)


def test_untrusted_duplicate_and_out_of_sequence_receipts_fail_closed(tmp_path):
    first = receipt()
    instance = registry(tmp_path, first)
    instance.register(first)

    forged = receipt(sequence=2, semantic="family/other")
    with pytest.raises(ValueError, match="UNTRUSTED"):
        instance.register(forged)

    duplicate = receipt(sequence=2, semantic=first["semantic_identity"])
    trusted = registry(tmp_path, first, duplicate)
    with pytest.raises(ValueError, match="DUPLICATE_ACTIVE_SEMANTIC"):
        trusted.register(duplicate)

    gap = receipt(sequence=4, semantic="family/gap")
    gap_registry = registry(tmp_path, first, gap)
    with pytest.raises(ValueError, match="SEQUENCE_MISMATCH"):
        gap_registry.register(gap)


def test_atomic_supersession_and_authorized_retirement(tmp_path):
    activation = receipt()
    replacement = receipt(sequence=2, event_type="SUPERSESSION", semantic=activation["semantic_identity"])
    instance = registry(tmp_path, activation, replacement)
    old = instance.register(activation)
    replacement["previous_knowledge_uuid"] = old.knowledge_uuid
    replacement["previous_activation_uuid"] = old.activation_uuid
    new = instance.register(replacement)

    assert len(instance.history()) == 2  # one activation plus one atomic supersession event
    assert instance.get_active(old.knowledge_uuid) is None
    assert instance.get_by_uuid(old.knowledge_uuid).status == "SUPERSEDED"
    assert instance.resolve(old.semantic_identity) == new

    retirement = receipt(
        sequence=3,
        event_type="RETIREMENT",
        semantic=new.semantic_identity,
        knowledge=new.knowledge_uuid,
        previous_activation_uuid=new.activation_uuid,
    )
    instance.trusted_receipts[retirement["receipt_uuid"]] = retirement["signature"]
    retired = instance.apply_lifecycle_event(retirement)
    assert retired.status == "RETIRED"
    assert instance.get_active(new.knowledge_uuid) is None
    assert instance.list_active() == ()


def test_registry_cannot_retire_from_activation_api(tmp_path):
    terminal = receipt(event_type="RETIREMENT", previous_activation_uuid=str(uuid4()))
    instance = registry(tmp_path, terminal)
    with pytest.raises(ValueError, match="ACTIVATION_RECEIPT_REQUIRED"):
        instance.register(terminal)


def test_corrupted_storage_blocks_reads_and_writes(tmp_path):
    activation = receipt()
    instance = registry(tmp_path, activation)
    instance.register(activation)
    corrupt = instance.storage.directory / "entry_00000000-0000-0000-0000-000000000000.json"
    corrupt.write_text("{broken", encoding="utf-8")
    with pytest.raises(RuntimeError, match="ACTIVE_REGISTRY_CORRUPTED"):
        instance.list_active()
    second = receipt(sequence=2, semantic="family/second")
    instance.trusted_receipts[second["receipt_uuid"]] = second["signature"]
    with pytest.raises(RuntimeError, match="ACTIVE_REGISTRY_CORRUPTED"):
        instance.register(second)


def test_semantic_lock_contention_and_stale_recovery(tmp_path):
    activation = receipt()
    instance = registry(tmp_path, activation)
    with instance._semantic_lock(activation["semantic_identity"]):
        with pytest.raises(RuntimeError, match="LOCK_CONTENDED"):
            with instance._semantic_lock(activation["semantic_identity"]):
                pass

    semantic = "family/stale"
    stale = receipt(semantic=semantic)
    stale_instance = registry(tmp_path, stale, now=datetime(2026, 1, 2, tzinfo=timezone.utc))
    lock_dir = tmp_path / "active_registry_locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{sha256(semantic.encode('utf-8')).hexdigest()}.lock"
    lock_path.write_text(json.dumps({
        "owner": "dead",
        "expires_at": (datetime(2026, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)).isoformat(),
    }), encoding="utf-8")
    assert stale_instance.register(stale).status == "ACTIVE"
