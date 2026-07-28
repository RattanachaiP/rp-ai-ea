import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mt5/canonical/RP_AI_Governed_Executor.mq5"
INCLUDE = ROOT / "mt5/canonical/RP_ExecutionPackageContract.mqh"
FIELDS = (
    "execution_uuid", "decision_uuid", "market_sequence", "heartbeat_unix", "producer",
    "producer_version", "schema_version", "source_uuid", "symbol", "direction", "confidence",
    "risk_profile", "lot_size", "entry", "sl", "tp", "management_profile", "execution_timestamp",
)
UUID1 = "00000000-0000-4000-8000-000000000237"
UUID2 = "00000000-0000-4000-8000-000000000238"


def package(**changes):
    value = dict(zip(FIELDS, (UUID1, UUID2, 42, 1000, "RP_AI_RUNTIME", "27.5", "1.0", UUID1,
        "XAUUSD", "BUY", 80.0, "Balanced", 0.1, 2400.0, 2395.0, 2410.0, "SCALP", "2026-07-28T00:00:00Z")))
    value.update(changes)
    return value


def strict_load(payload):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_FIELD")
            result[key] = value
        return result
    value = json.loads(payload, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    if type(value) is not dict or tuple(value) != FIELDS:
        raise ValueError("EXACT_FIELD_SET")
    string_fields = {0, 1, 4, 5, 6, 7, 8, 9, 11, 16, 17}
    integer_fields = {2, 3}
    for index, field in enumerate(FIELDS):
        if index in string_fields and type(value[field]) is not str:
            raise TypeError(field)
        if index in integer_fields and type(value[field]) is not int:
            raise TypeError(field)
        if index not in string_fields | integer_fields and type(value[field]) not in (int, float):
            raise TypeError(field)
    return value


def test_generated_contract_is_reproducible_and_has_one_authority():
    before = INCLUDE.read_bytes()
    subprocess.run([sys.executable, "tools/generate_execution_package_mql.py"], cwd=ROOT, check=True)
    assert INCLUDE.read_bytes() == before
    source = SOURCE.read_text()
    assert '#include "RP_ExecutionPackageContract.mqh"' in source
    assert "#define PACKAGE_SCHEMA_VERSION" not in source
    assert "RP_EXECUTOR_PACKAGE_MAX_AGE_SECONDS" in source


@pytest.mark.parametrize("payload", [
    '{"execution_uuid":"a","execution_uuid":"b"}',
    json.dumps(package()) + " trailing",
    json.dumps(package()).replace('"XAUUSD"', '"\\x"'),
    json.dumps(package()).replace('"market_sequence": 42', '"market_sequence": 01'),
])
def test_strict_json_rejects_duplicate_trailing_escape_and_number(payload):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        strict_load(payload)


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(unknown=True),
    lambda p: p.pop("producer"),
    lambda p: p.update(market_sequence="42"),
])
def test_exact_contract_rejects_unknown_missing_and_wrong_type(mutation):
    value = package(); mutation(value)
    with pytest.raises((ValueError, TypeError)):
        strict_load(json.dumps(value))


def test_mql_enforces_freshness_duplicates_monotonicity_and_corruption():
    source = SOURCE.read_text()
    for token in ("STALE_PACKAGE", "DUPLICATE_EXECUTION_UUID", "NON_MONOTONIC_MARKET_SEQUENCE",
                  "EXECUTOR_STATE_CORRUPT_OR_INACCESSIBLE", "EXECUTOR_JOURNAL_CORRUPT_OR_INACCESSIBLE"):
        assert token in source
    assert "ERR_FILE_NOT_FOUND" in source and "5004" not in source
    assert 'execution_package.json"' in source and 'decision.json"' not in source


def test_authoritative_crash_journal_and_truthful_broker_classification():
    source = SOURCE.read_text()
    for state in ("ACCEPTED", "SUBMITTING", "SUBMITTED", "REJECTED", "UNKNOWN_OUTCOME"):
        assert f'"{state}"' in source
    assert source.index('PersistTransition("SUBMITTING"') < source.index("OrderSend(request,result)")
    assert "TRADE_RETCODE_DONE" in source and "TRADE_RETCODE_DONE_PARTIAL" in source
    assert "TRADE_RETCODE_PLACED" in source and 'result_status="PENDING"' in source
    assert 'result_status=api_result ? "BROKER_REJECTED" : "ORDERSEND_FAILED"' in source


def test_state_result_trace_and_failure_paths_are_separate():
    source = SOURCE.read_text()
    for field in ("schema_version", "last_market_sequence", "last_execution_uuid", "last_decision_uuid",
                  "last_execution_status", "updated_at"):
        assert f'\\"{field}\\"' in source
    assert 'executor_journal.log"' in source and 'executor_trace.log"' in source
    assert 'execution_result.json"' in source
    assert "RESULT_PERSIST_FAILED" in source and "EXECUTOR_TRACE_OPEN_FAILED" in source
    for owner in ("PACKAGE", "VALIDATION", "BROKER", "ORDERSEND", "POSITION"):
        assert f'"{owner}"' in source
