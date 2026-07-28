"""Explicit owner-controlled commit command for a canonical PR184 activation."""

import argparse
from pathlib import Path
from typing import Optional, Sequence

from .exceptions import DecisionIntelligenceError
from .models import ACTIVATION_AUTHORITY_OWNER
from .repository import DecisionIntelligenceRepository


def commit_activation(*, repository_root, intelligence_uuid, snapshot_uuid,
                      authority_owner, activated_at):
    """Validate and immutably bind the two exact operator-selected identities."""
    repository = DecisionIntelligenceRepository(repository_root)
    intelligences = tuple(
        item for item in repository.records()
        if item.intelligence_uuid == intelligence_uuid
    )
    snapshots = tuple(
        item for item in repository.snapshots()
        if item.snapshot_uuid == snapshot_uuid
    )
    if len(intelligences) != 1:
        raise DecisionIntelligenceError("DECISION_INTELLIGENCE_MISSING")
    if len(snapshots) != 1:
        raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")
    return repository.activate(
        intelligences[0], snapshots[0], authority_owner=authority_owner,
        activated_at=activated_at,
    )


def _parser():
    parser = argparse.ArgumentParser(
        description="Commit one explicit owner-governed PR184 production activation."
    )
    parser.add_argument("--repository-root", type=Path,
                        default=Path("learning_data/decision_intelligence"))
    parser.add_argument("--intelligence-uuid", required=True)
    parser.add_argument("--snapshot-uuid", required=True)
    parser.add_argument("--authority-owner", required=True,
                        help=f"must be {ACTIVATION_AUTHORITY_OWNER}")
    parser.add_argument("--activated-at", required=True,
                        help="explicit canonical UTC timestamp")
    return parser


def main(argv: Optional[Sequence[str]] = None):
    arguments = _parser().parse_args(argv)
    activation = commit_activation(
        repository_root=arguments.repository_root,
        intelligence_uuid=arguments.intelligence_uuid,
        snapshot_uuid=arguments.snapshot_uuid,
        authority_owner=arguments.authority_owner,
        activated_at=arguments.activated_at,
    )
    print(activation.activation_uuid)
    return activation


if __name__ == "__main__":
    main()
