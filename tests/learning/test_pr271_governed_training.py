"""Adversarial PR271 governed offline training contracts."""
from dataclasses import replace
import pytest
from bridge.v28.offline_learning import build_learning_dataset, create_learning_registry, publish_learning_evidence
from bridge.v28.outcome_analytics import analyze_learning_evidence
from bridge.v28.outcome_evidence import publish_outcome_evidence
from bridge.v28.outcome_registry import create_outcome_registry
from learning.training import (CandidateRegistry, FeatureMatrix, ModelMetadata, TrainingConfiguration,
                               TrainingDatasetLoader, TrainingSession)
from tests.test_v28_outcome_intelligence import outcome


def authorities(*records):
    outcomes = create_outcome_registry()
    for record in records or (outcome(),): outcomes = outcomes.append(record)
    oe = publish_outcome_evidence(outcomes)
    learning_dataset = build_learning_dataset(outcomes, oe)
    evidence = publish_learning_evidence(outcomes, oe, learning_dataset)
    registry = create_learning_registry().append(evidence)
    return registry, evidence, analyze_learning_evidence(evidence)

@pytest.fixture(scope="module")
def governed():
    return authorities(outcome("one"))


def configuration(offset=0.0):
    return TrainingConfiguration(("confidence", "spread"), algorithm_parameters={"offset": offset},
                                 policy_identity="offline-training-policy-v1", code_version="git:pr271")


def test_direct_authoritative_contracts_have_one_canonical_row_owner(governed):
    registry, evidence, analytics = governed
    dataset = TrainingDatasetLoader().load(registry, evidence, analytics)
    assert dataset.record_count == len(evidence.dataset.examples) == 1
    assert tuple(r.outcome_identity for r in dataset.rows) == evidence.dataset.source_outcome_identities
    assert tuple(r.position for r in dataset.rows) == (0,)
    assert dataset.source_learning_registry_identity == registry.registry_identity
    assert dataset.source_analytics_identity == analytics.report_identity


def test_forged_sources_and_source_order_tampering_fail_closed(governed):
    registry, evidence, analytics = governed
    original = analytics.report_identity
    object.__setattr__(analytics, "report_identity", "forged")
    with pytest.raises(ValueError, match="AUTHORITATIVE"):
        TrainingDatasetLoader().load(registry, evidence, analytics)
    object.__setattr__(analytics, "report_identity", original)
    dataset = TrainingDatasetLoader().load(registry, evidence, analytics)
    with pytest.raises(ValueError, match="LINEAGE"):
        replace(dataset, rows=(replace(dataset.rows[0], position=1, row_identity=""),), dataset_identity="")


def test_duplicate_outcomes_and_nonfinite_values_are_rejected(governed):
    dataset = TrainingDatasetLoader().load(*governed)
    with pytest.raises(ValueError, match="LINEAGE"):
        replace(dataset, rows=(dataset.rows[0], dataset.rows[0]), record_count=2, dataset_identity="")
    with pytest.raises(ValueError, match="ROW_INVALID"):
        replace(dataset.rows[0], label=float("nan"), row_identity="")
    with pytest.raises(ValueError, match="FEATURE_MATRIX"):
        FeatureMatrix(("x",), ((float("inf"),),), (1.0,), ("row",), "dataset")


def test_algorithm_and_parameters_are_explicit_and_behavioral(governed):
    with pytest.raises(ValueError, match="CONFIGURATION"):
        replace(configuration(), algorithm="UNIMPLEMENTED", configuration_identity="")
    with pytest.raises(ValueError, match="CONFIGURATION"):
        replace(configuration(), algorithm_parameters={"unused": 1}, configuration_identity="")
    dataset = TrainingDatasetLoader().load(*governed)
    assert TrainingSession(configuration(1.0)).run(dataset).candidate.model_artifact["prediction"] == \
           TrainingSession(configuration()).run(dataset).candidate.model_artifact["prediction"] + 1.0


def test_result_self_validation_and_replay_reject_forged_expected_artifact(governed):
    dataset = TrainingDatasetLoader().load(*governed)
    session = TrainingSession(configuration())
    result = session.run(dataset)
    assert session.replay(dataset, result)
    object.__setattr__(result.evidence, "replay_digest", "forged")
    assert not session.replay(dataset, result)
    with pytest.raises(ValueError, match="BINDING"):
        replace(result, evidence=replace(result.evidence, replay_digest="forged", evidence_identity=""))


def test_metadata_consistency_and_candidate_authority_are_hardened(governed):
    result = TrainingSession(configuration()).run(TrainingDatasetLoader().load(*governed))
    metadata = result.candidate.metadata
    with pytest.raises(ValueError, match="METADATA"):
        ModelMetadata(metadata.algorithm, metadata.algorithm_parameters, metadata.feature_names, 2,
                      metadata.training_row_identities, metadata.metrics)
    for authority in ("runtime_authorized", "strategy_authorized", "risk_authorized", "broker_authorized",
                      "deployment_authorized", "promotion_authorized", "production_authorized"):
        with pytest.raises(ValueError, match="AUTHORITY"):
            replace(result.candidate, **{authority: True, "model_identity": ""})


def test_registry_binds_lineage_policy_and_complete_ancestry(governed):
    result = TrainingSession(configuration()).run(TrainingDatasetLoader().load(*governed))
    empty = CandidateRegistry(); populated = empty.append(result.candidate, result.evidence)
    assert populated.previous_registry_identity == empty.registry_identity
    with pytest.raises(ValueError, match="DUPLICATE"):
        populated.append(result.candidate, result.evidence)
    mismatched = replace(result.evidence, lineage_identity="forged", evidence_identity="")
    with pytest.raises(ValueError, match="BINDING"):
        empty.append(result.candidate, mismatched)
    with pytest.raises(ValueError, match="PREDECESSOR"):
        replace(populated, previous_registry_identity="forged", registry_identity="")
    entry = populated.entries[0]
    with pytest.raises(ValueError, match="BINDING"):
        replace(populated, entries=(replace(entry, previous_entry_identity="forged", entry_identity=""),),
                previous_registry_identity=empty.registry_identity, registry_identity="")
