"""PR244 canonical Decision Intelligence activation lifecycle regression tests."""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(1, str(Path(__file__).parent))

from learning.decision_intelligence import (
    DecisionIntelligenceActivation,
    DecisionIntelligenceError,
    DecisionIntelligenceRepository,
)
from learning.decision_intelligence.operator_activation import commit_activation
from runtime.production_startup import ProductionStartupConfiguration, ProductionStartupError
from test_pr184_decision_intelligence import setup_engine


OWNER = "PR184_DECISION_INTELLIGENCE_OWNER"


def prepared(root):
    context_report, _, engine = setup_engine(root)
    report = engine.run(context_report)
    return engine.repository, report.decision_intelligences[0], engine.repository.snapshots()[0]


def resolve(repository, item):
    return ProductionStartupConfiguration.from_canonical_repository(
        observations=(("feed_stability", .99), ("price_stream_continuity", .999),
                      ("market_session_quality", .9), ("spread_quality", 20.0),
                      ("latency_quality", 100.0), ("slippage_expectation", 10.0),
                      ("market_liquidity_quality", .9), ("environment_consistency", .9),
                      ("data_freshness", 2.0), ("environment_completeness", .95)),
        captured_at=item.created_at, intelligence_root=repository.root,
    )


def test_missing_activation_rejected(tmp_path):
    repository, item, _ = prepared(tmp_path)
    with pytest.raises(ProductionStartupError, match="ACTIVATION_MISSING"):
        resolve(repository, item)


def test_malformed_activation_rejected(tmp_path):
    repository, item, snapshot = prepared(tmp_path)
    repository.activation_root.mkdir()
    (repository.activation_root / f"{item.intelligence_uuid}.json").write_text("{}")
    with pytest.raises(ProductionStartupError, match="CORRUPT_DECISION_INTELLIGENCE_ACTIVATION"):
        resolve(repository, item)


def test_wrong_authority_rejected(tmp_path):
    repository, item, snapshot = prepared(tmp_path)
    with pytest.raises(DecisionIntelligenceError, match="WRONG.*AUTHORITY"):
        repository.activate(item, snapshot, authority_owner="RUNTIME", activated_at=item.created_at)
    commit_activation(repository_root=repository.root, intelligence_uuid=item.intelligence_uuid,
                      snapshot_uuid=snapshot.snapshot_uuid, authority_owner=OWNER,
                      activated_at=item.created_at)
    _replace_activation(repository, authority_owner="RUNTIME")
    with pytest.raises(ProductionStartupError, match="WRONG.*AUTHORITY"):
        resolve(repository, item)


def _replace_activation(repository, **changes):
    original = repository.activations()[0]
    values = original.identity_payload() | changes
    path = repository.activation_root / f"{original.activation_uuid}.json"
    path.unlink()
    replacement = DecisionIntelligenceActivation.create(**values)
    repository.save_activation(replacement)
    return repository.activation_root / f"{replacement.activation_uuid}.json"


def test_digest_mismatch_rejected(tmp_path):
    repository, item, snapshot = prepared(tmp_path)
    commit_activation(repository_root=repository.root, intelligence_uuid=item.intelligence_uuid,
                      snapshot_uuid=snapshot.snapshot_uuid, authority_owner=OWNER,
                      activated_at=item.created_at)
    path = next(repository.activation_root.glob("*.json"))
    data = json.loads(path.read_text())
    data["activation_digest"] = "0" * 64
    path.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")))
    with pytest.raises(ProductionStartupError, match="CORRUPT_DECISION_INTELLIGENCE_ACTIVATION"):
        resolve(repository, item)


def test_lineage_mismatch_rejected(tmp_path):
    repository, item, snapshot = prepared(tmp_path)
    commit_activation(repository_root=repository.root, intelligence_uuid=item.intelligence_uuid,
                      snapshot_uuid=snapshot.snapshot_uuid, authority_owner=OWNER,
                      activated_at=item.created_at)
    _replace_activation(repository, repository_digest="0" * 64)
    with pytest.raises(ProductionStartupError, match="SNAPSHOT_MISMATCH"):
        resolve(repository, item)


def test_activation_not_ready_rejected(tmp_path):
    repository, item, snapshot = prepared(tmp_path)
    commit_activation(repository_root=repository.root, intelligence_uuid=item.intelligence_uuid,
                      snapshot_uuid=snapshot.snapshot_uuid, authority_owner=OWNER,
                      activated_at=item.created_at)
    _replace_activation(repository, activation_state="PENDING")
    with pytest.raises(ProductionStartupError, match="ACTIVATION_NOT_READY"):
        resolve(repository, item)


def test_valid_canonical_activation_enters_decision_engine(tmp_path):
    repository, item, snapshot = prepared(tmp_path)
    activation = commit_activation(
        repository_root=repository.root, intelligence_uuid=item.intelligence_uuid,
        snapshot_uuid=snapshot.snapshot_uuid, authority_owner=OWNER,
        activated_at=item.created_at,
    )
    config = resolve(repository, item)
    assert activation.activation_state == "READY"
    assert config.decision_intelligence_uuid == item.intelligence_uuid
