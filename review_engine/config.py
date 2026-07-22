"""Configuration for the isolated RAIP observer."""
from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True)
class ReviewEngineConfig:
    enabled: bool = False
    review_data_root: Path = Path(r"D:\RP_AI_EA\review_data")
    poll_interval_seconds: int = 60
    source_paths: tuple[Path, ...] = field(default_factory=tuple)
    symbols: tuple[str, ...] = field(default_factory=tuple)
    log_level: str = "INFO"
    schema_strict_mode: bool = True
    quarantine_invalid_records: bool = True
