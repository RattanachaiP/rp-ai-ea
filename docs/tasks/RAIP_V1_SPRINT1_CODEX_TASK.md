# RAIP V1 — Sprint 1 Codex Implementation Task

**Project:** RP Autonomous Intelligence Platform (RAIP)  
**Sprint:** V1 Foundation — Passive Trade Intelligence Collection  
**Status:** Approved for implementation  
**Architecture Authority:** Rattanachai Pahtaradiloak  

## 1. Mandatory Pre-Read

Before implementation, Codex must read and comply with:

1. `ARCHITECTURE_RULES.md`
2. `CURRENT_SYSTEM_STATE.md`
3. `DECISION_FLOW_MAP.md`
4. `EMERGENCY_PATCH_POLICY.md`

If any instruction in this task conflicts with those documents, stop and report the conflict. Do not infer ownership.

## 2. Objective

Implement a **strictly passive, append-only observation layer** that collects completed-trade evidence for later review.

Sprint 1 must:

- record normalized lifecycle events;
- build one immutable trade snapshot after a trade is closed;
- generate a deterministic daily summary from stored snapshots;
- never modify decision, execution, exit, recovery, risk, or broker behavior;
- never create, cancel, amend, close, or influence any order;
- never manufacture trading authority.

## 3. Non-Goals

Do **not** implement in this sprint:

- self-learning;
- automatic threshold changes;
- strategy recommendations;
- pattern discovery;
- proposal generation;
- recovery logic;
- dashboard UI;
- database server;
- LLM/API calls;
- direct MT5 execution integration beyond reading already-published artifacts or exported closed-trade records.

## 4. Ownership Boundary

RAIP V1 is an **observer only**.

It may own:

- observation event serialization;
- snapshot normalization;
- review data persistence;
- deterministic report aggregation;
- schema validation for RAIP-owned files.

It must not own:

- market analysis;
- bias or direction;
- trade permission;
- entry timing;
- position sizing;
- exit authority;
- recovery authority;
- broker safety;
- order execution;
- production configuration changes.

## 5. Proposed Repository Structure

```text
review_engine/
├── __init__.py
├── collector/
│   ├── __init__.py
│   ├── event_collector.py
│   └── event_types.py
├── snapshots/
│   ├── __init__.py
│   ├── trade_snapshot_builder.py
│   └── snapshot_repository.py
├── reports/
│   ├── __init__.py
│   └── daily_review_builder.py
├── schemas/
│   ├── event.schema.json
│   ├── trade_snapshot.schema.json
│   └── daily_review.schema.json
├── validation/
│   ├── __init__.py
│   └── schema_validator.py
└── tests/
    ├── test_event_collector.py
    ├── test_trade_snapshot_builder.py
    ├── test_snapshot_repository.py
    ├── test_daily_review_builder.py
    └── test_observer_boundary.py

docs/
├── RAIP_V1_ARCHITECTURE.md
├── RAIP_EVENT_CONTRACT.md
├── RAIP_TRADE_SNAPSHOT_CONTRACT.md
└── RAIP_DATA_RETENTION_POLICY.md
```

Use the existing repository conventions if they differ. Do not duplicate an existing canonical utility.

## 6. Storage Layout

Default output root:

```text
D:\RP_AI_EA\review_data\
```

Logical layout:

```text
review_data/
├── events/YYYY/MM/DD/events.jsonl
├── snapshots/YYYY/MM/DD/trade_<trade_id>.json
├── daily/YYYY/MM/DD/daily_review.json
├── rejected/YYYY/MM/DD/
└── runtime/collector_state.json
```

Requirements:

- JSONL for events; one valid JSON object per line.
- One immutable JSON file per completed trade snapshot.
- Atomic write: write to `.tmp`, flush, `fsync` where supported, then rename.
- Existing snapshot files must never be silently overwritten.
- Duplicate `trade_id` input must return an idempotent result or a documented conflict; never create two contradictory snapshots.
- Invalid input must be quarantined under `rejected/` with a machine-readable reason.

## 7. Event Contract

