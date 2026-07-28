import json
from pathlib import Path
import subprocess
import sys
from dataclasses import dataclass, field

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
    assert "GetLastError()==ERR_FILE_NOT_FOUND" not in source
    assert "#define RP_ERR_FILE_CANNOT_OPEN 5004" in source
    assert source.count("GetLastError()==RP_ERR_FILE_CANNOT_OPEN") == 2
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


def test_authoritative_state_and_result_use_fail_closed_replacement():
    source = SOURCE.read_text()
    assert 'bool ReplaceTextFailClosed(' in source
    assert 'FileMove(temporary,FILE_COMMON,path,FILE_COMMON|FILE_REWRITE)' in source
    assert 'FileIsExist(temporary,FILE_COMMON)' in source
    assert 'execution_uuid+"."+status' in source
    assert 'execution_uuid+".result"' in source
    assert 'ReplaceTextFailClosed(EXECUTION_RESULT_PATH,value' in source
    assert 'PersistTransition("UNKNOWN_OUTCOME"' in source
    assert 'RESULT_PERSIST_FAILED|retcode=%u|ticket=%I64u' in source


@dataclass
class PublicationModel:
    """Behavioral model of the MQL Common/Files publication primitive."""

    files: dict[str, str] = field(default_factory=dict)
    fail_write: bool = False
    fail_replace: bool = False
    journal: list[tuple[str, str]] = field(default_factory=list)
    state: str = "SUBMITTED"

    def replace(self, path: str, value: str, publication_id: str) -> bool:
        temporary = f"{path}.{publication_id}.tmp"
        if temporary in self.files:
            del self.files[temporary]
            return False
        if self.fail_write:
            return False
        self.files[temporary] = value
        if self.fail_replace:
            del self.files[temporary]
            return False
        self.files[path] = self.files.pop(temporary)
        return True

    def publish_result(self, execution_uuid: str, value: str, retcode: int, ticket: int) -> bool:
        if self.replace("execution_result.json", value, f"{execution_uuid}.result"):
            return True
        reason = f"RESULT_PERSIST_FAILED|retcode={retcode}|ticket={ticket}"
        self.journal.append(("UNKNOWN_OUTCOME", reason))
        self.state = "UNKNOWN_OUTCOME"
        return False


def test_temporary_write_failure_preserves_destination():
    model = PublicationModel({"execution_result.json": "old"}, fail_write=True)
    assert model.replace("execution_result.json", "new", f"{UUID1}.result") is False
    assert model.files == {"execution_result.json": "old"}


def test_replacement_failure_cleans_temp_and_preserves_destination():
    model = PublicationModel({"execution_result.json": "old"}, fail_replace=True)
    assert model.replace("execution_result.json", "new", f"{UUID1}.result") is False
    assert model.files == {"execution_result.json": "old"}


def test_stale_temp_collision_is_cleaned_and_publication_is_blocked():
    temp = f"execution_result.json.{UUID1}.result.tmp"
    model = PublicationModel({"execution_result.json": "old", temp: "stale"})
    assert model.replace("execution_result.json", "new", f"{UUID1}.result") is False
    assert model.files == {"execution_result.json": "old"}


def test_successful_replacement_publishes_complete_value():
    model = PublicationModel({"execution_result.json": "old"})
    assert model.replace("execution_result.json", "new", f"{UUID1}.result") is True
    assert model.files == {"execution_result.json": "new"}


def test_result_publication_failure_records_unknown_outcome_and_broker_facts():
    model = PublicationModel(fail_replace=True)
    assert model.publish_result(UUID1, "result", 10009, 238001) is False
    assert model.state == "UNKNOWN_OUTCOME"
    assert model.journal == [("UNKNOWN_OUTCOME", "RESULT_PERSIST_FAILED|retcode=10009|ticket=238001")]
