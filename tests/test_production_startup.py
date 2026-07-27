"""Canonical PR184 -> PR185 -> governed Runtime startup coverage."""

import os
import json
from math import inf, nan
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(1, str(Path(__file__).parent / "learning"))

from learning.execution_environment.policy import ENVIRONMENT_DIMENSIONS
from runtime.production_startup import (
    GovernedProductionStartup,
    ProductionStartupConfiguration,
    ProductionStartupError,
)
from test_pr184_decision_intelligence import setup_engine


GOOD = (0.99, 0.999, 0.9, 20.0, 100.0, 10.0, 0.9, 0.9, 2.0, 0.95)


def configured(root: Path):
    context_report, _, engine = setup_engine(root)
    report = engine.run(context_report)
    intelligence = report.decision_intelligences[0]
    snapshot = engine.repository.snapshots()[0]
    engine.repository.activate(intelligence, snapshot)
    return ProductionStartupConfiguration(
        decision_intelligence_uuid=intelligence.intelligence_uuid,
        decision_intelligence_digest=intelligence.intelligence_digest,
        decision_intelligence_snapshot_uuid=snapshot.snapshot_uuid,
        decision_intelligence_snapshot_digest=snapshot.snapshot_digest,
        decision_intelligence_repository_digest=snapshot.repository_digest,
        intelligence_policy_uuid=snapshot.intelligence_policy_uuid,
        intelligence_policy_digest=snapshot.intelligence_policy_digest,
        intelligence_policy_version=snapshot.intelligence_policy_version,
        intelligence_engine_version=snapshot.intelligence_engine_version,
        observations=tuple(zip(ENVIRONMENT_DIMENSIONS, GOOD)),
        captured_at=intelligence.created_at,
        intelligence_root=root / "decision_intelligence",
        recommendation_root=root / "decision_recommendation",
        readiness_root=root / "execution_readiness",
        environment_root=root / "execution_environment",
        feasibility_root=root / "execution_feasibility",
        package_root=root / "execution_package",
    )


def test_clean_downstream_state_creates_pr185_and_starts_runtime_once(tmp_path, monkeypatch):
    config = configured(tmp_path)
    assert not config.recommendation_root.exists()
    calls = []
    monkeypatch.delenv("RP_EXECUTION_PACKAGE_UUID", raising=False)

    result = GovernedProductionStartup(config).start(
        lambda: calls.append(os.environ["RP_EXECUTION_PACKAGE_UUID"]) or "RUNNING"
    )

    assert result == "RUNNING"
    assert len(calls) == 1
    assert calls[0] == next(config.package_root.glob("*.json")).stem
    for root in (
        config.recommendation_root,
        config.readiness_root,
        config.environment_root,
        config.feasibility_root,
        config.package_root,
    ):
        record = next(root.glob("*.json"))
        assert record.stem in record.read_text()
    assert len(tuple((config.environment_root / "evidence").glob("*.json"))) == 1


def test_operator_configuration_resolves_identity_without_manual_bundle(tmp_path):
    explicit = configured(tmp_path)
    resolved = ProductionStartupConfiguration.from_canonical_repository(
        observations=explicit.observations, captured_at=explicit.captured_at,
        intelligence_root=explicit.intelligence_root,
        recommendation_root=explicit.recommendation_root,
        readiness_root=explicit.readiness_root,
        environment_root=explicit.environment_root,
        feasibility_root=explicit.feasibility_root,
        package_root=explicit.package_root,
    )
    assert resolved == explicit


def test_operator_resolution_fails_closed_without_pr184(tmp_path):
    context_report, _, engine = setup_engine(tmp_path)
    engine.run(context_report)
    assert engine.repository.records()
    assert engine.repository.activations() == ()
    with pytest.raises(ProductionStartupError, match="DECISION_INTELLIGENCE_ACTIVATION_MISSING"):
        ProductionStartupConfiguration.from_canonical_repository(
            observations=tuple(zip(ENVIRONMENT_DIMENSIONS, GOOD)),
            captured_at="2026-07-27T12:00:00Z",
            intelligence_root=engine.repository.root,
        )


