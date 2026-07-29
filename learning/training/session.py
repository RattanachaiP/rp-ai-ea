from .identity import identity_for
from .models import CandidateModel, ModelMetadata, TrainingConfiguration, TrainingDataset, TrainingEvidence, TrainingLineage, TrainingResult
from .pipeline import FeaturePipeline
class TrainingSession:
    def __init__(self, configuration: TrainingConfiguration, pipeline: FeaturePipeline | None = None):
        TrainingConfiguration(**configuration.__dict__); self.configuration = configuration; self.pipeline = pipeline or FeaturePipeline()
    def run(self, dataset: TrainingDataset) -> TrainingResult:
        matrix = self.pipeline.transform(dataset, self.configuration)
        lineage = TrainingLineage(dataset.dataset_identity, self.configuration.configuration_identity, matrix.pipeline_identity,
            dataset.source_learning_registry_identity, dataset.source_learning_evidence_identity, dataset.source_analytics_identity,
            self.configuration.policy_identity)
        prediction = sum(matrix.labels) / len(matrix.labels) + self.configuration.algorithm_parameters["offset"]
        mse = sum((x - prediction) ** 2 for x in matrix.labels) / len(matrix.labels)
        metadata = ModelMetadata(self.configuration.algorithm, self.configuration.algorithm_parameters, matrix.feature_names,
                                 len(matrix.labels), matrix.row_identities, {"training_mse": mse})
        candidate = CandidateModel({"format": "PR271.DETERMINISTIC_MEAN.1.0", "prediction": prediction}, metadata, lineage)
        session_payload = {"configuration_identity": lineage.configuration_identity, "lineage_identity": lineage.lineage_identity,
                           "candidate_identity": candidate.model_identity, "policy_identity": self.configuration.policy_identity}
        evidence = TrainingEvidence(identity_for("TRAINING_SESSION", session_payload), candidate.model_identity,
            lineage.lineage_identity, lineage.configuration_identity, self.configuration.policy_identity,
            identity_for("TRAINING_REPLAY", session_payload))
        return TrainingResult(candidate, evidence)
    def replay(self, dataset: TrainingDataset, expected: TrainingResult) -> bool:
        try: TrainingResult(**expected.__dict__)
        except (TypeError, ValueError, AttributeError): return False
        return self.run(dataset) == expected
