from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "mt5/canonical/RP_AI_Governed_Executor.mq5"


def executor():
    return SOURCE.read_text(encoding="utf-8")


def test_canonical_executor_consumes_only_the_execution_package():
    source = executor()
    assert 'execution_package.json"' in source
    assert 'decision.json"' not in source
    for field in ("execution_uuid", "decision_uuid", "producer", "producer_version",
                  "schema_version", "heartbeat_unix", "market_sequence"):
        assert f'ReadField' in source and f'json,"{field}"' in source
    assert 'PACKAGE_PRODUCER "RP_AI_RUNTIME"' in source
    assert 'PACKAGE_PRODUCER_VERSION "27.5"' in source
    assert 'PACKAGE_SCHEMA_VERSION "1.0"' in source


def test_authority_is_fail_closed_and_strategy_free():
    source = executor()
    assert "RUNTIME_EXECUTION_STATE_UNVERIFIED" in source
    assert "ENTRY_PERMISSION_UNVERIFIED" in source
    assert "ORDERSEND_PERMISSION_UNVERIFIED" in source
    assert "direction alone is never treated as authority" in source
    for forbidden in ("confidence >=", "confidence <", "lot =", "risk_profile ==", "signal"):
        assert forbidden not in source


def test_duplicate_authority_survives_package_deletion_and_non_adjacent_replay():
    source = executor()
    assert 'executor_state.json"' in source
    assert 'executor_accepted_uuids.log"' in source
    assert "WasExecutionUuidAccepted(execution_uuid" in source
    assert "AppendAcceptedUuid(execution_uuid)" in source
    assert "DUPLICATE_EXECUTION_UUID" in source
    assert source.index("AppendAcceptedUuid(execution_uuid)") < source.index("OrderSend(request,result)")


def test_broker_validation_precedes_real_order_send():
    source = executor()
    checks = ("SYMBOL_UNAVAILABLE", "TRADING_DISABLED", "MARKET_CLOSED", "VOLUME_INVALID",
              "MARGIN_INSUFFICIENT", "STOP_LEVELS_INVALID")
    for check in checks:
        assert check in source
    assert source.index("BrokerValidation(symbol") < source.index("OrderSend(request,result)")
    assert "MqlTradeRequest request" in source and "MqlTradeResult result" in source


def test_result_and_structured_trace_are_durable_contracts():
    source = executor()
    assert 'execution_result.json"' in source
    for field in ("execution_uuid", "ticket", "retcode", "broker_time", "execution_status"):
        assert f'\\"{field}\\"' in source
    assert 'executor_trace.log"' in source
    for stage in ("Package accepted", "Validation", "Broker validation", "OrderSend", "Execution result"):
        assert f'"{stage}"' in source
    for owner in ("PACKAGE", "VALIDATION", "BROKER", "ORDERSEND", "POSITION"):
        assert f'"{owner}"' in source