def _append_unrelated_ready(config):
    from learning.decision_intelligence import (
        DecisionIntelligence,
        DecisionIntelligenceRepository,
        DecisionIntelligenceSnapshot,
    )

    repository = DecisionIntelligenceRepository(config.intelligence_root)
    previous = repository.snapshots()[0]
    source = repository.records()[0]
    values = source.identity_payload()
    values["created_at"] = "2026-07-25T00:00:01Z"
    unrelated = DecisionIntelligence.create(**values)
    repository.save(unrelated)
    snapshot_values = previous.identity_payload()
    snapshot_values.update(
        intelligence_identities=repository.identities(),
        record_count=2,
        repository_digest=repository.digest(),
        previous_snapshot_uuid=previous.snapshot_uuid,
        previous_snapshot_digest=previous.snapshot_digest,
        generated_at="2026-07-25T00:00:01Z",
    )
    snapshot = DecisionIntelligenceSnapshot.create(**snapshot_values)
    repository.save_snapshot(snapshot)
    return repository, unrelated, snapshot


def test_activation_is_stable_after_unrelated_ready_append(tmp_path):
    explicit = configured(tmp_path)
    first = ProductionStartupConfiguration.from_canonical_repository(
        observations=explicit.observations,
        captured_at=explicit.captured_at,
        intelligence_root=explicit.intelligence_root,
    )
    _append_unrelated_ready(explicit)
    second = ProductionStartupConfiguration.from_canonical_repository(
        observations=explicit.observations,
        captured_at=explicit.captured_at,
        intelligence_root=explicit.intelligence_root,
    )
    assert first.decision_intelligence_uuid == second.decision_intelligence_uuid
    assert first.decision_intelligence_snapshot_uuid == second.decision_intelligence_snapshot_uuid


def test_historical_ready_records_do_not_create_startup_ambiguity(tmp_path):
    config = configured(tmp_path)
    repository, unrelated, _ = _append_unrelated_ready(config)
    activation = repository.activations()[0]
    resolved = ProductionStartupConfiguration.from_canonical_repository(
        observations=config.observations,
        captured_at=config.captured_at,
        intelligence_root=config.intelligence_root,
    )
    assert resolved.decision_intelligence_uuid == activation.intelligence_uuid
    assert resolved.decision_intelligence_uuid != unrelated.intelligence_uuid


def test_duplicate_activation_fails_closed(tmp_path):
    from learning.decision_intelligence import DecisionIntelligenceActivation

    config = configured(tmp_path)
    repository, _, _ = _append_unrelated_ready(config)
    original = repository.activations()[0]
    values = original.identity_payload()
    values["repository_digest"] = "0" * 64
    repository.save_activation(DecisionIntelligenceActivation.create(**values))
    with pytest.raises(ProductionStartupError, match="DECISION_INTELLIGENCE_ACTIVATION_AMBIGUOUS"):
        ProductionStartupConfiguration.from_canonical_repository(
            observations=config.observations,
            captured_at=config.captured_at,
            intelligence_root=config.intelligence_root,
        )


def test_corrupt_activation_fails_closed(tmp_path):
    config = configured(tmp_path)
    activation = next((config.intelligence_root / "activations").glob("*.json"))
    activation.write_text("{}")
    with pytest.raises(ProductionStartupError, match="CORRUPT_DECISION_INTELLIGENCE_ACTIVATION_REPOSITORY"):
        ProductionStartupConfiguration.from_canonical_repository(
            observations=config.observations,
            captured_at=config.captured_at,
            intelligence_root=config.intelligence_root,
        )


@pytest.mark.parametrize("field,value,reason", [
    ("repository_digest", "0" * 64, "SNAPSHOT_MISMATCH"),
    ("intelligence_policy_version", "PR184.POLICY.999", "SNAPSHOT_MISMATCH"),
    ("intelligence_engine_version", "PR184.9.9", "SNAPSHOT_MISMATCH"),
])
def test_activation_partition_mismatch_fails_closed(tmp_path, field, value, reason):
    from learning.decision_intelligence import DecisionIntelligenceActivation

    config = configured(tmp_path)
    activation_path = next((config.intelligence_root / "activations").glob("*.json"))
    values = json.loads(activation_path.read_text())
    values = {
        key: item for key, item in values.items()
        if key not in {"activation_uuid", "activation_digest"}
    }
    values[field] = value
    activation_path.unlink()
    repository = __import__(
        "learning.decision_intelligence", fromlist=["DecisionIntelligenceRepository"]
    ).DecisionIntelligenceRepository(config.intelligence_root)
    repository.save_activation(DecisionIntelligenceActivation.create(**values))
    with pytest.raises(ProductionStartupError, match=reason):
        ProductionStartupConfiguration.from_canonical_repository(
            observations=config.observations,
            captured_at=config.captured_at,
            intelligence_root=config.intelligence_root,
        )


def test_repeated_identical_command_resolves_same_activation(tmp_path):
    config = configured(tmp_path)
    arguments = dict(
        observations=config.observations,
        captured_at=config.captured_at,
        intelligence_root=config.intelligence_root,
    )
    assert (
        ProductionStartupConfiguration.from_canonical_repository(**arguments)
        == ProductionStartupConfiguration.from_canonical_repository(**arguments)
    )


