from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

@dataclass(frozen=True)
class ReviewEngineConfig:
    """Configuration only; disabled by default and never changes trading runtime state."""
    enabled: bool = False
    review_data_root: Path = Path(r"D:\RP_AI_EA\review_data")
    poll_interval_seconds: int = 60
    source_paths: Tuple[Path, ...] = field(default_factory=tuple)
    symbols: Tuple[str, ...] = field(default_factory=tuple)
    log_level: str = "INFO"
    schema_strict_mode: bool = True
    quarantine_invalid_records: bool = True
