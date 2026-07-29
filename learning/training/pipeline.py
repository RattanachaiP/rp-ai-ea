from .models import FeatureMatrix, TrainingConfiguration, TrainingDataset
class FeaturePipeline:
    def transform(self, dataset: TrainingDataset, configuration: TrainingConfiguration) -> FeatureMatrix:
        TrainingDataset(**dataset.__dict__); TrainingConfiguration(**configuration.__dict__)
        try: values = tuple(tuple(row.feature_values[f] for f in configuration.feature_fields) for row in dataset.rows)
        except KeyError as exc: raise ValueError(f"TRAINING_FIELD_MISSING:{exc.args[0]}") from exc
        return FeatureMatrix(configuration.feature_fields, values, tuple(r.label for r in dataset.rows),
                             tuple(r.row_identity for r in dataset.rows), dataset.dataset_identity)
