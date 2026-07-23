"""Read-only, asynchronous RAIP governance.  This package never imports trading code."""
from __future__ import annotations

import ast
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import time
from typing import Callable, Mapping

REQUIRED_METADATA = ("schema_version", "producer", "owner", "created_at")
GOVERNANCE_VERSION = "6.0.0"
BASELINE_COMMIT = "b108658"
LAYERS = ("snapshots", "evidence", "knowledge", "insights", "recommendations")


def _iso(clock: Callable[[], datetime]) -> str:
    return clock().astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _metadata(clock: Callable[[], datetime], producer: str) -> dict[str, object]:
    return {"schema_version": GOVERNANCE_VERSION, "producer": producer,
            "owner": "RAIP Governance Engine", "created_at": _iso(clock),
            "governance_version": GOVERNANCE_VERSION, "baseline_commit": BASELINE_COMMIT}


def _documents(root: Path) -> list[tuple[str, Path, dict[str, object]]]:
    records = []
    for layer in LAYERS:
        directory = root / layer
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                records.append((layer, path, value if isinstance(value, dict) else {}))
            except (OSError, json.JSONDecodeError):
                records.append((layer, path, {}))
    return records


class ArchitectureBoundaryMonitor:
    """Static AST boundary audit; it only reads RAIP source files."""
    FORBIDDEN_ROOTS = {"bridge", "runtime", "mt5"}
    FORBIDDEN_NAMES = {"decision", "writer", "executor", "broker", "order_send", "ordersend", "risk_engine"}

    def __init__(self, project_root: Path | str, *, clock=None):
        self.project_root, self.clock = Path(project_root), clock or (lambda: datetime.now(timezone.utc))

    def check(self) -> dict[str, object]:
        issues = []
        package = self.project_root / "review_engine"
        for path in sorted(package.rglob("*.py")):
            if "governance" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError) as exc:
                issues.append({"code": "SOURCE_UNREADABLE", "path": str(path.relative_to(self.project_root)), "detail": str(exc)})
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                    for name in names:
                        if name.split(".")[0] in self.FORBIDDEN_ROOTS:
                            issues.append({"code": "PROHIBITED_DEPENDENCY", "path": str(path.relative_to(self.project_root)), "dependency": name, "line": node.lineno})
                if isinstance(node, ast.Call):
                    name = getattr(node.func, "id", "").lower() if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "").lower()
                    if name in self.FORBIDDEN_NAMES:
                        issues.append({"code": "PROHIBITED_RUNTIME_CALL", "path": str(path.relative_to(self.project_root)), "call": name, "line": node.lineno})
        return _metadata(self.clock, "RAIP Architecture Boundary Monitor") | {"status": "PASS" if not issues else "FAIL", "issues": sorted(issues, key=lambda row: (row["path"], row.get("line", 0), row["code"])), "checked_modules": len(list(package.rglob("*.py")))}


class SchemaIntegrityMonitor:
    """Checks the common contract and known layer schema versions without mutation."""
    EXPECTED = {"evidence": "2.0.0", "knowledge": "3.0.0", "insights": "4.0.0", "recommendations": "5.0.0"}
    def __init__(self, root: Path | str, *, clock=None): self.root, self.clock = Path(root), clock or (lambda: datetime.now(timezone.utc))
    def check(self) -> dict[str, object]:
        issues = []
        for layer, path, document in _documents(self.root):
            missing = [field for field in REQUIRED_METADATA if not document.get(field)]
            if missing: issues.append({"code": "MISSING_REQUIRED_FIELDS", "path": str(path.relative_to(self.root)), "fields": missing})
            expected = self.EXPECTED.get(layer)
            if expected and document.get("schema_version") != expected:
                issues.append({"code": "INCOMPATIBLE_SCHEMA", "path": str(path.relative_to(self.root)), "expected": expected, "actual": document.get("schema_version")})
            if str(document.get("schema_version", "")).startswith(("0.", "1.")):
                issues.append({"code": "DEPRECATED_SCHEMA", "path": str(path.relative_to(self.root)), "actual": document.get("schema_version")})
        return _metadata(self.clock, "RAIP Schema Integrity Monitor") | {"status": "PASS" if not issues else "FAIL", "issues": issues, "checked_documents": len(_documents(self.root))}


