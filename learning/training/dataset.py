"""Fail-closed loader accepting only governed learning inputs."""
from __future__ import annotations
from typing import Iterable, Mapping, Any
from .models import TrainingDataset, TrainingSource

class TrainingDatasetLoader:
    def load(self, sources: Iterable[TrainingSource], *, dataset_version: str = "1.0") -> TrainingDataset:
        governed = tuple(sources)
        if not governed: raise ValueError("TRAINING_SOURCES_REQUIRED")
        rows: list[Mapping[str, Any]] = []
        for source in governed:
            if not isinstance(source, TrainingSource): raise TypeError("UNGOVERNED_TRAINING_SOURCE")
            rows.extend(source.records)
        if not rows: raise ValueError("TRAINING_DATASET_EMPTY")
        return TrainingDataset(governed, tuple(rows), dataset_version)
