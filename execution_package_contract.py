"""Owned schema for the decision-to-executor execution package boundary."""

EXECUTION_PACKAGE_SCHEMA_VERSION = "1.0"
EXECUTABLE_DECISION_LIFECYCLE = "NORMAL_TRADE"
EXECUTABLE_DECISION = "TRADE"
EXECUTABLE_STATES = frozenset({
    "EXECUTE_AGGRESSIVE", "EXECUTE_NORMAL", "EXECUTE_CAUTIOUS",
})
EXECUTION_PACKAGE_FIELDS = (
    "execution_uuid", "decision_uuid", "market_sequence", "heartbeat_unix",
    "producer", "producer_version", "schema_version", "source_uuid", "symbol",
    "direction", "confidence", "risk_profile", "lot_size", "entry", "sl", "tp",
    "management_profile", "execution_timestamp",
)
