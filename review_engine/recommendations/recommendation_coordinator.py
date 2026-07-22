from concurrent.futures import Future, ThreadPoolExecutor
import json, logging
from pathlib import Path
from .recommendation_engine import RecommendationEngine
from .recommendation_repository import RecommendationRepository
from .recommendation_validator import RecommendationValidator

class RecommendationCoordinator:
    """Asynchronous, failure-isolated post-Insight processor with no runtime imports."""
    def __init__(self, root, repository=None, engine=None, validator=None):
        self.root = Path(root); self.repository = repository or RecommendationRepository(root); self.engine = engine or RecommendationEngine(); self.validator = validator or RecommendationValidator()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="raip-recommendation"); self.log = logging.getLogger(__name__)
    def process_available(self):
        paths = sorted((self.root / "insights").glob("*/insight_repository.json"))
        if not paths: return None
        try:
            package = self.engine.generate([json.loads(path.read_text(encoding="utf-8")) for path in paths])
            existing_path = self.root / "recommendations" / package["recommendation_version"] / "recommendation_repository.json"
            if existing_path.exists(): return existing_path
            valid, errors = self.validator.validate(package, self.repository.existing_ids())
            if not valid: raise ValueError("RECOMMENDATION_VALIDATION_FAILED:" + ",".join(errors))
            return self.repository.save(package, {"validation_status": "VALID", "errors": []})
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            self.log.error("recommendation generation failed safely: %s", exc); raise
    def process_async(self) -> Future: return self._executor.submit(self.process_available)
    def shutdown(self): self._executor.shutdown(wait=True)