Required event envelope:

```json
{
  "schema_version": "1.0.0",
  "event_id": "uuid",
  "event_type": "TRADE_CLOSED",
  "occurred_at_utc": "2026-07-22T10:00:00.000Z",
  "observed_at_utc": "2026-07-22T10:00:00.250Z",
  "source_module": "executor_export",
  "source_version": "unknown",
  "symbol": "XAUUSD",
  "account_id_hash": "sha256-or-null",
  "trade_id": "string-or-null",
  "position_id": "string-or-null",
  "series_id": "string-or-null",
  "candidate_id": "string-or-null",
  "sequence_id": "string-or-null",
  "correlation_id": "string-or-null",
  "payload": {},
  "integrity": {
    "payload_sha256": "hex"
  }
}
```

Allowed Sprint 1 event types:

- `DECISION_OBSERVED`
- `ENTRY_REQUEST_OBSERVED`
- `ORDER_FILL_OBSERVED`
- `POSITION_UPDATE_OBSERVED`
- `EXIT_REQUEST_OBSERVED`
- `TRADE_CLOSED`
- `SNAPSHOT_CREATED`
- `SNAPSHOT_REJECTED`
- `DAILY_REVIEW_CREATED`

The naming deliberately uses **OBSERVED** where RAIP is not the owner.

## 8. Trade Snapshot Contract

Minimum required fields:

```json
{
  "schema_version": "1.0.0",
  "snapshot_id": "uuid",
  "created_at_utc": "2026-07-22T10:01:00.000Z",
  "trade_identity": {
    "trade_id": "string",
    "position_id": "string-or-null",
    "series_id": "string-or-null",
    "symbol": "XAUUSD",
    "side": "BUY",
    "volume": 0.01
  },
  "timeline": {
    "decision_at_utc": null,
    "entry_requested_at_utc": null,
    "filled_at_utc": "2026-07-22T09:30:00.000Z",
    "closed_at_utc": "2026-07-22T10:00:00.000Z",
    "duration_seconds": 1800
  },
  "decision_context": {
    "candidate_id": null,
    "sequence_id": null,
    "bias": null,
    "decision": null,
    "execution_state": null,
    "confidence": null,
    "veto_code": null,
    "reason_codes": []
  },
  "market_context": {
    "market_mode": null,
    "market_state": null,
    "session": null,
    "atr": null,
    "rsi": null,
    "macd_histogram": null,
    "bb_state": null,
    "source_snapshot_timestamp_utc": null
  },
  "execution_context": {
    "requested_price": null,
    "entry_price": 0.0,
    "exit_price": 0.0,
    "spread_points_at_entry": null,
    "slippage_points": null,
    "commission": 0.0,
    "swap": 0.0
  },
  "outcome": {
    "gross_profit": 0.0,
    "net_profit": 0.0,
    "profit_points": null,
    "r_multiple": null,
    "mae_points": null,
    "mfe_points": null,
    "exit_reason": null
  },
  "data_quality": {
    "completeness_ratio": 0.0,
    "missing_fields": [],
    "warnings": [],
    "source_event_count": 0
  },
  "provenance": {
    "source_event_ids": [],
    "builder_version": "1.0.0",
    "snapshot_sha256": "hex"
  }
}
```

Rules:

- Missing optional evidence is represented as `null`; it must not be guessed.
- Side must be `BUY` or `SELL`.
- Timestamps must be UTC ISO-8601.
- Financial values must use consistent account currency units.
- `net_profit = gross_profit + commission + swap` only if the source system uses signed costs; otherwise preserve source semantics and document them.
- MAE/MFE must remain `null` unless reliable price-path evidence exists.
- No heuristic labels such as “good entry” or “bad exit” in Sprint 1.

## 9. Daily Review Contract

Sprint 1 daily reporting is factual aggregation only:

```json
{
  "schema_version": "1.0.0",
  "date_utc": "2026-07-22",
  "generated_at_utc": "2026-07-23T00:01:00.000Z",
  "scope": {
    "symbols": ["XAUUSD"],
    "trade_count": 0,
    "complete_snapshot_count": 0,
    "incomplete_snapshot_count": 0
  },
  "performance": {
    "wins": 0,
    "losses": 0,
    "breakeven": 0,
    "win_rate": null,
    "gross_profit": 0.0,
    "net_profit": 0.0,
    "profit_factor": null,
    "average_win": null,
    "average_loss": null,
    "average_duration_seconds": null
  },
  "direction": {
    "buy_trades": 0,
    "sell_trades": 0,
    "buy_net_profit": 0.0,
    "sell_net_profit": 0.0
  },
  "data_quality": {
    "average_completeness_ratio": 0.0,
    "missing_field_counts": {},
    "warnings": []
  },
  "provenance": {
    "snapshot_ids": [],
    "builder_version": "1.0.0",
    "report_sha256": "hex"
  }
}
```

No recommendation or self-improvement proposal is permitted in Sprint 1.

## 10. Runtime Behavior

- Collector must fail closed **for RAIP only**: a RAIP failure must not block or delay trading.
- All RAIP errors must be logged separately.
- Trading modules must not wait for RAIP acknowledgment.
- RAIP may consume copies of exported artifacts; it must not lock canonical trading files.
- Polling frequency must be configurable and conservative.
- Reprocessing the same closed trade must be idempotent.
- Restart must resume safely from `collector_state.json`.

## 11. Configuration

Provide a configuration file or typed configuration object with at least:

- `enabled`
- `review_data_root`
- `poll_interval_seconds`
- `source_paths`
- `symbols`
- `log_level`
- `schema_strict_mode`
- `quarantine_invalid_records`

Default `enabled` should be `false` until explicitly deployed and configured.

## 12. Security and Privacy

- Do not store broker credentials.
- Do not store personal names.
- Hash or omit account numbers.
- Never write secrets to logs.
- Use normalized paths and reject path traversal.

## 13. Tests and Acceptance Criteria

Implementation is acceptable only when all of the following pass:

1. A valid `TRADE_CLOSED` event produces exactly one valid snapshot.
2. Replaying the same event does not create a contradictory duplicate.
3. Missing optional fields remain `null` and are listed under `data_quality.missing_fields`.
4. Invalid JSON is quarantined without affecting trading files.
5. A simulated disk/write failure does not propagate into the trading process.
6. Atomic writes leave no partially readable final JSON file.
7. Daily aggregation is deterministic for the same snapshot set.
8. Profit-factor division-by-zero cases return `null`, not an exception.
9. All timestamps are normalized to UTC.
10. Observer-boundary test proves the RAIP package contains no order-send, position-close, decision mutation, threshold mutation, or deployment functions.
11. Existing repository tests remain green.
12. Python compilation/linting/type checks used by the repository pass.

## 14. Required Documentation

Codex must document:

- exact source artifacts consumed;
- how `trade_id` and correlations are resolved;
- signed commission/swap semantics;
- restart/idempotency behavior;
- data-loss limitations;
- enable/disable and rollback procedure;
- proof that RAIP cannot affect the trading path.

## 15. PR Requirements

Create one branch and one PR for Sprint 1 only.

Suggested branch:

```text
codex/raip-v1-passive-trade-collector
```

Suggested PR title:

```text
RAIP V1: add passive trade event collection and immutable snapshots
```

PR description must include:

- architecture boundary statement;
- file list;
- data flow;
- test evidence;
- failure isolation evidence;
- deployment disabled by default;
- rollback instructions;
- unresolved assumptions.

## 16. Stop Conditions

Stop and request architecture clarification if:

- no reliable closed-trade source can be identified;
- trade IDs are not stable across source artifacts;
- implementation would require changing executor authority;
- canonical trading files would need to be locked or rewritten;
- commission/swap signs cannot be determined;
- existing architecture documents conflict with this specification.

## 17. Definition of Done

Sprint 1 is done when RAIP can passively produce validated, immutable trade snapshots and a deterministic daily factual summary from real closed-trade evidence, while remaining provably unable to influence live trading.
