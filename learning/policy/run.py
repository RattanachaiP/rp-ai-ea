"""Offline CLI for evaluating JSON knowledge snapshots."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .engine import KnowledgePolicyEngine
from .models import PolicyConfig
from .repository import PolicyEvaluationRepository


def _load(path: str | None):
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"INVALID_JSON_INPUT:{path}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate knowledge eligibility offline")
    parser.add_argument("knowledge")
    parser.add_argument("--governance")
    parser.add_argument("--analytics")
    parser.add_argument("--config")
    parser.add_argument("--lifecycle-state")
    parser.add_argument("--timestamp")
    parser.add_argument("--source-baseline", required=True)
    parser.add_argument("--root", default="learning_data")
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    try:
        engine = KnowledgePolicyEngine(
            PolicyConfig(**(_load(args.config) or {})),
            source_baseline=args.source_baseline,
        )
        report = engine.evaluate(
            _load(args.knowledge),
            governance=_load(args.governance),
            analytics=_load(args.analytics),
            lifecycle_state=args.lifecycle_state,
            evaluation_timestamp=args.timestamp,
        )
        if args.persist:
            PolicyEvaluationRepository(args.root).save(report)
        print(json.dumps(report.to_dict(), sort_keys=True, allow_nan=False))
        return 0
    except (TypeError, ValueError, FileExistsError) as exc:
        print(f"POLICY_EVALUATION_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
