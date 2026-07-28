"""Read-only operator evidence for exact PR184 activation review.

This module deliberately has no dependency on the activation command and never
persists anything below the canonical repository root.
"""

import argparse
import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from learning.pattern_memory.models import valid_timestamp

from .exceptions import DecisionIntelligenceError
from .identity import canonical_bytes, digest
from .models import ACTIVATION_AUTHORITY_OWNER
from .repository import DecisionIntelligenceRepository

ELIGIBLE = "ELIGIBLE_FOR_OPERATOR_REVIEW"
NOT_ELIGIBLE = "NOT_ELIGIBLE_FOR_OPERATOR_REVIEW"


def _inside(path, root):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def inspect_repository(repository_root="learning_data/decision_intelligence"):
    """Return deterministic evidence for all records, snapshots, and exact pairs."""
    repository = DecisionIntelligenceRepository(repository_root)
    if not repository.root.is_dir():
        raise DecisionIntelligenceError("DECISION_INTELLIGENCE_REPOSITORY_MISSING")

    records = repository.records()
    snapshots = repository.snapshots()
    activations = repository.activations()
    if len(activations) > 1:
        raise DecisionIntelligenceError("AMBIGUOUS_DECISION_INTELLIGENCE_ACTIVATION_STATE")
    if activations:
        activation = activations[0]
        if (activation.authority_owner != ACTIVATION_AUTHORITY_OWNER
                or activation.activation_state != "READY"):
            raise DecisionIntelligenceError("AMBIGUOUS_DECISION_INTELLIGENCE_ACTIVATION_STATE")
        repository.exact(
            intelligence_uuid=activation.intelligence_uuid,
            intelligence_digest=activation.intelligence_digest,
            snapshot_uuid=activation.snapshot_uuid,
            snapshot_digest=activation.snapshot_digest,
            repository_digest=activation.repository_digest,
            intelligence_policy_uuid=activation.intelligence_policy_uuid,
            intelligence_policy_digest=activation.intelligence_policy_digest,
            intelligence_policy_version=activation.intelligence_policy_version,
            intelligence_engine_version=activation.intelligence_engine_version,
        )

    record_uuids = [item.intelligence_uuid for item in records]
    snapshot_uuids = [item.snapshot_uuid for item in snapshots]
    if len(record_uuids) != len(set(record_uuids)):
        raise DecisionIntelligenceError("DUPLICATE_DECISION_INTELLIGENCE_UUID")
    if len(snapshot_uuids) != len(set(snapshot_uuids)):
        raise DecisionIntelligenceError("DUPLICATE_INTELLIGENCE_SNAPSHOT_UUID")

    # This validates the complete chain, current repository identity, and all
    # policy/engine partitions without selecting a candidate for the operator.
    if snapshots:
        repository.latest_snapshot()
    elif records:
        raise DecisionIntelligenceError("INTELLIGENCE_SNAPSHOT_MISSING")

    record_evidence = []
    for item in records:
        record_evidence.append({
            "canonical_json_validation": "VALID",
            "canonical_record_path": str(repository.root / f"{item.intelligence_uuid}.json"),
            "intelligence_digest": item.intelligence_digest,
            "intelligence_engine_version": item.intelligence_engine_version,
            "intelligence_policy_digest": item.intelligence_policy_digest,
            "intelligence_policy_uuid": item.intelligence_policy_uuid,
            "intelligence_policy_version": item.intelligence_policy_version,
            "intelligence_state": item.intelligence_state,
            "intelligence_uuid": item.intelligence_uuid,
            "integrity_validation": "VALID",
            "repository_digest": repository.digest(),
            "source_context_identity": {
                "decision_context_digest": item.decision_context_digest,
                "decision_context_repository_digest": item.decision_context_repository_digest,
                "decision_context_snapshot_digest": item.decision_context_snapshot_digest,
                "decision_context_snapshot_uuid": item.decision_context_snapshot_uuid,
                "decision_context_uuid": item.decision_context_uuid,
            },
        })

    snapshot_evidence = []
    record_identities = set(repository.identities())
    for item in snapshots:
        internal_digest = digest([list(identity) for identity in item.intelligence_identities])
        snapshot_evidence.append({
            "canonical_snapshot_path": str(repository.snapshot_root / f"{item.snapshot_uuid}.json"),
            "chain_validation": "VALID",
            "engine_identity": {"intelligence_engine_version": item.intelligence_engine_version},
            "intelligence_identity_membership": [list(value) for value in item.intelligence_identities],
            "integrity_validation": "VALID" if item.repository_digest == internal_digest else "INVALID",
            "policy_identity": {
                "intelligence_policy_digest": item.intelligence_policy_digest,
                "intelligence_policy_uuid": item.intelligence_policy_uuid,
                "intelligence_policy_version": item.intelligence_policy_version,
            },
            "previous_snapshot_identity": {
                "snapshot_digest": item.previous_snapshot_digest,
                "snapshot_uuid": item.previous_snapshot_uuid,
            },
            "repository_digest": item.repository_digest,
            "snapshot_digest": item.snapshot_digest,
            "snapshot_uuid": item.snapshot_uuid,
        })
        if item.repository_digest != internal_digest:
            raise DecisionIntelligenceError("REPOSITORY_DIGEST_MISMATCH")
        if not set(item.intelligence_identities).issubset(record_identities):
            raise DecisionIntelligenceError("INTELLIGENCE_ABSENT_FROM_SNAPSHOT_REPOSITORY")

    pairs = []
    for intelligence in records:
        for snapshot in snapshots:
            membership = (intelligence.intelligence_uuid, intelligence.intelligence_digest) in snapshot.intelligence_identities
            repository_agreement = snapshot.repository_digest == digest(
                [list(value) for value in snapshot.intelligence_identities]
            )
            policy = (
                intelligence.intelligence_policy_uuid,
                intelligence.intelligence_policy_digest,
                intelligence.intelligence_policy_version,
            ) == (
                snapshot.intelligence_policy_uuid,
                snapshot.intelligence_policy_digest,
                snapshot.intelligence_policy_version,
            )
            engine = intelligence.intelligence_engine_version == snapshot.intelligence_engine_version
            lineage = membership and repository_agreement and policy and engine
            eligible = lineage and intelligence.intelligence_state == "DECISION_INTELLIGENCE_READY"
            pairs.append({
                "activation_eligibility_evidence": ELIGIBLE if eligible else NOT_ELIGIBLE,
                "complete_lineage_validity": lineage,
                "engine_compatibility": engine,
                "intelligence_membership_in_snapshot": membership,
                "intelligence_state": intelligence.intelligence_state,
                "intelligence_uuid": intelligence.intelligence_uuid,
                "policy_compatibility": policy,
                "repository_digest_agreement": repository_agreement,
                "snapshot_uuid": snapshot.snapshot_uuid,
            })

    return {
        "authority_notice": "INSPECTION_EVIDENCE_IS_NOT_APPROVAL_OR_ACTIVATION_AUTHORITY",
        "decision_intelligences": record_evidence,
        "exact_pairs": pairs,
        "repository_root": str(repository.root),
        "snapshots": snapshot_evidence,
        "status": "VALID" if records else "NO_DECISION_INTELLIGENCE_RECORDS",
    }


