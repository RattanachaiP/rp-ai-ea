from concurrent.futures import Future, ThreadPoolExecutor
import json, logging
from pathlib import Path
from .insight_engine import InsightEngine
from .insight_repository import InsightRepository

class InsightCoordinator:
    """Failure-isolated asynchronous processor of immutable Knowledge files."""
    def __init__(self, root, repository=None, engine=None):
        self.root, self.repository, self.engine = Path(root), repository or InsightRepository(root), engine or InsightEngine()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="raip-insight"); self.log = logging.getLogger(__name__)
    def process_available(self):
        paths = sorted((self.root / "knowledge").glob("*/knowledge.json"))
        if not paths: return None
        try: return self.repository.save(self.engine.generate(json.loads(paths[-1].read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError, ValueError) as exc: self.log.error("insight generation failed: %s", exc); raise
    def process_async(self) -> Future: return self._executor.submit(self.process_available)
    def shutdown(self): self._executor.shutdown(wait=True)