class RepositoryIntegrityMonitor:
    """Detects malformed JSON, duplicate logical IDs, broken local references, and invalid snapshot hashes."""
    ID_FIELDS = {"snapshots": "snapshot_id", "evidence": "evidence_id", "knowledge": "pattern_repository_version", "insights": "insight_version", "recommendations": "recommendation_version"}
    def __init__(self, root: Path | str, *, clock=None): self.root, self.clock = Path(root), clock or (lambda: datetime.now(timezone.utc))
    def check(self) -> dict[str, object]:
        issues, ids = [], {layer: set() for layer in LAYERS}
        seen = set()
        for layer, path, document in _documents(self.root):
            key = str(document.get(self.ID_FIELDS.get(layer, ""), ""))
            marker = (layer, key)
            if not key: issues.append({"code": "MISSING_ID", "path": str(path.relative_to(self.root))})
            elif marker in seen: issues.append({"code": "DUPLICATE_ID", "path": str(path.relative_to(self.root)), "id": key})
            else: seen.add(marker); ids[layer].add(key)
            if layer == "snapshots" and document:
                supplied = document.get("provenance", {}).get("snapshot_sha256") if isinstance(document.get("provenance"), Mapping) else None
                copy = json.loads(json.dumps(document));
                if isinstance(copy.get("provenance"), dict): copy["provenance"]["snapshot_sha256"] = ""
                if supplied and supplied != _digest(copy): issues.append({"code": "INVALID_HASH", "path": str(path.relative_to(self.root))})
        for layer, path, document in _documents(self.root):
            if layer == "evidence" and str(document.get("snapshot_id", "")) not in ids["snapshots"]:
                issues.append({"code": "ORPHAN_RECORD", "path": str(path.relative_to(self.root)), "reference": "snapshot_id"})
            if layer == "insights" and str(document.get("knowledge_version", "")) not in ids["knowledge"]:
                issues.append({"code": "BROKEN_REFERENCE", "path": str(path.relative_to(self.root)), "reference": "knowledge_version"})
            if layer == "recommendations" and str(document.get("insight_version", "")) not in ids["insights"]:
                issues.append({"code": "BROKEN_REFERENCE", "path": str(path.relative_to(self.root)), "reference": "insight_version"})
        return _metadata(self.clock, "RAIP Repository Integrity Monitor") | {"status": "PASS" if not issues else "FAIL", "issues": issues, "checked_documents": len(_documents(self.root))}


class DataLineageAuditor:
    def __init__(self, root: Path | str, *, clock=None): self.root, self.clock = Path(root), clock or (lambda: datetime.now(timezone.utc))
    def check(self) -> dict[str, object]:
        issues = []
        records = _documents(self.root)
        identifiers = {layer: {str(doc.get(field, "")) for current, _, doc in records if current == layer} for layer, field in RepositoryIntegrityMonitor.ID_FIELDS.items()}
        for layer, path, doc in records:
            rel = str(path.relative_to(self.root))
            if layer == "evidence" and str(doc.get("snapshot_id", "")) not in identifiers["snapshots"]: issues.append({"code": "LINEAGE_SNAPSHOT_MISSING", "path": rel})
            if layer == "knowledge":
                rows = doc.get("generated_from", {}).get("evidence_lineage", []) if isinstance(doc.get("generated_from"), Mapping) else []
                if not rows: issues.append({"code": "LINEAGE_EVIDENCE_MISSING", "path": rel})
                for row in rows if isinstance(rows, list) else []:
                    if not isinstance(row, Mapping) or str(row.get("evidence_id", "")) not in identifiers["evidence"] or str(row.get("snapshot_id", "")) not in identifiers["snapshots"]: issues.append({"code": "LINEAGE_INCOMPLETE", "path": rel})
            if layer == "insights":
                lineage = doc.get("lineage", {}) if isinstance(doc.get("lineage"), Mapping) else {}
                if str(doc.get("knowledge_version", "")) not in identifiers["knowledge"] or not lineage.get("evidence"): issues.append({"code": "LINEAGE_INCOMPLETE", "path": rel})
            if layer == "recommendations":
                for row in doc.get("recommendations", []) if isinstance(doc.get("recommendations"), list) else []:
                    if not all(row.get(key) for key in ("supporting_insights", "supporting_knowledge", "supporting_evidence", "supporting_snapshots")): issues.append({"code": "LINEAGE_INCOMPLETE", "path": rel})
        return _metadata(self.clock, "RAIP Data Lineage Auditor") | {"status": "PASS" if not issues else "FAIL", "issues": issues, "checked_documents": len(records)}


