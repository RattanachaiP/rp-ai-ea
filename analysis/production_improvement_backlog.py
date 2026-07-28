"""Build a human-governed improvement backlog from production evidence (PR255).

This is an offline report builder.  It imports no Runtime, AI, strategy,
execution, risk, learning, production, or promotion package and cannot apply an
item.  Only directly measured adverse observations can create backlog items.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


SCHEMA_VERSION = "PR255.PRODUCTION_IMPROVEMENT_BACKLOG.1.1"
ALLOWED_SOURCES = frozenset({
    "runtime_metrics.json", "runtime_daily_summary.json", "trade_statistics.csv",
    "production_trading_report.json", "daily_trade_review.json",
    "pipeline_validation_report.json", "ReportHistory", "Experts.log", "Journal.log",
})
PRIORITY_BY_SEVERITY = {"CRITICAL": "P0", "HIGH": "P1", "MEDIUM": "P2", "LOW": "P3"}
OPERATIONAL_RULES = {
    "execution_rejections": ("EXECUTION_RELIABILITY", "Execution rejections were observed.", "HIGH", "Execution", "rejected_execution_count"),
    "duplicate_decisions": ("DECISION_DELIVERY", "Duplicate decision publications were observed.", "HIGH", "Writer/Decision Publication", "duplicate_publication_count"),
    "runtime_restarts": ("RUNTIME_STABILITY", "Runtime restarts were observed.", "MEDIUM", "Runtime Operations", "restart_count"),
    "telemetry_runtime_exceptions": ("RUNTIME_STABILITY", "Runtime exceptions were observed in telemetry.", "HIGH", "Runtime Operations", "exception_count"),
    "log_exception_indicators": ("RUNTIME_STABILITY", "Exception indicators were observed in production logs.", "MEDIUM", "Runtime Operations", "log_indicator_count"),
}


def _read_report(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"INVALID_JSON_SOURCE:{path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"INVALID_JSON_SOURCE:{path.name}")
    return value


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _nonnegative_integer(value: object, *, error: str) -> int:
    number = _number(value)
    if number is None or number < 0 or not number.is_integer():
        raise ValueError(error)
    return int(number)


def _sample_size(value: object, *, metric: str) -> int | None:
    if value is None:
        return None
    sample = _nonnegative_integer(value, error=f"INVALID_GOVERNED_SAMPLE_SIZE:{metric}")
    if sample == 0:
        raise ValueError(f"INVALID_GOVERNED_SAMPLE_SIZE:{metric}")
    return sample


def _item(*, key: str, snapshot_sha256: str, category: str, description: str,
          source_ref: str, pointer: str, observed_value: int | float,
          frequency: Mapping[str, object], impact: Mapping[str, object], severity: str,
          component: str) -> dict[str, object]:
    """Create a snapshot-scoped item; severity alone governs priority."""
    return {
        "id": f"PR255-{key}-{snapshot_sha256.upper()}",
        "category": category,
        "description": description,
        "evidence": [{"source_ref": source_ref, "json_pointer": pointer,
                      "observed_value": observed_value}],
        "frequency": dict(frequency),
        "business_impact": dict(impact),
        "reproducibility": {"classification": "NOT_ESTABLISHED",
                            "basis": "single_authoritative_snapshot"},
        "severity": severity,
        "priority": PRIORITY_BY_SEVERITY[severity],
        "recommended_component": component,
        "status": "PENDING_HUMAN_REVIEW",
    }


def _production_items(path: Path, report: Mapping[str, object], *, source_ref: str,
                      digest: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if report.get("schema_version") != "PR253.PRODUCTION_TRADING_REPORT.1.0":
        raise ValueError(f"INVALID_SOURCE_SCHEMA:{path.name}")
    observations = report.get("measurable_observations")
    if not isinstance(observations, list):
        raise ValueError(f"MISSING_MEASURABLE_OBSERVATIONS:{path.name}")
    items: list[dict[str, object]] = []
    unsupported: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, observation in enumerate(observations):
        if not isinstance(observation, Mapping) or not isinstance(observation.get("metric"), str):
            raise ValueError(f"MALFORMED_GOVERNED_OBSERVATION:index={index}")
        metric = str(observation["metric"])
        if metric in seen:
            raise ValueError(f"DUPLICATE_OBSERVATION:{metric}")
        seen.add(metric)
        if metric not in OPERATIONAL_RULES:
            unsupported.append({"source_ref": source_ref,
                "json_pointer": f"/measurable_observations/{index}", "metric": metric,
                "processing_status": "UNSUPPORTED_GOVERNED_OBSERVATION"})
            continue
        occurrences = _nonnegative_integer(observation.get("value"),
            error=f"INVALID_GOVERNED_OBSERVATION_VALUE:{metric}")
        sample_size = _sample_size(observation.get("sample_size"), metric=metric)
        if occurrences == 0:
            continue
        category, description, severity, component, impact_name = OPERATIONAL_RULES[metric]
        rate = round(occurrences / sample_size, 6) if sample_size else None
        items.append(_item(key=metric.upper(), snapshot_sha256=digest, category=category,
            description=description, source_ref=source_ref,
            pointer=f"/measurable_observations/{index}/value", observed_value=occurrences,
            frequency={"measurement": "occurrence_rate", "occurrences": occurrences,
                       "sample_size": sample_size, "rate": rate},
            impact={"measure": impact_name, "value": occurrences, "unit": "count"},
            severity=severity, component=component))
    trading = report.get("trading")
    if not isinstance(trading, Mapping):
        raise ValueError(f"MISSING_TRADING_MEASUREMENTS:{path.name}")
    trades = _nonnegative_integer(trading.get("total_trades"), error="INVALID_TOTAL_TRADES")
    net_profit = _number(trading.get("net_profit"))
    if net_profit is None:
        raise ValueError("INVALID_NET_PROFIT")
    if trades and net_profit < 0:
        items.append(_item(key="NEGATIVE_NET_PROFIT", snapshot_sha256=digest,
            category="TRADING_OUTCOME", description="Completed trades produced a measured net loss.",
            source_ref=source_ref, pointer="/trading/net_profit", observed_value=net_profit,
            frequency={"measurement": "not_applicable", "reason": "aggregate_outcome"},
            impact={"measure": "net_profit", "value": net_profit, "unit": "report_currency",
                    "trade_sample_size": trades}, severity="HIGH", component="Human Strategy Review"))
    return items, unsupported


def _pipeline_items(path: Path, report: Mapping[str, object], *, source_ref: str,
                    digest: str) -> list[dict[str, object]]:
    if report.get("schema_version") != "PR254.PIPELINE_VALIDATION_REPORT.1.0":
        raise ValueError(f"INVALID_SOURCE_SCHEMA:{path.name}")
    metrics = report.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError(f"MISSING_PIPELINE_METRICS:{path.name}")
    total = _nonnegative_integer(metrics.get("total_lifecycles"), error="INVALID_TOTAL_LIFECYCLES")
    if total == 0:
        raise ValueError("INVALID_TOTAL_LIFECYCLES")
    missing = _nonnegative_integer(metrics.get("missing_stage_count"), error="INVALID_MISSING_STAGE_COUNT")
    if missing == 0:
        return []
    density = round(missing / total, 6)
    return [_item(key="PIPELINE_MISSING_STAGES", snapshot_sha256=digest,
        category="PIPELINE_COMPLETENESS",
        description="Production lifecycle stages were absent; cause attribution remains unknown.",
        source_ref=source_ref, pointer="/metrics/missing_stage_count", observed_value=missing,
        frequency={"measurement": "event_density",
                   "metric": "missing_stage_events_per_lifecycle",
                   "missing_stage_events": missing, "total_lifecycles": total, "value": density},
        impact={"measure": "missing_stage_count", "value": missing, "unit": "stage_events"},
        severity="CRITICAL", component="Human Pipeline Investigation")]


def _generated_time(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value)
    except ValueError as exc:
        raise ValueError("INVALID_GENERATED_AT_UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("AMBIGUOUS_GENERATED_AT_UTC")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_backlog(*, evidence: Sequence[Path | str], output_directory: Path | str,
                     generated_at_utc: str | None = None) -> dict[str, object]:
    """Inspect exact selected snapshots and atomically write the sole PR255 output."""
    paths = [Path(item) for item in evidence]
    if not paths:
        raise ValueError("NO_EVIDENCE_SELECTED")
    resolved = [str(path.resolve()) for path in paths]
    if len(set(resolved)) != len(resolved):
        raise ValueError("DUPLICATE_EVIDENCE_PATH")

    selected: list[dict[str, object]] = []
    for path in paths:
        if path.name not in ALLOWED_SOURCES:
            raise ValueError(f"NON_AUTHORITATIVE_SOURCE:{path.name}")
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ValueError(f"UNREADABLE_EVIDENCE_SOURCE:{path.name}") from exc
        selected.append({"path": path, "basename": path.name,
                         "sha256": hashlib.sha256(payload).hexdigest()})
    identities = [(entry["basename"], entry["sha256"]) for entry in selected]
    if len(set(identities)) != len(identities):
        raise ValueError("DUPLICATE_EVIDENCE_SNAPSHOT")
    selected.sort(key=lambda entry: (str(entry["basename"]), str(entry["sha256"])))

    items: list[dict[str, object]] = []
    unsupported: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    for number, entry in enumerate(selected, start=1):
        path = entry["path"]
        assert isinstance(path, Path)
        digest = str(entry["sha256"])
        source_ref = f"S{number:06d}"
        source_items: list[dict[str, object]] = []
        if path.name == "production_trading_report.json":
            source_items, source_unsupported = _production_items(
                path, _read_report(path), source_ref=source_ref, digest=digest)
            unsupported.extend(source_unsupported)
            status = "ANALYZED" if source_items else "NO_ADVERSE_OBSERVATION"
        elif path.name == "pipeline_validation_report.json":
            source_items = _pipeline_items(path, _read_report(path), source_ref=source_ref, digest=digest)
            status = "ANALYZED" if source_items else "NO_ADVERSE_OBSERVATION"
        else:
            status = "PROVENANCE_ONLY"
        items.extend(source_items)
        sources.append({"source_ref": source_ref, "basename": path.name,
                        "sha256": digest, "processing_status": status})

    items.sort(key=lambda item: (str(item["priority"]), str(item["id"])))
    unsupported.sort(key=lambda value: (str(value["source_ref"]), str(value["json_pointer"])))
    now = generated_at_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report = {"schema_version": SCHEMA_VERSION, "generated_at_utc": _generated_time(now),
              "advisory_only": True, "human_approval_required": True,
              "source_evidence": sources, "unsupported_observations": unsupported, "items": items}

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "production_improvement_backlog.json"
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with temporary.open("wb") as stream:
            stream.write((json.dumps(report, indent=2, sort_keys=True) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", action="append", required=True)
    parser.add_argument("--output-directory", required=True)
    args = parser.parse_args(argv)
    generate_backlog(evidence=args.evidence, output_directory=args.output_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
