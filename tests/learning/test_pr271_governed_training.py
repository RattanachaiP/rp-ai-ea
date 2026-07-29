"""PR271 governed offline training foundation contracts."""
from dataclasses import replace
import pytest
from learning.training import (CandidateRegistry, TrainingConfiguration, TrainingDatasetLoader,
                               TrainingSession, TrainingSource)


def source(kind, identity, records):
    return TrainingSource(kind, identity, "1.0", tuple(records))


def configuration():
    return TrainingConfiguration(("confidence", "spread"), "outcome", "DETERMINISTIC_MEAN",
                                 {"mode": "offline"}, 271, "offline-training-policy-v1", "git:pr271")


def dataset():
    return TrainingDatasetLoader().load((
        source("LEARNING_REGISTRY", "registry-1", ({"confidence": .8, "spread": .2, "outcome": 2.0},)),
        source("LEARNING_EVIDENCE", "evidence-1", ({"confidence": .4, "spread": .4, "outcome": -1.0},)),
        source("OUTCOME_ANALYTICS", "analytics-1", ({"confidence": .6, "spread": .3, "outcome": .5},)),
    ))


def test_training_is_reproducible_identity_bound_and_candidate_only():
    session = TrainingSession(configuration())
    first, second = session.run(dataset()), session.run(dataset())
    assert first == second and session.replay(dataset(), first)
    assert first.candidate.candidate_only
    assert not first.candidate.production_authorized
    assert not first.candidate.runtime_compatible
    assert first.evidence.output_type == "CANDIDATE_MODEL_ONLY"
    assert first.candidate.lineage.dataset_identity == dataset().dataset_identity


def test_loader_rejects_ungoverned_and_empty_sources():
    with pytest.raises(ValueError, match="TRAINING_SOURCE_INVALID"):
        source("RUNTIME", "runtime", ({"outcome": 1},))
    with pytest.raises(TypeError, match="UNGOVERNED"):
        TrainingDatasetLoader().load(({"source_type": "LEARNING_REGISTRY"},))
    with pytest.raises(ValueError, match="EMPTY"):
        TrainingDatasetLoader().load((source("LEARNING_REGISTRY", "registry", ()),))


def test_configuration_and_pipeline_fail_closed():
    with pytest.raises(ValueError, match="CONFIGURATION"):
        TrainingConfiguration(("x", "x"), "y", "mean", {}, 0, "policy", "code")
    incomplete = TrainingDatasetLoader().load((source("LEARNING_EVIDENCE", "e", ({"confidence": 1, "outcome": 1},)),))
    with pytest.raises(ValueError, match="TRAINING_FIELD_MISSING:spread"):
        TrainingSession(configuration()).run(incomplete)


def test_candidate_registry_is_append_only_and_evidence_bound():
    result = TrainingSession(configuration()).run(dataset())
    empty = CandidateRegistry()
    populated = empty.append(result.candidate, result.evidence)
    assert not empty.entries and populated.entries[0].candidate == result.candidate
    with pytest.raises(ValueError, match="DUPLICATE"):
        populated.append(result.candidate, result.evidence)
    forged = replace(result.evidence, candidate_identity="forged", evidence_identity="")
    with pytest.raises(ValueError, match="MISMATCH"):
        empty.append(result.candidate, forged)


def test_candidate_authority_and_artifacts_are_tamper_evident():
    result = TrainingSession(configuration()).run(dataset())
    with pytest.raises(ValueError, match="AUTHORITY"):
        replace(result.candidate, production_authorized=True, model_identity="")
    with pytest.raises(TypeError):
        result.candidate.model_artifact["prediction"] = 999
    object.__setattr__(result.candidate, "model_identity", "forged")
    assert not TrainingSession(configuration()).replay(dataset(), result)
