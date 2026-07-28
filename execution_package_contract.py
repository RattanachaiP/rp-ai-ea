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

# Executor-owned consumption window. This is intentionally distinct from the
# Runtime decision heartbeat and assembler lineage-age limits.
EXECUTOR_PACKAGE_MAXIMUM_AGE_SECONDS = 5

# Ordered MT5 scalar types used to generate the MQL contract include. The
# package remains exactly EXECUTION_PACKAGE_FIELDS; no executor-local field is
# added to the Runtime/assembler boundary.
EXECUTION_PACKAGE_MQL_TYPES = (
    "STRING", "STRING", "INTEGER", "INTEGER", "STRING", "STRING", "STRING",
    "STRING", "STRING", "STRING", "NUMBER", "STRING", "NUMBER", "NUMBER",
    "NUMBER", "NUMBER", "STRING", "STRING",
)
