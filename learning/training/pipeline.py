"""Deterministic numeric feature pipeline."""
from .models import FeatureMatrix, TrainingConfiguration, TrainingDataset

class FeaturePipeline:
    def transform(self, dataset: TrainingDataset, configuration: TrainingConfiguration) -> FeatureMatrix:
        values, labels = [], []
        for row in dataset.rows:
            try:
                values.append(tuple(row[field] for field in configuration.feature_fields))
                labels.append(row[configuration.label_field])
            except KeyError as exc:
                raise ValueError(f"TRAINING_FIELD_MISSING:{exc.args[0]}") from exc
        return FeatureMatrix(configuration.feature_fields, tuple(values), tuple(labels), dataset.dataset_identity)
