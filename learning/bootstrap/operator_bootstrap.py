"""PR248 read-only audit and exact-snapshot construction orchestration.

This module never creates source evidence, approvals, or activations.  Canonical
writes are delegated to the engine that owns the selected lifecycle stage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from learning.knowledge_registry import KnowledgeRegistryRepository
from learning.runtime_knowledge import RuntimeKnowledgeGate, RuntimeKnowledgeRepository
from learning.runtime_selection import RuntimeKnowledgeSelectionRepository, RuntimeKnowledgeSelector
from learning.runtime_confidence import RuntimeConfidenceEvaluator, RuntimeConfidenceRepository
from learning.decision_context import DecisionContextRepository, GovernedDecisionContextEngine
from learning.decision_intelligence import DecisionIntelligenceRepository, GovernedDecisionIntelligenceEngine


class BootstrapError(RuntimeError):
    """Stable fail-closed operator diagnostic."""


_STAGE = {
    "pr179": ("knowledge_registry", KnowledgeRegistryRepository, "records", "snapshots", "registry_uuid", "snapshot_uuid"),
    "pr180": ("runtime_knowledge", RuntimeKnowledgeRepository, "packages", "snapshots", "runtime_package_uuid", "snapshot_uuid"),
    "pr181": ("runtime_selection", RuntimeKnowledgeSelectionRepository, "selections", "snapshots", "selection_uuid", "snapshot_uuid"),
    "pr182": ("runtime_confidence", RuntimeConfidenceRepository, "records", "snapshots", "confidence_uuid", "snapshot_uuid"),
    "pr183": ("decision_context", DecisionContextRepository, "records", "snapshots", "context_uuid", "snapshot_uuid"),
    "pr184": ("decision_intelligence", DecisionIntelligenceRepository, "records", "snapshots", "intelligence_uuid", "snapshot_uuid"),
}
_ORDER = tuple(_STAGE)


def _repository(base: Path, stage: str):
    name, cls, *_ = _STAGE[stage]
    return cls(base / name)


def _read(repo: Any, method: str, stage: str):
    try:
        return getattr(repo, method)()
    except Exception as exc:
        raise BootstrapError(
            f"PROVENANCE_VERIFICATION_FAILED stage={stage} mutation_occurred=false "
            f"rerun_safe=true detail={type(exc).__name__}:{exc}"
        ) from exc


def inspect(base: Path) -> dict[str, Any]:
    """Return deterministic evidence only; it neither selects nor mutates."""
    stages = []
    for stage, (name, _, records_method, snapshots_method, record_id, snapshot_id) in _STAGE.items():
        root = base / name
        repo = _repository(base, stage)
        records = _read(repo, records_method, stage)
        snapshots = _read(repo, snapshots_method, stage)
        stages.append({
            "stage": stage, "repository": str(root), "repository_exists": root.is_dir(),
            "record_count": len(records), "snapshot_count": len(snapshots),
            "record_identities": [getattr(x, record_id) for x in records],
            "snapshot_identities": [getattr(x, snapshot_id) for x in snapshots],
            "missing_dependency": None if records and snapshots else ("EXTERNAL_APPROVED_PR173_PR175_EVIDENCE" if stage == "pr179" else _ORDER[_ORDER.index(stage)-1]),
        })
    first = next((x for x in stages if not x["record_count"] or not x["snapshot_count"]), None)
    return {"mode": "INSPECT", "mutation_occurred": False, "stages": stages,
            "next_required_operator_action": _action(first["stage"]) if first else "review PR184 and approve explicitly"}


def _action(stage: str) -> str:
    if stage == "pr179":
        return "acquire governed external outcome evidence and approved PR175 evidence; run PR173-PR179 owner workflow"
    previous = _ORDER[_ORDER.index(stage)-1]
    return f"inspect {previous}; then construct {stage} with one real exact {previous} snapshot UUID"


def plan(base: Path) -> dict[str, Any]:
    state = inspect(base)
    return {"mode": "PLAN", "mutation_occurred": False, "current_state": state["stages"],
            "lifecycle_order": list(_ORDER), "genesis": "operator-supplied immutable outcome evidence (PR173)",
            "commands": ["python -m learning.bootstrap.operator_bootstrap inspect --json",
                         "python -m learning.bootstrap.operator_bootstrap construct --stage pr180 --source-snapshot-uuid $SnapshotUuid",
                         "python -m learning.bootstrap.operator_bootstrap verify --json"],
            "activation_prerequisites": ["one exact READY PR184 intelligence/snapshot pair", "explicit human UTC approval timestamp", "explicit owner activation command"],
            "next_required_operator_action": state["next_required_operator_action"]}


def _exact_snapshot(repo: Any, uuid: str, stage: str):
    snapshots = _read(repo, "snapshots", stage)
    matches = [item for item in snapshots if item.snapshot_uuid == uuid]
    if len(matches) != 1:
        code = "UPSTREAM_SNAPSHOT_REQUIRED" if not matches else "AMBIGUOUS_UPSTREAM_SNAPSHOT"
        raise BootstrapError(f"{code} stage={stage} required_upstream_source={uuid} mutation_occurred=false rerun_safe=true")
    return matches[0]


def construct(base: Path, stage: str, source_uuid: str) -> dict[str, Any]:
    """Construct one stage from one operator-supplied exact upstream snapshot."""
    if stage not in ("pr180", "pr181", "pr182", "pr183", "pr184"):
        raise BootstrapError("UNSUPPORTED_CONSTRUCTION_STAGE mutation_occurred=false rerun_safe=true")
    upstream = _ORDER[_ORDER.index(stage)-1]
    source_repo = _repository(base, upstream)
    source = _exact_snapshot(source_repo, source_uuid, upstream)
    if stage == "pr180":
        # PR180 accepts registry records/reports (not snapshots).  The exact
        # operator-selected snapshot is therefore resolved to every identity it
        # binds, and only those canonical records are passed to the owner.
        records = {item.registry_uuid: item for item in _read(source_repo, "records", upstream)}
        selected = []
        for identity, content_digest in source.record_identities:
            item = records.get(identity)
            if item is None or item.registry_digest != content_digest:
                raise BootstrapError(
                    f"PROVENANCE_VERIFICATION_FAILED stage=pr179 required_upstream_source={source_uuid} "
                    "mutation_occurred=false rerun_safe=true"
                )
            selected.append(item)
        if not selected:
            raise BootstrapError("UPSTREAM_SNAPSHOT_REQUIRED stage=pr179 mutation_occurred=false rerun_safe=true")
        engine = RuntimeKnowledgeGate(source_repo, _repository(base, stage))
        for item in selected:
            report = engine.prepare_advisory_package(item)
    elif stage == "pr181":
        report = RuntimeKnowledgeSelector(source_repo, _repository(base, stage)).evaluate_eligibility(source)
    elif stage == "pr182":
        report = RuntimeConfidenceEvaluator(source_repo, _repository(base, stage)).evaluate_confidence(source)
    elif stage == "pr183":
        report = GovernedDecisionContextEngine(source_repo, _repository(base, stage)).construct_context(source)
    else:
        report = GovernedDecisionIntelligenceEngine(source_repo, _repository(base, stage)).construct_intelligence(source)
    result_snapshot = _read(_repository(base, stage), "snapshots", stage)
    matching_result = result_snapshot[-1] if result_snapshot else None
    if matching_result is None:
        raise BootstrapError(f"PROVENANCE_VERIFICATION_FAILED stage={stage} mutation_occurred=true rerun_safe=true")
    return {"mode": "CONSTRUCT", "stage": stage, "source_stage": upstream,
            "source_snapshot_uuid": source_uuid, "result_snapshot_uuid": matching_result.snapshot_uuid,
            "mutation_occurred": True, "rerun_safe": True}


def verify(base: Path) -> dict[str, Any]:
    state = inspect(base)
    missing = [x["stage"] for x in state["stages"] if not x["record_count"] or not x["snapshot_count"]]
    return {"mode": "VERIFY", "mutation_occurred": False, "chain_valid": not missing,
            "missing_stages": missing, "activation_checked_separately": True,
            "production_ready": False,
            "next_required_operator_action": state["next_required_operator_action"] if missing else "run read-only PR184 inspection, human approval, explicit activation, then production startup"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PR248 governed learning bootstrap")
    parser.add_argument("--base", default="learning_data")
    sub = parser.add_subparsers(dest="mode", required=True)
    for name in ("inspect", "plan", "verify"):
        p = sub.add_parser(name); p.add_argument("--json", action="store_true")
    p = sub.add_parser("construct"); p.add_argument("--stage", required=True, choices=("pr180","pr181","pr182","pr183","pr184")); p.add_argument("--source-snapshot-uuid", required=True)
    args = parser.parse_args(argv); base = Path(args.base)
    try:
        result = inspect(base) if args.mode == "inspect" else plan(base) if args.mode == "plan" else verify(base) if args.mode == "verify" else construct(base, args.stage, args.source_snapshot_uuid)
    except BootstrapError as exc:
        parser.exit(2, f"BOOTSTRAP_FAILED {exc}\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
