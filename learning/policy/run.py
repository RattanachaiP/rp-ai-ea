"""Offline CLI for evaluating JSON knowledge snapshots."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from .engine import KnowledgePolicyEngine
from .models import PolicyConfig
from .repository import PolicyEvaluationRepository
def main():
    parser=argparse.ArgumentParser(description="Evaluate knowledge eligibility offline")
    parser.add_argument("knowledge"); parser.add_argument("--governance"); parser.add_argument("--analytics"); parser.add_argument("--config"); parser.add_argument("--lifecycle-state"); parser.add_argument("--timestamp"); parser.add_argument("--source-baseline", required=True); parser.add_argument("--root", default="learning_data"); parser.add_argument("--persist", action="store_true")
    args=parser.parse_args(); load=lambda value: json.loads(Path(value).read_text()) if value else None
    engine=KnowledgePolicyEngine(PolicyConfig(**(load(args.config) or {})), source_baseline=args.source_baseline)
    report=engine.evaluate(load(args.knowledge), governance=load(args.governance), analytics=load(args.analytics), lifecycle_state=args.lifecycle_state, evaluation_timestamp=args.timestamp)
    if args.persist: PolicyEvaluationRepository(args.root).save(report)
    print(json.dumps(report.to_dict(), sort_keys=True))
if __name__ == "__main__": main()