def test_missing_malformed_and_duplicate_intelligence_fail_before_runtime(tmp_path, monkeypatch):
    config = configured(tmp_path)
    calls = []
    missing = ProductionStartupConfiguration(
        **(config.__dict__ | {"decision_intelligence_uuid": "00000000-0000-0000-0000-000000000000"})
    )
    with pytest.raises(ProductionStartupError, match="DECISION_INTELLIGENCE_MISSING"):
        GovernedProductionStartup(missing).start(lambda: calls.append(True))
    with pytest.raises(ProductionStartupError, match="INVALID_DECISION_INTELLIGENCE_IDENTITY"):
        ProductionStartupConfiguration(**(config.__dict__ | {"decision_intelligence_uuid": "BAD"}))

    from learning.decision_intelligence import DecisionIntelligenceRepository

    original = DecisionIntelligenceRepository.records
    monkeypatch.setattr(
        DecisionIntelligenceRepository,
        "records",
        lambda repository: original(repository) + original(repository),
    )
    with pytest.raises(ProductionStartupError, match="DECISION_INTELLIGENCE_MISSING"):
        GovernedProductionStartup(config).start(lambda: calls.append(True))
    assert calls == []


def test_incomplete_chain_and_unauthorized_runtime_never_start(tmp_path, monkeypatch):
    config = configured(tmp_path)
    startup = GovernedProductionStartup(config)
    with pytest.raises(ProductionStartupError, match="UNAUTHORIZED_RUNTIME_TARGET"):
        startup.start(object())

    calls = []
    monkeypatch.setattr(
        "runtime.production_startup.ProductionExecutionInitializer.start",
        lambda initializer, runtime=None: (_ for _ in ()).throw(ValueError("PR208 failed")),
    )
    with pytest.raises(ProductionStartupError, match="PRODUCTION_STARTUP_REJECTED"):
        startup.start(lambda: calls.append(True))
    assert calls == []


@pytest.mark.parametrize(
    "observations",
    [
        tuple(zip(reversed(ENVIRONMENT_DIMENSIONS), GOOD)),
        tuple(zip(ENVIRONMENT_DIMENSIONS[:-1], GOOD[:-1])),
        tuple(zip(ENVIRONMENT_DIMENSIONS, (1,) + GOOD[1:])),
        tuple(zip(ENVIRONMENT_DIMENSIONS, (nan,) + GOOD[1:])),
        tuple(zip(ENVIRONMENT_DIMENSIONS, (inf,) + GOOD[1:])),
        tuple(zip(ENVIRONMENT_DIMENSIONS, (-0.1,) + GOOD[1:])),
    ],
)
def test_configuration_rejects_invalid_observation_contract(tmp_path, observations):
    config = configured(tmp_path)
    with pytest.raises(ProductionStartupError, match="INVALID_ENVIRONMENT_OBSERVATIONS"):
        ProductionStartupConfiguration(**(config.__dict__ | {"observations": observations}))


@pytest.mark.parametrize("captured_at", [None, "", "   ", 1])
def test_configuration_rejects_invalid_capture_timestamp(tmp_path, captured_at):
    config = configured(tmp_path)
    with pytest.raises(ProductionStartupError, match="INVALID_CAPTURED_AT"):
        ProductionStartupConfiguration(**(config.__dict__ | {"captured_at": captured_at}))


@pytest.mark.parametrize("root", ["learning_data", None, 1, object()])
def test_configuration_rejects_non_path_repository_roots(tmp_path, root):
    config = configured(tmp_path)
    with pytest.raises(ProductionStartupError, match="INVALID_REPOSITORY_ROOT"):
        ProductionStartupConfiguration(**(config.__dict__ | {"intelligence_root": root}))


def test_corrupt_pr184_record_and_snapshot_lineage_never_start_runtime(tmp_path):
    for corrupt_snapshot in (False, True):
        root = tmp_path / str(corrupt_snapshot)
        config = configured(root)
        calls = []
        repository_root = config.intelligence_root
        target = next(
            (repository_root / "snapshots").glob("*.json")
            if corrupt_snapshot
            else repository_root.glob("*.json")
        )
        data = json.loads(target.read_text())
        if corrupt_snapshot:
            data["repository_digest"] = "0" * 64
        else:
            data["intelligence_digest"] = "0" * 64
        target.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")))
        with pytest.raises(ProductionStartupError):
            GovernedProductionStartup(config).start(lambda: calls.append(True))
        assert calls == []


