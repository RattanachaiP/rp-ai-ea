"""Read-only end-to-end production pipeline validation (PR254).

The validator consumes an operator-selected JSON Lines trace captured by the
production host.  It has no imports from, and makes no calls into, any trading
subsystem.  Its sole side effect is an atomically written validation report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


SCHEMA_VERSION = "PR254.PIPELINE_VALIDATION_REPORT.1.0"
EVENT_SCHEMA_VERSION = "PR254.PIPELINE_TRACE_EVENT.1.0"

STAGES = (
    "MARKET_STATE", "DECISION", "PACKAGE", "EXECUTOR_ACCEPTED", "ORDER_SENT",
    "ORDER_FILLED", "POSITION_CLOSED", "TELEMETRY", "ANALYTICS",
)
FAILURE_CLASSES = (
    "WRITER", "AI_ENGINE", "DECISION", "PACKAGE", "EXECUTOR", "BROKER",
    "ORDER", "POSITION", "TELEMETRY", "ANALYTICS", "UNKNOWN",
)
ALLOWED_FAILURE_CLASSES_BY_STAGE = {
    "MARKET_STATE": frozenset(("WRITER",)),
    "DECISION": frozenset(("AI_ENGINE", "DECISION")),
    "PACKAGE": frozenset(("PACKAGE",)),
    "EXECUTOR_ACCEPTED": frozenset(("EXECUTOR",)),
    "ORDER_SENT": frozenset(("ORDER",)),
    "ORDER_FILLED": frozenset(("BROKER",)),
    "POSITION_CLOSED": frozenset(("POSITION",)),
    "TELEMETRY": frozenset(("TELEMETRY",)),
    "ANALYTICS": frozenset(("ANALYTICS",)),
}


def _timestamp(value: object, *, line: int) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"MISSING_EVENT_TIMESTAMP:line={line}")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value)
    except ValueError as exc:
        raise ValueError(f"INVALID_EVENT_TIMESTAMP:line={line}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"AMBIGUOUS_EVENT_TIMESTAMP:line={line}")
    return parsed.astimezone(timezone.utc)


def _read_events(path: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"UNREADABLE_TRACE_SOURCE:{path.name}") from exc
    for line_number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"INVALID_TRACE_JSON:line={line_number}") from exc
        if not isinstance(event, dict) or event.get("schema_version") != EVENT_SCHEMA_VERSION:
            raise ValueError(f"INVALID_EVENT_SCHEMA:line={line_number}")
        lifecycle_id = event.get("lifecycle_id")
        if not isinstance(lifecycle_id, str) or not lifecycle_id.strip():
            raise ValueError(f"MISSING_LIFECYCLE_ID:line={line_number}")
        stage = event.get("stage")
        if stage not in STAGES:
            raise ValueError(f"INVALID_EVENT_STAGE:line={line_number}")
        status = event.get("status")
        if status not in ("SUCCEEDED", "FAILED"):
            raise ValueError(f"INVALID_EVENT_STATUS:line={line_number}")
        failure_class = event.get("failure_class")
        if status == "FAILED" and failure_class not in FAILURE_CLASSES:
            raise ValueError(f"FAILED_EVENT_REQUIRES_ONE_FAILURE_CLASS:line={line_number}")
        if status == "FAILED" and failure_class not in ALLOWED_FAILURE_CLASSES_BY_STAGE[stage]:
            raise ValueError(f"FAILURE_CLASS_NOT_ALLOWED_FOR_STAGE:line={line_number}")
        if status == "SUCCEEDED" and failure_class is not None:
            raise ValueError(f"SUCCESS_EVENT_HAS_FAILURE_CLASS:line={line_number}")
        timestamp = _timestamp(event.get("timestamp_utc"), line=line_number)
        events.append({**event, "_timestamp": timestamp, "_line": line_number})
    return events


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def generate_report(*, trace_events: Path | str, output_directory: Path | str,
                    generated_at_utc: str | None = None) -> dict[str, object]:
    """Validate an immutable trace and write only pipeline_validation_report.json."""
    source = Path(trace_events)
    events = _read_events(source)
    if not events:
        raise ValueError("EMPTY_PIPELINE_TRACE")
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for event in events:
        grouped[str(event["lifecycle_id"])].append(event)

    failure_events: Counter[str] = Counter()
    failure_lifecycles: Counter[str] = Counter()
    traces: list[dict[str, object]] = []
    successful = missing_count = 0
    stage_success = Counter()
    latencies: list[float] = []
    for lifecycle_number, lifecycle_id in enumerate(sorted(grouped), start=1):
        lifecycle = sorted(grouped[lifecycle_id], key=lambda item: (item["_timestamp"], item["_line"]))
        by_stage: dict[str, dict[str, object]] = {}
        failures: list[dict[str, str]] = []
        failed_stage: str | None = None
        lifecycle_failure_classes: set[str] = set()
        for event in lifecycle:
            stage = str(event["stage"])
            if failed_stage is not None:
                raise ValueError(f"STAGE_AFTER_TERMINAL_FAILURE:{lifecycle_id}:{stage}")
            if stage in by_stage:
                raise ValueError(f"DUPLICATE_LIFECYCLE_STAGE:{lifecycle_id}:{stage}")
            by_stage[stage] = event
            if event["status"] == "SUCCEEDED":
                stage_success[stage] += 1
            else:
                classification = str(event["failure_class"])
                failure_events[classification] += 1
                lifecycle_failure_classes.add(classification)
                failed_stage = stage
                failures.append({"stage": stage, "classification": classification,
                                 "reason": "EXPLICIT_FAILURE"})
        present = [stage for stage in STAGES if stage in by_stage]
        expected_prefix = list(STAGES[:len(present)])
        if present != expected_prefix:
            first_gap = next(stage for stage in STAGES if stage not in by_stage)
            raise ValueError(f"DOWNSTREAM_STAGE_WITH_MISSING_UPSTREAM:{lifecycle_id}:{first_gap}")
        timestamps = [by_stage[stage]["_timestamp"] for stage in present]
        if timestamps != sorted(timestamps):
            raise ValueError(f"INVALID_LIFECYCLE_CHRONOLOGY:{lifecycle_id}")
        missing = [stage for stage in STAGES if stage not in by_stage]
        missing_count += len(missing)
        for stage in missing:
            # Absence proves the location of an interruption, not its owner.
            # Attribution without an explicit failure event remains UNKNOWN.
            classification = "UNKNOWN"
            failure_events[classification] += 1
            lifecycle_failure_classes.add(classification)
            failures.append({"stage": stage, "classification": classification,
                             "reason": "MISSING_STAGE"})
        complete = not missing and not failures
        if complete:
            successful += 1
            latencies.append((by_stage["ANALYTICS"]["_timestamp"] - by_stage["MARKET_STATE"]["_timestamp"]).total_seconds() * 1000)
        for classification in lifecycle_failure_classes:
            failure_lifecycles[classification] += 1
        traces.append({
            # A stable report-local ordinal prevents trade/order/decision IDs
            # from crossing the offline reporting boundary.
            "lifecycle_ref": f"L{lifecycle_number:06d}",
            "complete": complete,
            "stage_times_utc": {stage: _iso(by_stage[stage]["_timestamp"]) if stage in by_stage else None for stage in STAGES},
            "missing_stages": missing,
            "failures": failures,
        })

    total = len(grouped)
    now = generated_at_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    # Validate caller-supplied report time using the same explicit-offset contract.
    generated = _iso(_timestamp(now, line=0))
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated,
        "validation_only": True,
        "source_evidence": {"basename": source.name, "sha256": source_digest, "event_count": len(events)},
        "metrics": {
            "total_lifecycles": total,
            "valid_decisions": stage_success["DECISION"],
            "packages_created": stage_success["PACKAGE"],
            "executor_acceptances": stage_success["EXECUTOR_ACCEPTED"],
            "orders_sent": stage_success["ORDER_SENT"],
            "orders_filled": stage_success["ORDER_FILLED"],
            "orders_closed": stage_success["POSITION_CLOSED"],
            "pipeline_success_rate": round(successful / total, 6) if total else None,
            "lifecycle_failure_rate_by_class": {
                name: round(failure_lifecycles[name] / total, 6) for name in FAILURE_CLASSES},
            "failure_events_per_lifecycle_by_class": {
                name: round(failure_events[name] / total, 6) for name in FAILURE_CLASSES},
            "average_end_to_end_latency_ms": round(sum(latencies) / len(latencies), 6) if latencies else None,
            "missing_stage_count": missing_count,
        },
        "lifecycles": traces,
    }
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "pipeline_validation_report.json"
    temporary = destination.with_name(destination.name + ".tmp")
    payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the read-only PR254 pipeline validation report")
    parser.add_argument("--trace-events", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--generated-at-utc")
    arguments = parser.parse_args(argv)
    generate_report(trace_events=arguments.trace_events, output_directory=arguments.output_directory,
                    generated_at_utc=arguments.generated_at_utc)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
