from dataclasses import dataclass, field
from pathlib import Path
@dataclass(frozen=True)
class ReviewEngineConfig:
    """Passive observer configuration. The host must opt in by setting enabled."""
    enabled: bool = False
    review_data_root: Path = Path("review_data")
    poll_interval_seconds: float = 60.0
    source_paths: tuple[Path, ...] = field(default_factory=tuple)
    symbols: tuple[str, ...] = field(default_factory=tuple)
    log_level: str = "INFO"
    schema_strict_mode: bool = True
    quarantine_invalid_records: bool = True
