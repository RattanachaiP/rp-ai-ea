"""Offline command entry point; no runtime, broker, or network dependency."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from learning.knowledge.reader import KnowledgeReader
from learning.knowledge.repository import KnowledgeRepository
from .engine import KnowledgeAnalyticsEngine
from .repository import AnalyticsRepository

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge-path", default="learning_data")
    parser.add_argument("--analytics-path", default="learning_data")
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--report-json")
    args = parser.parse_args()
    knowledge_path, analytics_path = Path(args.knowledge_path).expanduser().resolve(), Path(args.analytics_path).expanduser().resolve()
    if not args.no_persist and knowledge_path == analytics_path:
        parser.error("--knowledge-path and --analytics-path must be separate roots")
    if args.report_json and Path(args.report_json).expanduser().resolve().parent == knowledge_path / "knowledge":
        parser.error("--report-json must not be written into the knowledge repository")
    try:
        repository = None if args.no_persist else AnalyticsRepository(analytics_path)
        report = KnowledgeAnalyticsEngine(KnowledgeReader(KnowledgeRepository(knowledge_path)), repository).analyze()
        payload = json.dumps(report.to_dict(), sort_keys=True, indent=2, allow_nan=False)
        if args.report_json:
            output = Path(args.report_json).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload + "\n", encoding="utf-8")
        else: print(payload)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"knowledge analytics failed: {type(error).__name__}: {error}\n")
if __name__ == "__main__": main()