class PlatformPerformanceMonitor:
    def __init__(self, root: Path | str, *, clock=None, metrics_provider: Callable[[], Mapping[str, object]] | None = None): self.root, self.clock, self.metrics_provider = Path(root), clock or (lambda: datetime.now(timezone.utc)), metrics_provider
    def check(self, elapsed_seconds: float = 0.0) -> dict[str, object]:
        supplied = dict(self.metrics_provider() if self.metrics_provider else {})
        total = len(_documents(self.root)); failures = sum(1 for _, _, doc in _documents(self.root) if not doc)
        metrics = {"processing_latency_ms": round(elapsed_seconds * 1000, 3), "queue_depth": int(supplied.get("queue_depth", 0)), "retry_count": int(supplied.get("retry_count", 0)), "failure_count": int(supplied.get("failure_count", failures)), "processing_throughput_per_second": round(total / elapsed_seconds, 6) if elapsed_seconds else 0.0}
        return _metadata(self.clock, "RAIP Platform Performance Monitor") | {"status": "PASS" if metrics["failure_count"] == 0 else "WARN", "metrics": metrics}


class GovernanceRepository:
    """Append-only governance history; a report ID can never be overwritten."""
    def __init__(self, root: Path | str): self.root = Path(root)
    def save(self, report: Mapping[str, object]) -> Path:
        report_id = str(report.get("report_id", ""))
        if not report_id: raise ValueError("REPORT_ID_REQUIRED")
        document = _metadata(lambda: datetime.fromisoformat(str(report["created_at"]).replace("Z", "+00:00")), "RAIP Governance History Repository") | {"report_id": report_id, "timestamp": report["created_at"], "platform_status": report["overall_status"], "detected_issues": report["detected_issues"], "warning_count": report["warning_count"]}
        path = self.root / "governance" / "history" / report_id / "governance_repository.json"; path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists(): return path
        tmp = path.with_suffix(".json.tmp"); payload = (json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        try:
            with tmp.open("xb") as handle: handle.write(payload); handle.flush(); os.fsync(handle.fileno())
            if not path.exists(): os.rename(tmp, path)
        except FileExistsError: pass
        finally:
            if tmp.exists(): tmp.unlink()
        return path


class GovernanceCoordinator:
    """Failure-isolated observer.  It has no runtime objects or trading imports."""
    OUTPUTS = (("boundary", "boundary_health.json"), ("health", "schema_health.json"), ("integrity", "repository_health.json"), ("lineage", "lineage_health.json"), ("performance", "performance_health.json"))
    def __init__(self, root: Path | str, project_root: Path | str | None = None, *, clock=None):
        self.root, self.project_root, self.clock = Path(root), Path(project_root) if project_root else Path(__file__).resolve().parents[2], clock or (lambda: datetime.now(timezone.utc)); self.repository = GovernanceRepository(self.root); self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="raip-governance"); self.log = logging.getLogger(__name__)
    def run(self) -> dict[str, object]:
        started = time.perf_counter()
        monitors = [ArchitectureBoundaryMonitor(self.project_root, clock=self.clock).check(), SchemaIntegrityMonitor(self.root, clock=self.clock).check(), RepositoryIntegrityMonitor(self.root, clock=self.clock).check(), DataLineageAuditor(self.root, clock=self.clock).check()]
        monitors.append(PlatformPerformanceMonitor(self.root, clock=self.clock).check(time.perf_counter() - started))
        for (folder, filename), document in zip(self.OUTPUTS, monitors): self._atomic_replace(self.root / "governance" / folder / filename, document)
        statuses = [item["status"] for item in monitors]; issues = [issue for item in monitors for issue in item.get("issues", [])]
        report_id = _digest({"baseline_commit": BASELINE_COMMIT, "monitors": [{"producer": item["producer"], "status": item["status"], "issues": item.get("issues", [])} for item in monitors]})
        report = _metadata(self.clock, "RAIP Governance Coordinator") | {"report_id": report_id, "overall_status": "HEALTHY" if all(value == "PASS" for value in statuses) else "UNHEALTHY", "monitor_status": {item["producer"].replace("RAIP ", "").replace(" Monitor", ""): item["status"] for item in monitors}, "detected_issues": issues, "warning_count": sum(value == "WARN" for value in statuses)}
        self._atomic_replace(self.root / "governance" / "health" / "governance_report.json", report); self.repository.save(report); return report
    def run_async(self) -> Future: return self._executor.submit(self._run_safely)
    def _run_safely(self):
        try: return self.run()
        except Exception: self.log.exception("governance failed safely; trading remains unaffected"); raise
    def shutdown(self): self._executor.shutdown(wait=True)
    @staticmethod
    def _atomic_replace(path: Path, document: Mapping[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("wb") as handle:
            handle.write((json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, path)