def _selected(report, intelligence_uuid, snapshot_uuid):
    matches = [pair for pair in report["exact_pairs"] if pair["intelligence_uuid"] == intelligence_uuid and pair["snapshot_uuid"] == snapshot_uuid]
    if len(matches) != 1:
        raise DecisionIntelligenceError("EXACT_INTELLIGENCE_SNAPSHOT_PAIR_NOT_FOUND")
    if not matches[0]["complete_lineage_validity"]:
        raise DecisionIntelligenceError("EXACT_INTELLIGENCE_SNAPSHOT_LINEAGE_INVALID")
    intelligence = next(value for value in report["decision_intelligences"] if value["intelligence_uuid"] == intelligence_uuid)
    snapshot = next(value for value in report["snapshots"] if value["snapshot_uuid"] == snapshot_uuid)
    return matches[0], intelligence, snapshot


def approval_request(report, intelligence_uuid, snapshot_uuid, generated_at=None):
    pair, intelligence, snapshot = _selected(report, intelligence_uuid, snapshot_uuid)
    return {
        "authority_required": ACTIVATION_AUTHORITY_OWNER,
        "complete_validation_result": pair,
        "engine_version": intelligence["intelligence_engine_version"],
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "intelligence_digest": intelligence["intelligence_digest"],
        "intelligence_uuid": intelligence_uuid,
        "policy_digest": intelligence["intelligence_policy_digest"],
        "policy_uuid": intelligence["intelligence_policy_uuid"],
        "policy_version": intelligence["intelligence_policy_version"],
        "repository_digest": snapshot["repository_digest"],
        "snapshot_digest": snapshot["snapshot_digest"],
        "snapshot_uuid": snapshot_uuid,
        "status": "PENDING_OPERATOR_APPROVAL",
    }


