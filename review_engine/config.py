from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

@dataclass(frozen=True)
class ReviewEngineConfig:
    """Deployment settings. Collection is deliberately disabled by default."""
    enabled: bool = False
    review_data_root: Path = Path("review_data")
    poll_interval_seconds: float = 60.0
    source_paths: tuple[Path, ...] = ()
    symbols: tuple[str, ...] = ()
    log_level: str = "INFO"
    schema_strict_mode: bool = True
    quarantine_invalid_records: bool = True
