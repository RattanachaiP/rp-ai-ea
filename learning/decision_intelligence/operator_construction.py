"""Explicit operator entrypoint for owner-engine PR184 construction."""

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from learning.decision_context import DecisionContextRepository
from learning.decision_context.exceptions import DecisionContextError

from .engine import GovernedDecisionIntelligenceEngine
from .exceptions import DecisionIntelligenceError
from .identity import canonical_bytes
from .repository import DecisionIntelligenceRepository


def construct_from_snapshot(
    *,
    context_repository_root="learning_data/decision_context",
    repository_root="learning_data/decision_intelligence",
    context_snapshot_uuid,
):
    """Construct PR184 through its owner from one exact canonical PR183 snapshot."""
    context_repository = DecisionContextRepository(context_repository_root)
    if not context_repository.root.is_dir():
        raise DecisionIntelligenceError("DECISION_CONTEXT_REPOSITORY_MISSING")
    try:
        matches = tuple(
            snapshot
            for snapshot in context_repository.snapshots()
            if snapshot.snapshot_uuid == context_snapshot_uuid
        )
    except (DecisionContextError, ValueError, OSError) as exc:
        raise DecisionIntelligenceError("BROKEN_PROVENANCE") from exc
    if len(matches) != 1:
        raise DecisionIntelligenceError("CONTEXT_SNAPSHOT_MISMATCH")

    engine = GovernedDecisionIntelligenceEngine(
        context_repository=context_repository,
        repository=DecisionIntelligenceRepository(repository_root),
    )
    return engine.construct_intelligence(matches[0])


def _parser():
    parser = argparse.ArgumentParser(
        description="Construct PR184 Decision Intelligence from one exact PR183 snapshot."
    )
    parser.add_argument(
        "--context-repository-root",
        type=Path,
        default=Path("learning_data/decision_context"),
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path("learning_data/decision_intelligence"),
    )
    parser.add_argument("--context-snapshot-uuid", required=True)
    parser.add_argument("--format", choices=("human", "json"), default="human")
    return parser


def main(argv: Optional[Sequence[str]] = None):
    arguments = _parser().parse_args(argv)
    try:
        report = construct_from_snapshot(
            context_repository_root=arguments.context_repository_root,
            repository_root=arguments.repository_root,
            context_snapshot_uuid=arguments.context_snapshot_uuid,
        )
    except DecisionIntelligenceError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    if arguments.format == "json":
        print(canonical_bytes(report.to_dict()).decode())
    else:
        print(f"REPORT {report.report_uuid}")
        print(f"SNAPSHOT {report.snapshot_uuid}")
        print(f"PROCESSED {report.processed_count}")
        print(f"PREPARED {report.prepared_count}")
        print("AUTHORITY ADVISORY_DECISION_INTELLIGENCE_ONLY")
    return report


if __name__ == "__main__":
    main()
