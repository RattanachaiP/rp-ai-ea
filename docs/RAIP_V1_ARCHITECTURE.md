# RAIP V1 Architecture

RAIP is a disabled-by-default, append-only observer. It is an independent Python package and has no import from `bridge`, `runtime`, or `mt5`. It consumes copies of exported closed-trade records only, serializes events, creates immutable snapshots, and aggregates facts. It has no APIs for decisions, execution, orders, exits, recovery, risk, or deployment, so it cannot affect the trading path.

The configured source artifact is an exported `trade_memory.csv` closed-trade record (the existing runtime's documented evidence-only artifact). A deployment adapter must convert each exported row into the `TRADE_CLOSED` event contract; this sprint deliberately does not poll, lock, or rewrite that canonical source.
