# PR203 — Canonical CompletedTradeEvent

`CompletedTradeEvent` is the sole supported input to passive production outcome integration. The production host constructs it only after the broker confirms a trade is closed and result values are final.

## Exact schema and encoding

The versioned fields are `decision_uuid`, `execution_context_uuid`, `order_ticket`, `deal_ticket`, `position_ticket`, `open_time`, `close_time`, `capture_time`, `symbol`, `direction`, `volume`, `entry_price`, `exit_price`, `exit_reason`, `gross_profit`, `net_profit`, `commission`, `swap`, `event_uuid`, `sha256_digest`, `replay_identity`, and `contract_version`.

Times are UTC ISO-8601 with six fractional digits and `Z`, ordered `open_time <= close_time <= capture_time`. JSON is UTF-8, compact, and lexicographically key-sorted; NaN and infinity are forbidden.

`event_uuid` is UUIDv5 over replay identity and the three tickets. `sha256_digest` is the lowercase SHA-256 of the canonical object with only `sha256_digest` omitted. The stable UUID makes repeat publication a duplicate even if capture time changes.

The frozen, slotted object validates the full contract. The host publisher registers identity before notifying passive observers and rejects any second event for that completed-trade identity.
