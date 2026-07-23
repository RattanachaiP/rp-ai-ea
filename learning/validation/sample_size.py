"""Minimum sample-size validation."""
from __future__ import annotations

DEFAULT_MINIMUM_SAMPLES = 30

def validate_sample_size(samples: int | float, minimum_samples: int = DEFAULT_MINIMUM_SAMPLES) -> bool:
    if minimum_samples < 1:
        raise ValueError("MINIMUM_SAMPLES_MUST_BE_POSITIVE")
    return int(samples) >= minimum_samples
has_minimum_sample_size = validate_sample_size
