"""Deterministic, read-only historical validation for executive decision packages.

This module has deliberately no imports from runtime, writer, executor, broker, or learning
code.  It accepts historical snapshots supplied by RAIP storage and writes only below the
``simulation/`` root supplied to the coordinator.
"""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
from typing import Mapping, Sequence

SCHEMA_VERSION = "9.0.0"
PRODUCER = "RAIP Simulation & Validation Domain"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _write_once(path: Path, document: Mapping[str, object]) -> Path:
    """Atomically create a document without replacing an existing validation record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write((json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _number(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _snapshot_id(snapshot: Mapping[str, object], ordinal: int) -> str:
    return str(snapshot.get("snapshot_id") or snapshot.get("trade_id") or "snapshot-" + str(ordinal))


def _require_executive_compatibility(package: Mapping[str, object]) -> None:
    """Reject unknown executive contracts rather than guessing their semantics."""
    version = str(package.get("schema_version", ""))
    if version.split(".", 1)[0] != "7":
        raise ValueError("INCOMPATIBLE_EXECUTIVE_PACKAGE_SCHEMA")


class HistoricalReplayEngine:
    """Replays supplied snapshots in a stable order; it never accesses live market data."""
    def replay(self, executive_package: Mapping[str, object], snapshots: Sequence[Mapping[str, object]]) -> dict[str, object]:
        _require_executive_compatibility(executive_package)
        decision_id = str(executive_package.get("decision_id", ""))
        ordered = sorted((dict(item) for item in snapshots if isinstance(item, Mapping)), key=lambda item: _snapshot_id(item, 0))
        records = []
        for ordinal, snapshot in enumerate(ordered):
            outcome = snapshot.get("outcome", {}) if isinstance(snapshot.get("outcome"), Mapping) else {}
            quality = snapshot.get("data_quality", {}) if isinstance(snapshot.get("data_quality"), Mapping) else {}
            records.append({"snapshot_id": _snapshot_id(snapshot, ordinal), "net_profit": _number(outcome.get("net_profit")), "profit_points": _number(outcome.get("profit_points")), "r_multiple": _number(outcome.get("r_multiple")), "completeness_ratio": _number(quality.get("completeness_ratio", 1.0)), "market_context": dict(snapshot.get("market_context", {})) if isinstance(snapshot.get("market_context"), Mapping) else {}})
        net_profit = sum(item["net_profit"] for item in records)
        return {"schema_version": SCHEMA_VERSION, "producer": PRODUCER, "document_type": "historical_replay", "decision_id": decision_id, "historical_snapshot_ids": [item["snapshot_id"] for item in records], "replayed_observations": records, "replay_summary": {"observation_count": len(records), "net_profit": net_profit, "average_r_multiple": sum(item["r_multiple"] for item in records) / len(records) if records else 0.0, "complete_observation_count": sum(item["completeness_ratio"] >= 1.0 for item in records)}, "evidence_lineage": {"decision_id": decision_id, "evidence_ids": sorted(str(item) for item in executive_package.get("evidence_lineage", {}).get("evidence_ids", [])) if isinstance(executive_package.get("evidence_lineage"), Mapping) else [], "snapshot_ids": [item["snapshot_id"] for item in records]}}


class ScenarioGenerator:
    """Classifies historical observations using declared fields only, with stable coverage."""
    def generate(self, replay: Mapping[str, object]) -> dict[str, object]:
        buckets = {name: [] for name in ("TRENDING_MARKET", "RANGE_MARKET", "VOLATILE_SESSION", "LOW_LIQUIDITY")}
        for item in replay.get("replayed_observations", []):
            context = item.get("market_context", {}) if isinstance(item, Mapping) else {}
            text = " ".join(str(context.get(key, "")).upper() for key in ("regime", "market_mode", "liquidity", "session"))
            snapshot_id = str(item.get("snapshot_id"))
            if "TREND" in text: buckets["TRENDING_MARKET"].append(snapshot_id)
            if "RANGE" in text: buckets["RANGE_MARKET"].append(snapshot_id)
            if "VOLAT" in text: buckets["VOLATILE_SESSION"].append(snapshot_id)
            if "LOW_LIQUID" in text or "ILLIQUID" in text: buckets["LOW_LIQUIDITY"].append(snapshot_id)
        scenarios = [{"scenario_type": name, "snapshot_ids": ids, "observation_count": len(ids)} for name, ids in buckets.items()]
        return {"schema_version": SCHEMA_VERSION, "producer": PRODUCER, "document_type": "scenario_summary", "decision_id": replay.get("decision_id"), "scenario_generation_basis": "historical_snapshot_market_context_only", "scenarios": scenarios, "scenario_coverage": {"covered_observations": len(set(identifier for ids in buckets.values() for identifier in ids)), "replayed_observations": len(replay.get("replayed_observations", []))}}


class CounterfactualAnalyzer:
    """Applies only explicitly declared historical deltas; it does not forecast markets."""
    def analyze(self, executive_package: Mapping[str, object], replay: Mapping[str, object], scenarios: Mapping[str, object]) -> dict[str, object]:
        impacts = [row.get("estimated_impact", {}) for row in executive_package.get("supporting_recommendations", []) if isinstance(row, Mapping) and isinstance(row.get("estimated_impact"), Mapping)]
        profit_delta = sum(_number(impact.get("historical_net_profit_delta")) for impact in impacts)
        r_delta = sum(_number(impact.get("historical_r_multiple_delta")) for impact in impacts)
        count = int(replay.get("replay_summary", {}).get("observation_count", 0))
        complete = int(replay.get("replay_summary", {}).get("complete_observation_count", 0))
        confidence = round((complete / count if count else 0.0) * min(count / 20.0, 1.0), 6)
        observed = _number(replay.get("replay_summary", {}).get("net_profit"))
        return {"schema_version": SCHEMA_VERSION, "producer": PRODUCER, "document_type": "counterfactual_analysis", "decision_id": replay.get("decision_id"), "simulated_outcome": {"historical_net_profit": observed + profit_delta, "historical_net_profit_delta": profit_delta, "historical_average_r_multiple": _number(replay.get("replay_summary", {}).get("average_r_multiple")) + r_delta}, "confidence": confidence, "assumptions": ["Historical snapshots are complete only where completeness_ratio is 1.0.", "Only explicit estimated_impact historical_*_delta values are applied.", "No live-market data, prediction, trading action, or learning update is performed."], "observed_historical_outcome": {"net_profit": observed}, "scenario_coverage": scenarios.get("scenario_coverage", {})}


class ValidationReportBuilder:
    def build(self, replay: Mapping[str, object], scenarios: Mapping[str, object], counterfactual: Mapping[str, object]) -> dict[str, object]:
        observed = _number(counterfactual.get("observed_historical_outcome", {}).get("net_profit"))
        simulated = _number(counterfactual.get("simulated_outcome", {}).get("historical_net_profit"))
        delta = simulated - observed
        quality = "SUPPORTED" if counterfactual.get("confidence", 0) > 0 and replay.get("evidence_lineage", {}).get("evidence_ids") else "INSUFFICIENT_EVIDENCE"
        return {"schema_version": SCHEMA_VERSION, "producer": PRODUCER, "document_type": "validation_report", "decision_id": replay.get("decision_id"), "scenario_coverage": scenarios.get("scenario_coverage", {}), "replay_consistency": {"deterministic_replay": True, "observation_count": replay.get("replay_summary", {}).get("observation_count", 0)}, "expected_impact": counterfactual.get("simulated_outcome", {}), "observed_historical_outcome": counterfactual.get("observed_historical_outcome", {}), "variance_summary": {"historical_net_profit_variance": delta}, "recommendation_quality": {"status": quality, "confidence": counterfactual.get("confidence", 0)}, "evidence_lineage": replay.get("evidence_lineage", {}), "assumptions": counterfactual.get("assumptions", [])}


class ValidationRepository:
    """Immutable append-only storage indexed by deterministic validation execution ID."""
    def __init__(self, root: Path | str): self.root = Path(root)
    def save(self, report: Mapping[str, object]) -> Path:
        validation_id = _digest({"decision_id": report.get("decision_id"), "report": report})
        document = {"schema_version": SCHEMA_VERSION, "producer": PRODUCER, "document_type": "validation_repository", "validation_id": validation_id, "validation_report": dict(report)}
        return _write_once(self.root / "simulation" / "validation_repository" / validation_id / "validation_repository.json", document)


class SimulationCoordinator:
    """Asynchronous orchestration isolated from all runtime and learning paths."""
    def __init__(self, root: Path | str):
        self.root = Path(root); self.replay = HistoricalReplayEngine(); self.scenarios = ScenarioGenerator(); self.counterfactuals = CounterfactualAnalyzer(); self.reports = ValidationReportBuilder(); self.repository = ValidationRepository(self.root); self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="raip-simulation"); self.log = logging.getLogger(__name__)
    def validate(self, executive_package: Mapping[str, object], snapshots: Sequence[Mapping[str, object]]) -> Path:
        replay = self.replay.replay(executive_package, snapshots); scenario = self.scenarios.generate(replay); analysis = self.counterfactuals.analyze(executive_package, replay, scenario); report = self.reports.build(replay, scenario, analysis)
        execution_id = _digest({"decision_id": replay["decision_id"], "replay": replay})
        base = self.root / "simulation"
        _write_once(base / "historical_replay" / execution_id / "historical_replay.json", replay)
        _write_once(base / "historical_replay" / execution_id / "replay_summary.json", {"schema_version": SCHEMA_VERSION, "producer": PRODUCER, "document_type": "replay_summary", "decision_id": replay["decision_id"], "replay_summary": replay["replay_summary"], "evidence_lineage": replay["evidence_lineage"]})
        _write_once(base / "validation" / execution_id / "scenario_summary.json", scenario)
        _write_once(base / "validation" / execution_id / "validation_report.json", report)
        return self.repository.save(report)
    def validate_async(self, executive_package: Mapping[str, object], snapshots: Sequence[Mapping[str, object]]) -> Future:
        return self._executor.submit(self.validate, executive_package, snapshots)
    def shutdown(self) -> None: self._executor.shutdown(wait=True)