def activation_command(report, intelligence_uuid, snapshot_uuid, approved_at):
    _selected(report, intelligence_uuid, snapshot_uuid)
    if not valid_timestamp(approved_at):
        raise DecisionIntelligenceError("EXPLICIT_APPROVED_AT_REQUIRED")
    values = ["python", "-m", "learning.decision_intelligence.operator_activation",
              "--intelligence-uuid", intelligence_uuid, "--snapshot-uuid", snapshot_uuid,
              "--authority-owner", ACTIVATION_AUTHORITY_OWNER, "--activated-at", approved_at]
    return " ".join(shlex.quote(value) for value in values)


def _parser():
    parser = argparse.ArgumentParser(description="Read-only PR184 operator inspection and approval evidence.")
    parser.add_argument("--repository-root", type=Path, default=Path("learning_data/decision_intelligence"))
    parser.add_argument("--format", choices=("human", "json"), default="human")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--intelligence-uuid")
    parser.add_argument("--snapshot-uuid")
    parser.add_argument("--approval-request-output", type=Path)
    parser.add_argument("--approved-at")
    parser.add_argument("--print-activation-command", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None):
    args = _parser().parse_args(argv)
    try:
        if bool(args.intelligence_uuid) != bool(args.snapshot_uuid):
            raise DecisionIntelligenceError("EXACT_PAIR_IDENTITIES_REQUIRED")
        if args.approval_request_output and not args.intelligence_uuid:
            raise DecisionIntelligenceError("EXACT_PAIR_IDENTITIES_REQUIRED")
        if args.print_activation_command and (not args.intelligence_uuid or not args.approved_at):
            raise DecisionIntelligenceError("EXPLICIT_APPROVED_AT_REQUIRED")
        report = inspect_repository(args.repository_root)
        rendered = canonical_bytes(report).decode() if args.format == "json" else _human(report)
        if args.output:
            if _inside(args.output, args.repository_root):
                raise DecisionIntelligenceError("OUTPUT_INSIDE_CANONICAL_REPOSITORY")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + ("\n" if not rendered.endswith("\n") else ""))
        else:
            print(rendered)
        if args.approval_request_output:
            if _inside(args.approval_request_output, args.repository_root):
                raise DecisionIntelligenceError("OUTPUT_INSIDE_CANONICAL_REPOSITORY")
            request = approval_request(report, args.intelligence_uuid, args.snapshot_uuid)
            args.approval_request_output.parent.mkdir(parents=True, exist_ok=True)
            args.approval_request_output.write_bytes(canonical_bytes(request))
        if args.print_activation_command:
            print(activation_command(report, args.intelligence_uuid, args.snapshot_uuid, args.approved_at))
        return report
    except DecisionIntelligenceError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


def _human(report):
    lines = [report["authority_notice"], f"STATUS: {report['status']}"]
    for item in report["decision_intelligences"]:
        lines.append(f"INTELLIGENCE {item['intelligence_uuid']} {item['intelligence_state']} {item['intelligence_digest']}")
    for item in report["snapshots"]:
        lines.append(f"SNAPSHOT {item['snapshot_uuid']} {item['snapshot_digest']}")
    for pair in report["exact_pairs"]:
        lines.append(f"PAIR {pair['intelligence_uuid']} {pair['snapshot_uuid']} {pair['activation_eligibility_evidence']}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