@pytest.mark.parametrize("mode", ["not_ready", "missing", "duplicate"])
def test_invalid_recommendation_owner_output_never_starts_runtime(tmp_path, monkeypatch, mode):
    config = configured(tmp_path)
    calls = []
    from learning.decision_recommendation import GovernedDecisionRecommendationEngine

    original = GovernedDecisionRecommendationEngine.run

    def invalid(engine, source):
        report = original(engine, source)
        if mode == "not_ready":
            object.__setattr__(report.recommendations[0], "recommendation_state", "RECOMMENDATION_NOT_READY")
        elif mode == "missing":
            object.__setattr__(report.recommendations[0], "decision_intelligence_uuid", "00000000-0000-0000-0000-000000000000")
        else:
            object.__setattr__(report, "recommendations", report.recommendations * 2)
        return report

    monkeypatch.setattr(GovernedDecisionRecommendationEngine, "run", invalid)
    reason = "RECOMMENDATION_NOT_READY" if mode == "not_ready" else "RECOMMENDATION_MISSING"
    with pytest.raises(ProductionStartupError, match=reason):
        GovernedProductionStartup(config).start(lambda: calls.append(True))
    assert calls == []


def test_replay_is_idempotent_and_invokes_runtime_once_per_explicit_start(tmp_path, monkeypatch):
    config = configured(tmp_path)
    startup = GovernedProductionStartup(config)
    calls = []
    monkeypatch.delenv("RP_EXECUTION_PACKAGE_UUID", raising=False)
    startup.start(lambda: calls.append(os.environ["RP_EXECUTION_PACKAGE_UUID"]))
    before = {path: path.read_bytes() for path in tmp_path.glob("**/*.json")}
    startup.start(lambda: calls.append(os.environ["RP_EXECUTION_PACKAGE_UUID"]))
    assert {path: path.read_bytes() for path in before} == before
    assert set(tmp_path.glob("**/*.json")) == set(before)
    assert len(calls) == 2 and calls[0] == calls[1]


def test_explicit_non_head_snapshot_is_immune_to_unrelated_new_head(tmp_path, monkeypatch):
    from learning.decision_intelligence import (
        DecisionIntelligence,
        DecisionIntelligenceRepository,
        DecisionIntelligenceSnapshot,
    )

    config = configured(tmp_path)
    repository = DecisionIntelligenceRepository(config.intelligence_root)
    target_snapshot = repository.snapshots()[0]
    source = repository.records()[0]
    unrelated_values = source.identity_payload()
    unrelated_values["created_at"] = "2026-07-25T00:00:01Z"
    unrelated = DecisionIntelligence.create(**unrelated_values)
    repository.save(unrelated)
    head_values = target_snapshot.identity_payload()
    head_values.update(
        intelligence_identities=repository.identities(),
        record_count=2,
        repository_digest=repository.digest(),
        previous_snapshot_uuid=target_snapshot.snapshot_uuid,
        previous_snapshot_digest=target_snapshot.snapshot_digest,
        generated_at="2026-07-25T00:00:01Z",
    )
    head = DecisionIntelligenceSnapshot.create(**head_values)
    repository.save_snapshot(head)
    calls = []
    monkeypatch.delenv("RP_EXECUTION_PACKAGE_UUID", raising=False)

    GovernedProductionStartup(config).start(lambda: calls.append(True))

    recommendation_files = tuple(config.recommendation_root.glob("*.json"))
    assert len(calls) == 1
    assert len(recommendation_files) == 1
    recommendation = json.loads(recommendation_files[0].read_text())
    assert recommendation["decision_intelligence_uuid"] == config.decision_intelligence_uuid
    assert recommendation["decision_intelligence_snapshot_uuid"] == target_snapshot.snapshot_uuid
    assert head.snapshot_uuid != target_snapshot.snapshot_uuid


def test_disconnected_snapshot_lineage_fails_before_runtime(tmp_path):
    from learning.decision_intelligence import (
        DecisionIntelligenceRepository,
        DecisionIntelligenceSnapshot,
    )

    config = configured(tmp_path)
    repository = DecisionIntelligenceRepository(config.intelligence_root)
    source = repository.snapshots()[0]
    values = source.identity_payload()
    values.update(
        previous_snapshot_uuid=None,
        previous_snapshot_digest=None,
        generated_at="2026-07-25T00:00:01Z",
    )
    repository.save_snapshot(DecisionIntelligenceSnapshot.create(**values))
    calls = []
    with pytest.raises(ProductionStartupError, match="SNAPSHOT_MISMATCH"):
        GovernedProductionStartup(config).start(lambda: calls.append(True))
    assert calls == []
