"""Passive, deterministic Executive Decision Intelligence Domain.

This domain consumes only validated recommendation repositories and governance reports.
It deliberately has no dependency on the trading runtime and cannot alter its inputs.
"""
from __future__ import annotations
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
from typing import Callable, Mapping, Sequence

SCHEMA_VERSION = "7.0.0"
GOVERNANCE_VERSION = "6.0.0"
BASELINE_COMMIT = "84769de"
PRIORITY_WEIGHT = {"CRITICAL": 500, "HIGH": 400, "MEDIUM": 300, "LOW": 200, "INFORMATION": 100}


def _iso(clock: Callable[[], datetime]) -> str:
    return clock().astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _metadata(clock: Callable[[], datetime], producer: str) -> dict[str, object]:
    return {"schema_version": SCHEMA_VERSION, "producer": producer, "owner": "RAIP Executive Decision Intelligence Domain", "created_at": _iso(clock), "governance_version": GOVERNANCE_VERSION, "baseline_commit": BASELINE_COMMIT}


def _atomic_replace(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(document, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
    with temporary.open("wb") as handle:
        handle.write(payload); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


class DecisionCandidateAggregator:
    """Groups recommendations by their stable business issue category."""
    def aggregate(self, recommendations: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
        grouped: dict[str, list[Mapping[str, object]]] = {}
        for recommendation in recommendations:
            if recommendation.get("validation_status") != "VALID":
                continue
            issue = str(recommendation.get("category") or recommendation.get("summary") or "UNCLASSIFIED")
            grouped.setdefault(issue, []).append(recommendation)
        candidates = []
        for issue, rows in sorted(grouped.items()):
            ordered = sorted(rows, key=lambda row: str(row.get("recommendation_id", "")))
            identifiers = [str(row["recommendation_id"]) for row in ordered]
            candidates.append({"business_issue": issue, "decision_id": _digest({"business_issue": issue, "recommendation_ids": identifiers}), "recommendations": ordered})
        return candidates


class ConflictAnalysisEngine:
    """Reports incompatible recommendation summaries; it never resolves them."""
    OPPOSITES = (("increase", "reduce"), ("enable", "disable"), ("expand", "restrict"))
    def analyse(self, candidate: Mapping[str, object]) -> dict[str, object]:
        rows = candidate.get("recommendations", [])
        conflicts = []
        for index, left in enumerate(rows):
            left_text = str(left.get("summary", "")).lower()
            for right in rows[index + 1:]:
                right_text = str(right.get("summary", "")).lower()
                if any(first in left_text and second in right_text or second in left_text and first in right_text for first, second in self.OPPOSITES):
                    conflicts.append({"recommendation_ids": sorted([str(left["recommendation_id"]), str(right["recommendation_id"])]), "reason": "OPPOSING_ADVISORY_ACTION"})
        return {"status": "CONFLICT" if conflicts else "CLEAR", "conflicts": conflicts}


class DecisionPrioritizationEngine:
    """Stable score: priority + governance health + lineage support coverage."""
    def rank(self, candidate: Mapping[str, object], governance_healthy: bool) -> dict[str, object]:
        rows = candidate["recommendations"]
        priority = max((PRIORITY_WEIGHT.get(str(row.get("priority")), 0) for row in rows), default=0)
        insights = {item for row in rows for item in row.get("supporting_insights", [])}
        evidence = {item for row in rows for item in row.get("supporting_evidence", [])}
        score = priority + (100 if governance_healthy else 0) + len(insights) * 10 + min(len(evidence), 50)
        return {"score": score, "priority": next((level for level, weight in PRIORITY_WEIGHT.items() if weight == priority), "INFORMATION"), "supporting_insight_count": len(insights), "historical_evidence_coverage": len(evidence)}


class ExecutivePackageBuilder:
    def __init__(self, *, clock: Callable[[], datetime] | None = None): self.clock = clock or (lambda: datetime.now(timezone.utc))
    def build(self, candidate: Mapping[str, object], conflict: Mapping[str, object], ranking: Mapping[str, object], governance: Mapping[str, object]) -> dict[str, object]:
        rows = candidate["recommendations"]
        lineage = {"insight_ids": sorted({x for row in rows for x in row.get("supporting_insights", [])}), "knowledge_ids": sorted({x for row in rows for x in row.get("supporting_knowledge", [])}), "evidence_ids": sorted({x for row in rows for x in row.get("supporting_evidence", [])}), "snapshot_ids": sorted({x for row in rows for x in row.get("supporting_snapshots", [])})}
        healthy = governance.get("overall_status") == "HEALTHY"
        blocked = not healthy or conflict["status"] == "CONFLICT"
        impacts = [row.get("estimated_impact", {}) for row in rows]
        return _metadata(self.clock, "RAIP Executive Package Builder") | {"decision_id": candidate["decision_id"], "business_issue": candidate["business_issue"], "executive_summary": f"Decision review required: {candidate['business_issue']}", "supporting_recommendations": [dict(row) for row in rows], "governance_status": {"approved": healthy, "overall_status": governance.get("overall_status", "MISSING"), "report_id": governance.get("report_id")}, "evidence_lineage": lineage, "expected_historical_impact": impacts, "risk_summary": {"blocked": blocked, "conflict_status": conflict["status"], "conflicts": conflict["conflicts"]}, "approval_required": True, "priority": ranking["priority"], "priority_score": ranking["score"], "supporting_insight_count": ranking["supporting_insight_count"], "historical_evidence_coverage": ranking["historical_evidence_coverage"]}


class ExecutiveRepository:
    """Immutable append-only package repository. Existing decision IDs are never replaced."""
    def __init__(self, root: Path | str): self.root = Path(root)
    def save(self, package: Mapping[str, object]) -> Path:
        decision_id = str(package.get("decision_id", ""))
        if len(decision_id) != 64: raise ValueError("DECISION_ID_REQUIRED")
        path = self.root / "executive" / "decision_repository" / decision_id / "executive_repository.json"
        if path.exists(): return path
        _atomic_write_once(path, package)
        return path


def _atomic_write_once(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists(): return
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(document, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
    try:
        with temporary.open("xb") as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        if not path.exists(): os.rename(temporary, path)
    except FileExistsError:
        pass
    finally:
        if temporary.exists(): temporary.unlink()


class ExecutiveReadinessReport:
    def __init__(self, *, clock: Callable[[], datetime] | None = None): self.clock = clock or (lambda: datetime.now(timezone.utc))
    def build(self, packages: Sequence[Mapping[str, object]]) -> dict[str, object]:
        blocked = [item for item in packages if item["risk_summary"]["blocked"]]
        high = [item for item in packages if item.get("priority") in ("CRITICAL", "HIGH")]
        total_recs = sum(len(item["supporting_recommendations"]) for item in packages)
        complete = sum(bool(item["evidence_lineage"]["evidence_ids"]) for item in packages)
        return _metadata(self.clock, "RAIP Executive Readiness Report") | {"pending_decisions": len(packages), "high_priority_decisions": len(high), "blocked_decisions": len(blocked), "governance_failures": sum(item["governance_status"]["overall_status"] != "HEALTHY" for item in packages), "recommendation_coverage": {"decision_count": len(packages), "recommendation_count": total_recs}, "evidence_completeness": {"complete_decisions": complete, "total_decisions": len(packages), "ratio": complete / len(packages) if packages else 1.0}, "decision_ids": [item["decision_id"] for item in sorted(packages, key=lambda item: (-int(item["priority_score"]), item["decision_id"]))]}


class ExecutiveCoordinator:
    """Async, retry-safe post-governance preparation; failures are isolated from trading."""
    def __init__(self, root: Path | str, *, clock: Callable[[], datetime] | None = None):
        self.root, self.clock = Path(root), clock or (lambda: datetime.now(timezone.utc)); self.aggregator = DecisionCandidateAggregator(); self.conflicts = ConflictAnalysisEngine(); self.prioritizer = DecisionPrioritizationEngine(); self.builder = ExecutivePackageBuilder(clock=self.clock); self.repository = ExecutiveRepository(self.root); self.readiness = ExecutiveReadinessReport(clock=self.clock); self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="raip-executive"); self.log = logging.getLogger(__name__)
    def process_available(self) -> list[Path]:
        recommendations = self._recommendations(); governance = self._governance()
        packages = []
        for candidate in self.aggregator.aggregate(recommendations):
            conflict = self.conflicts.analyse(candidate); ranking = self.prioritizer.rank(candidate, governance.get("overall_status") == "HEALTHY")
            packages.append(self.builder.build(candidate, conflict, ranking, governance))
        packages.sort(key=lambda item: (-int(item["priority_score"]), item["decision_id"]))
        paths = []
        for package in packages:
            package_path = self.root / "executive" / "decision_packages" / package["decision_id"] / "executive_decision_package.json"
            if not package_path.exists():
                _atomic_replace(package_path, package)
            paths.append(self.repository.save(package))
        _atomic_replace(self.root / "executive" / "readiness" / "executive_readiness.json", self.readiness.build(packages))
        return paths
    def process_async(self) -> Future: return self._executor.submit(self._process_safely)
    def _process_safely(self):
        try: return self.process_available()
        except Exception:
            self.log.exception("executive preparation failed safely; trading remains unaffected")
            raise
    def shutdown(self): self._executor.shutdown(wait=True)
    def _recommendations(self):
        rows = []
        for path in sorted((self.root / "recommendations").glob("*/recommendation_repository.json")):
            try: rows.extend(json.loads(path.read_text(encoding="utf-8")).get("recommendations", []))
            except (OSError, json.JSONDecodeError): self.log.warning("unreadable recommendation repository: %s", path)
        return [row for row in rows if isinstance(row, Mapping)]
    def _governance(self):
        path = self.root / "governance" / "health" / "governance_report.json"
        try: return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): return {"overall_status": "MISSING"}
