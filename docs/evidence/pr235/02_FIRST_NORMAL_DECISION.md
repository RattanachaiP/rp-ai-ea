# PR235 First NORMAL Decision

`first_normal_decision.json` is created once, by atomic replacement, only after
a NORMAL publication has passed identity, schema, sequence, heartbeat,
producer, market-sequence, and market-source verification. Subsequent NORMAL
decisions cannot replace the evidence.

Evidence creation requires the complete governed publication contract,
including authoritative producer, producer version, schema version, lifecycle,
decision identity, fresh heartbeat, confidence, and matching accepted-market
sequence and source UUID. Incomplete legacy documents cannot activate the
runtime or create either first-decision evidence file.

No real MT5 `market_state.json` publication is available in this repository or
CI environment. Therefore this change contains no claimed production decision
and no fabricated evidence. The owning live prerequisite is the MT5 Market
State Writer; without it the canonical block is `NO_MARKET_STATE`.
