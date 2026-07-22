"""Configuration for the passive RAIP review-data writer."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ReviewEngineConfig:
    """RAIP is disabled unless an operator explicitly enables it."""
    enabled: bool = False
    review_data_root: Path = Path(r"D:\RP_AI_EA\review_data")
    poll_interval_seconds: int = 60
    source_paths: Mapping[str, Path] = field(default_factory=dict)
    symbols: Sequence[str] = ("XAUUSD",)
    log_level: str = "INFO"
    schema_strict_mode: bool = True
    quarantine_invalid_records: bool = True
