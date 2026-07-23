"""In-memory lookup of immutable validation outcomes."""
from __future__ import annotations
from .schema import ValidationResult
class ValidationRegistry:
    def __init__(self) -> None: self._results: dict[str, ValidationResult] = {}
    def register(self, result: ValidationResult) -> ValidationResult:
        prior = self._results.get(result.pattern_uuid)
        if prior is not None and prior != result: raise ValueError("VALIDATION_IMMUTABLE")
        self._results[result.pattern_uuid] = result; return result
    def get(self, pattern_uuid: str) -> ValidationResult | None: return self._results.get(pattern_uuid)
