"""Build a human-governed improvement backlog from production evidence (PR255).

This module is an offline report builder.  It deliberately has no imports from
Runtime, AI, strategy, execution, or learning packages and cannot apply a
backlog item.  It records only directly measured adverse observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


SCHEMA_VERSION = "PR255.PRODUCTION_IMPROVEMENT_BACKLOG.1.0"
ALLOWED_SOURCES = frozenset({
    "runtime_metrics.json", "runtime_daily_summary.json", "trade_statistics.csv",
    "production_trading_report.json", "daily_trade_review.json",
    "pipeline_validation_report.json", "ReportHistory", "Experts.log", "Journal.log",
})


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
    return result if result == result and abs(result) != float("inf") else None


def _priority(severity: str, occurrences: int) -> str:
    base = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}[severity]
    # Repeated evidence may raise urgency by one band, but never creates an item.
    return f"P{max(0, base - (1 if occurrences > 1 else 0))}"


def _item(*, key: str, category: str, description: str, source: Path,
          pointer: str, occurrences: int, sample_size: int | None, impact: Mapping[str, object],
          severity: str, component: str) -> dict[str, object]:
    rate = round(occurrences / sample_size, 6) if sample_size else None
    return {
        "id": f"PR255-{key}", "category": category, "description": description,
        "evidence": [{"source": source.name, "json_pointer": pointer,
                      "observed_value": occurrences}],
        "frequency": {"occurrences": occurrences, "sample_size": sample_size, "rate": rate},
        "business_impact": dict(impact),
        "reproducibility": {"classification": "REPEATED" if occurrences > 1 else "OBSERVED_ONCE",
                            "observed_occurrences": occurrences},
        "severity": severity, "priority": _priority(severity, occurrences),
        "recommended_component": component, "status": "PENDING_HUMAN_REVIEW",
    }


def _from_production_report(path: Path, report: Mapping[str, object]) -> list[dict[str, object]]:
    if report.get("schema_version") != "PR253.PRODUCTION_TRADING_REPORT.1.0":
        raise ValueError(f"INVALID_SOURCE_SCHEMA:{path.name}")
    observations = report.get("measurable_observations")
    if not isinstance(observations, list):
        raise ValueError(f"MISSING_MEASURABLE_OBSERVATIONS:{path.name}")
    specifications = {
        "execution_rejections": ("EXECUTION_RELIABILITY", "Execution rejections were observed.", "HIGH", "Execution", "rejected_execution_count"),
        "duplicate_decisions": ("DECISION_DELIVERY", "Duplicate decision publications were observed.", "HIGH", "Writer/Decision Publication", "duplicate_publication_count"),
        "runtime_restarts": ("RUNTIME_STABILITY", "Runtime restarts were observed.", "MEDIUM", "Runtime Operations", "restart_count"),
        "telemetry_runtime_exceptions": ("RUNTIME_STABILITY", "Runtime exceptions were observed in telemetry.", "HIGH", "Runtime Operations", "exception_count"),
        "log_exception_indicators": ("RUNTIME_STABILITY", "Exception indicators were observed in production logs.", "MEDIUM", "Runtime Operations", "log_indicator_count"),
    }
    result = []
    seen: set[str] = set()
    for index, observation in enumerate(observations):
        if not isinstance(observation, Mapping) or observation.get("metric") not in specifications:
            continue
        metric = str(observation["metric"])
        if metric in seen:
            raise ValueError(f"DUPLICATE_OBSERVATION:{metric}")
        seen.add(metric)
        value = _number(observation.get("value"))
        if value is None or value <= 0 or not value.is_integer():
            continue
        sample = _number(observation.get("sample_size"))
        sample_size = int(sample) if sample is not None and sample > 0 and sample.is_integer() else None
        category, description, severity, component, impact_name = specifications[metric]
        result.append(_item(key=metric.upper(), category=category, description=description,
                            source=path, pointer=f"/measurable_observations/{index}/value",
                            occurrences=int(value), sample_size=sample_size,
                            impact={"measure": impact_name, "value": int(value), "unit": "count"},
                            severity=severity, component=component))
    trading = report.get("trading")
    if isinstance(trading, Mapping):
        count = _number(trading.get("total_trades"))
        net = _number(trading.get("net_profit"))
        if count is not None and count > 0 and count.is_integer() and net is not None and net < 0:
            result.append(_item(key="NEGATIVE_NET_PROFIT", category="TRADING_OUTCOME",
                description="Completed trades produced a measured net loss.", source=path,
                pointer="/trading/net_profit", occurrences=1, sample_size=int(count),
                impact={"measure": "net_profit", "value": net, "unit": "report_currency"},
                severity="HIGH", component="Human Strategy Review"))
    return result


def _from_pipeline_report(path: Path, report: Mapping[str, object]) -> list[dict[str, object]]:
    if report.get("schema_version") != "PR254.PIPELINE_VALIDATION_REPORT.1.0":
        raise ValueError(f"INVALID_SOURCE_SCHEMA:{path.name}")
    metrics = report.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError(f"MISSING_PIPELINE_METRICS:{path.name}")
    total = _number(metrics.get("total_lifecycles"))
    total_count = int(total) if total is not None and total > 0 and total.is_integer() else None
    missing = _number(metrics.get("missing_stage_count"))
    if missing is None or missing <= 0 or not missing.is_integer():
        return []
    return [_item(key="PIPELINE_MISSING_STAGES", category="PIPELINE_COMPLETENESS",
        description="Production lifecycle stages were absent from the selected trace.", source=path,
        pointer="/metrics/missing_stage_count", occurrences=int(missing), sample_size=total_count,
        impact={"measure": "missing_stage_count", "value": int(missing), "unit": "stage_events"},
        severity="CRITICAL", component="Pipeline Stage Owner")]


def generate_backlog(*, evidence: Sequence[Path | str], output_directory: Path | str,
                     generated_at_utc: str | None = None) -> dict[str, object]:
    """Inspect exact evidence snapshots and atomically write the sole PR255 output."""
    paths = [Path(item) for item in evidence]
    if not paths:
        raise ValueError("NO_EVIDENCE_SELECTED")
    if len({str(path.resolve()) for path in paths}) != len(paths):
        raise ValueError("DUPLICATE_EVIDENCE_SOURCE")
    items: list[dict[str, object]] = []
    sources = []
    for path in paths:
        if path.name not in ALLOWED_SOURCES:
            raise ValueError(f"NON_AUTHORITATIVE_SOURCE:{path.name}")
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ValueError(f"UNREADABLE_EVIDENCE_SOURCE:{path.name}") from exc
        sources.append({"basename": path.name, "sha256": hashlib.sha256(payload).hexdigest()})
        if path.name == "production_trading_report.json":
            items.extend(_from_production_report(path, _read_report(path)))
        elif path.name == "pipeline_validation_report.json":
            items.extend(_from_pipeline_report(path, _read_report(path)))
        # Remaining authoritative artifacts are retained as source evidence.  Their
        # facts are not reinterpreted without a governed, schema-specific rule.
    if len({str(item["id"]) for item in items}) != len(items):
        raise ValueError("DUPLICATE_BACKLOG_ITEM")
    items.sort(key=lambda item: (str(item["priority"]), str(item["id"])))
    now = generated_at_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        parsed = datetime.fromisoformat(now[:-1] + "+00:00" if now.endswith("Z") else now)
    except ValueError as exc:
        raise ValueError("INVALID_GENERATED_AT_UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("AMBIGUOUS_GENERATED_AT_UTC")
    report = {"schema_version": SCHEMA_VERSION,
              "generated_at_utc": parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
              "advisory_only": True, "human_approval_required": True,
              "source_evidence": sources, "items": items}
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "production_improvement_backlog.json"
    temporary = destination.with_name(destination.name + ".tmp")
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
