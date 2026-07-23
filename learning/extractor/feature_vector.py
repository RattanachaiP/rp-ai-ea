from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping
from pathlib import Path
from uuid import uuid4
@dataclass(frozen=True)
class FeatureVector:
    uuid: str
    trade_uuid: str
    schema_version: str
    feature_version: str
    created_at: str
    features: Mapping[str, object] = field(default_factory=dict)
    def __post_init__(self) -> None:
        object.__setattr__(self, "features", MappingProxyType(dict(self.features)))
    @classmethod
    def create(cls, trade_uuid: str, features: Mapping[str, object], *, schema_version: str = "1.0", feature_version: str = "1.0", uuid: str | None = None, created_at: str | None = None) -> "FeatureVector":
        return cls(uuid or str(uuid4()), trade_uuid, schema_version, feature_version, created_at or datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"), features)
    def to_dict(self) -> dict[str, object]:
        return {"uuid": self.uuid, "trade_uuid": self.trade_uuid, "schema_version": self.schema_version, "feature_version": self.feature_version, "created_at": self.created_at, "features": dict(self.features)}

@dataclass(frozen=True)
class FeatureVectorWriteResult:
    created: bool
    path: Path
    conflict: bool = False

class FeatureVectorRepository:
    """Append-only JSON storage for validated feature vectors."""
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def save(self, vector: FeatureVector) -> FeatureVectorWriteResult:
        from .validator import FeatureVectorValidator
        import json
        import os
        FeatureVectorValidator().validate(vector)
        if any(part in vector.uuid for part in ("/", "\\", "..")):
            raise ValueError("INVALID_FEATURE_VECTOR_UUID")
        year = vector.created_at[:4]
        if len(year) != 4 or not year.isdigit():
            raise ValueError("INVALID_CREATED_AT")
        path = self.root / "features" / year / f"feature_{vector.uuid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(vector.to_dict(), sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        temporary = path.with_suffix(".json.tmp")
        if path.exists():
            try:
                if json.loads(path.read_text(encoding="utf-8")).get("uuid") == vector.uuid:
                    return FeatureVectorWriteResult(False, path)
            except (OSError, ValueError):
                pass
            return FeatureVectorWriteResult(False, path, True)
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temporary, path)
            temporary.unlink()
            return FeatureVectorWriteResult(True, path)
        except FileExistsError:
            return FeatureVectorWriteResult(False, path, True)
        finally:
            if temporary.exists():
                temporary.unlink()
