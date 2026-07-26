# PR203 — Canonical CompletedTradeEvent

`CompletedTradeEvent` is the sole supported input to passive production outcome integration. The production host constructs it only after the broker confirms a trade is closed and result values are final.

## Exact schema and encoding

The versioned fields include the required identity, timing, execution, result,
and integrity fields plus the broker-confirmed facts required by PR201:
`publication_uuid`, `publication_timestamp`, `consumer_acceptance_timestamp`,
`activation_timestamp`, `order_send_timestamp`, `stop_loss`, `take_profit`,
`broker_response_code`, `account_number`, `server_name`,
`maximum_favorable_excursion`, and `maximum_adverse_excursion`.

Publication identity and timestamp are jointly optional. Excursion values are
individually optional. All other broker facts are required; the host must not
substitute synthetic defaults for unavailable values.

Times are UTC ISO-8601 with six fractional digits and `Z`, ordered `open_time <= close_time <= capture_time`. JSON is UTF-8, compact, and lexicographically key-sorted; NaN and infinity are forbidden.

`event_uuid` is UUIDv5 over replay identity and the three tickets. `sha256_digest` is the lowercase SHA-256 of the canonical object with only `sha256_digest` omitted. The stable UUID makes repeat publication a duplicate even if capture time changes.

The frozen, slotted object validates the full contract. The host publisher registers identity before notifying passive observers and rejects any second event for that completed-trade identity.
