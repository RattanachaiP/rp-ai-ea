"""Replay-safe offline training session with candidate-only output."""
from __future__ import annotations
from .identity import identity_for
from .models import (CandidateModel, ModelMetadata, TrainingConfiguration, TrainingDataset,
                     TrainingEvidence, TrainingLineage, TrainingResult)
from .pipeline import FeaturePipeline

class TrainingSession:
    """Train a deterministic mean-label baseline without any runtime dependency."""
    def __init__(self, configuration: TrainingConfiguration, pipeline: FeaturePipeline | None = None):
        self.configuration = configuration
        self.pipeline = pipeline or FeaturePipeline()

    def run(self, dataset: TrainingDataset) -> TrainingResult:
        matrix = self.pipeline.transform(dataset, self.configuration)
        lineage = TrainingLineage(dataset.dataset_identity, tuple(s.source_digest for s in dataset.sources),
                                  self.configuration.configuration_identity, matrix.pipeline_identity)
        mean = sum(matrix.labels) / len(matrix.labels)
        mse = sum((label - mean) ** 2 for label in matrix.labels) / len(matrix.labels)
        artifact = {"format": "PR271.DETERMINISTIC_MEAN.1.0", "prediction": mean,
                    "random_seed": self.configuration.random_seed}
        metadata = ModelMetadata(self.configuration.algorithm, self.configuration.algorithm_parameters,
                                 matrix.feature_names, len(matrix.labels), {"training_mse": mse})
        candidate = CandidateModel(artifact, metadata, lineage)
        session_payload = {"configuration_identity": self.configuration.configuration_identity,
                           "lineage_identity": lineage.lineage_identity, "candidate_identity": candidate.model_identity}
        session_identity = identity_for("TRAINING_SESSION", session_payload)
        replay_digest = identity_for("TRAINING_REPLAY", session_payload)
        evidence = TrainingEvidence(session_identity, candidate.model_identity, lineage.lineage_identity,
                                    replay_digest, self.configuration.policy_identity)
        return TrainingResult(candidate, evidence)

    def replay(self, dataset: TrainingDataset, expected: TrainingResult) -> bool:
        return self.run(dataset) == expected
