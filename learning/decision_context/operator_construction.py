"""Explicit operator entrypoint for owner-engine PR183 construction."""

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from learning.runtime_confidence import RuntimeConfidenceRepository
from learning.runtime_confidence.exceptions import RuntimeConfidenceError

from .engine import GovernedDecisionContextEngine
from .exceptions import DecisionContextError
from .identity import canonical_bytes
from .repository import DecisionContextRepository


def construct_from_snapshot(
    *,
    confidence_repository_root="learning_data/runtime_confidence",
    repository_root="learning_data/decision_context",
    confidence_snapshot_uuid,
):
    """Construct PR183 through its owner from one exact canonical PR182 snapshot."""
    confidence_repository = RuntimeConfidenceRepository(confidence_repository_root)
    if not confidence_repository.root.is_dir():
        raise DecisionContextError("CONFIDENCE_REPOSITORY_MISSING")
    try:
        matches = tuple(
            snapshot
            for snapshot in confidence_repository.snapshots()
            if snapshot.snapshot_uuid == confidence_snapshot_uuid
        )
    except (RuntimeConfidenceError, ValueError, OSError) as exc:
        raise DecisionContextError("BROKEN_PROVENANCE") from exc
    if len(matches) != 1:
        raise DecisionContextError("CONFIDENCE_SNAPSHOT_MISMATCH")

    engine = GovernedDecisionContextEngine(
        confidence_repository=confidence_repository,
        repository=DecisionContextRepository(repository_root),
    )
    return engine.construct_context(matches[0])


def _parser():
    parser = argparse.ArgumentParser(
        description="Construct PR183 Decision Context from one exact PR182 snapshot."
    )
    parser.add_argument(
        "--confidence-repository-root",
        type=Path,
        default=Path("learning_data/runtime_confidence"),
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path("learning_data/decision_context"),
    )
    parser.add_argument("--confidence-snapshot-uuid", required=True)
    parser.add_argument("--format", choices=("human", "json"), default="human")
    return parser


def main(argv: Optional[Sequence[str]] = None):
    arguments = _parser().parse_args(argv)
    try:
        report = construct_from_snapshot(
            confidence_repository_root=arguments.confidence_repository_root,
            repository_root=arguments.repository_root,
            confidence_snapshot_uuid=arguments.confidence_snapshot_uuid,
        )
    except DecisionContextError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    if arguments.format == "json":
        print(canonical_bytes(report.to_dict()).decode())
    else:
        print(f"REPORT {report.report_uuid}")
        print(f"SNAPSHOT {report.snapshot_uuid}")
        print(f"PROCESSED {report.processed_count}")
        print(f"PREPARED {report.prepared_count}")
        print("AUTHORITY ADVISORY_DECISION_CONTEXT_ONLY")
    return report


if __name__ == "__main__":
    main()
