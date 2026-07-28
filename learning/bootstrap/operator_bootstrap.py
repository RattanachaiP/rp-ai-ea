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
from learning.decision_intelligence.operator_inspection import inspect_repository
from runtime.production_startup import ProductionStartupConfiguration


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
    target_repo = _repository(base, stage)
    before_records = tuple(_read(target_repo, _STAGE[stage][2], stage))
    before_snapshots = tuple(_read(target_repo, "snapshots", stage))
    if stage == "pr180":
        report = RuntimeKnowledgeGate(source_repo, target_repo).prepare_advisory_package(source)
    elif stage == "pr181":
        report = RuntimeKnowledgeSelector(source_repo, target_repo).evaluate_eligibility(source)
    elif stage == "pr182":
        report = RuntimeConfidenceEvaluator(source_repo, target_repo).evaluate_confidence(source)
    elif stage == "pr183":
        report = GovernedDecisionContextEngine(source_repo, target_repo).construct_context(source)
    else:
        report = GovernedDecisionIntelligenceEngine(source_repo, target_repo).construct_intelligence(source)
    result_uuid = report.selection_snapshot_uuid if stage == "pr181" else report.snapshot_uuid
    result_digest = report.selection_snapshot_digest if stage == "pr181" else report.snapshot_digest
    matches = [item for item in _read(target_repo, "snapshots", stage)
               if item.snapshot_uuid == result_uuid and item.snapshot_digest == result_digest]
    if len(matches) != 1:
        raise BootstrapError(f"EXACT_RESULT_SNAPSHOT_NOT_FOUND stage={stage} mutation_occurred=true rerun_safe=true")
    after_records = tuple(_read(target_repo, _STAGE[stage][2], stage))
    after_snapshots = tuple(_read(target_repo, "snapshots", stage))
    new_record_ids = sorted(set(_ids(after_records, _STAGE[stage][4])) - set(_ids(before_records, _STAGE[stage][4])))
    new_snapshot_ids = sorted(set(_ids(after_snapshots, "snapshot_uuid")) - set(_ids(before_snapshots, "snapshot_uuid")))
    result_records = getattr(report, "runtime_packages", getattr(report, "runtime_selections",
                     getattr(report, "confidence_records", getattr(report, "decision_contexts",
                     getattr(report, "decision_intelligences", ())))))
    return {"mode": "CONSTRUCT", "stage": stage, "source_stage": upstream,
            "source_snapshot_uuid": source_uuid, "constructed_record_uuids": _ids(result_records, _STAGE[stage][4]),
            "result_snapshot_uuid": result_uuid, "result_snapshot_digest": result_digest,
            "new_record_uuids": new_record_ids, "new_snapshot_uuids": new_snapshot_ids,
            "duplicate_replay": not new_record_ids and not new_snapshot_ids,
            "mutation_occurred": bool(new_record_ids or new_snapshot_ids), "rerun_safe": True}


def _ids(values, field):
    return [getattr(item, field) for item in values]


def verify(base: Path, observations=None, captured_at=None) -> dict[str, Any]:
    state = inspect(base)
    missing = [x["stage"] for x in state["stages"] if not x["record_count"] or not x["snapshot_count"]]
    activation_status = "NOT_CHECKED"
    production_ready = False
    activated_pair = None
    if not missing:
        try:
            inspect_repository(base / "decision_intelligence")
            repository = DecisionIntelligenceRepository(base / "decision_intelligence")
            activations = repository.activations()
            if not activations:
                activation_status = "ACTIVATION_REQUIRED"
            else:
                activation = activations[0]
                activation_status = "VALID"
                activated_pair = {"intelligence_uuid": activation.intelligence_uuid,
                                  "snapshot_uuid": activation.snapshot_uuid}
                if observations is not None and captured_at is not None:
                    config = ProductionStartupConfiguration.from_canonical_repository(
                        observations=observations, captured_at=captured_at,
                        intelligence_root=repository.root)
                    production_ready = True
                    activated_pair = {"intelligence_uuid": config.decision_intelligence_uuid,
                                      "snapshot_uuid": config.decision_intelligence_snapshot_uuid}
        except Exception as exc:
            activation_status = f"INVALID:{type(exc).__name__}:{exc}"
    return {"mode": "VERIFY", "mutation_occurred": False, "learning_chain_ready": not missing,
            "missing_stages": missing, "pr184_repository_integrity": "VALID" if not missing and not activation_status.startswith("INVALID") else "NOT_VALID",
            "activation_status": activation_status, "activated_pair": activated_pair,
            "production_startup_prerequisites_ready": production_ready, "production_ready": production_ready,
            "blocked_before_activation": activation_status == "ACTIVATION_REQUIRED",
            "next_required_operator_action": state["next_required_operator_action"] if missing else ("production startup prerequisites verified" if production_ready else ("supply exact environment observations for startup verification" if activation_status == "VALID" else "inspect PR184, approve exact pair, and activate explicitly"))}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PR248 governed learning bootstrap")
    parser.add_argument("--base", default="learning_data")
    sub = parser.add_subparsers(dest="mode", required=True)
    for name in ("inspect", "plan"):
        p = sub.add_parser(name); p.add_argument("--json", action="store_true")
    p = sub.add_parser("verify"); p.add_argument("--json", action="store_true"); p.add_argument("--environment-observations-file"); p.add_argument("--captured-at")
    p = sub.add_parser("construct"); p.add_argument("--stage", required=True, choices=("pr180","pr181","pr182","pr183","pr184")); p.add_argument("--source-snapshot-uuid", required=True)
    args = parser.parse_args(argv); base = Path(args.base)
    try:
        if args.mode == "verify":
            if bool(args.environment_observations_file) != bool(args.captured_at):
                raise BootstrapError("ENVIRONMENT_OBSERVATIONS_AND_CAPTURED_AT_REQUIRED mutation_occurred=false rerun_safe=true")
            observations = None
            if args.environment_observations_file:
                try:
                    values = json.loads(Path(args.environment_observations_file).read_text(encoding="utf-8"))
                    observations = tuple((item[0], item[1]) for item in values)
                except (OSError, json.JSONDecodeError, TypeError, IndexError) as exc:
                    raise BootstrapError(
                        "INVALID_ENVIRONMENT_OBSERVATIONS mutation_occurred=false rerun_safe=true"
                    ) from exc
            result = verify(base, observations, args.captured_at)
        else:
            result = inspect(base) if args.mode == "inspect" else plan(base) if args.mode == "plan" else construct(base, args.stage, args.source_snapshot_uuid)
    except BootstrapError as exc:
        parser.exit(2, f"BOOTSTRAP_FAILED {exc}\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
