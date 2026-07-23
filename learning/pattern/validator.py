"""Validation gates for untrusted pattern candidates."""
from __future__ import annotations
import math
from collections.abc import Iterable
from .candidate import CandidatePattern
from .schema import PATTERN_VERSION, REQUIRED_STATISTICS, STATUSES
class PatternValidationError(ValueError): pass
class PatternValidator:
    def validate(self, pattern: CandidatePattern, existing: Iterable[CandidatePattern] = ()) -> None:
        if not pattern.pattern_uuid or not pattern.conditions: raise PatternValidationError("REQUIRED_FIELDS")
        if pattern.pattern_version != PATTERN_VERSION: raise PatternValidationError("INVALID_PATTERN_VERSION")
        if pattern.status not in STATUSES: raise PatternValidationError("INVALID_STATUS")
        missing = set(REQUIRED_STATISTICS) - set(pattern.statistics)
        if missing: raise PatternValidationError("MISSING_STATISTICS:" + ",".join(sorted(missing)))
        stats = pattern.statistics
        if any(not isinstance(stats[key], (int, float)) or isinstance(stats[key], bool) or not math.isfinite(float(stats[key])) for key in REQUIRED_STATISTICS): raise PatternValidationError("INVALID_STATISTICS")
        if any(float(stats[key]) < 0 for key in ("samples", "wins", "losses", "breakeven", "win_rate", "stddev_profit")): raise PatternValidationError("INVALID_STATISTICS")
        if int(stats["wins"]) + int(stats["losses"]) + int(stats["breakeven"]) > int(stats["samples"]): raise PatternValidationError("INCONSISTENT_OUTCOMES")
        if not 0 <= float(stats["win_rate"]) <= 1: raise PatternValidationError("INVALID_WIN_RATE")
        for prior in existing:
            if prior.pattern_uuid != pattern.pattern_uuid and dict(prior.conditions) == dict(pattern.conditions): raise PatternValidationError("DUPLICATE_PATTERN")
