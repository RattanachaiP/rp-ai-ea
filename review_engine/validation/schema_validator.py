"""Small dependency-free validators for RAIP-owned persistence contracts."""
def validate_snapshot(value):
    required = ("schema_version", "snapshot_id", "trade_identity", "timeline", "outcome", "provenance")
    if not isinstance(value, dict) or any(key not in value for key in required): raise ValueError("INVALID_TRADE_SNAPSHOT")
    if value["trade_identity"].get("side") not in {"BUY", "SELL"}: raise ValueError("INVALID_SNAPSHOT_SIDE")
    return value
def validate_daily_review(value):
    if not isinstance(value, dict) or value.get("schema_version") != "1.0.0": raise ValueError("INVALID_DAILY_REVIEW")
    return value
