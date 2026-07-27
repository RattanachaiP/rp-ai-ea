import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import sys
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from runtime.governed_execution_package import (
    DecisionContextLineage, ExecutionPackageBuilder, GovernedPackageError,
    GovernedRecommendation,
)
from runtime.market_state_reader import GovernedMarketStateReader, MarketStateReaderError


NOW = 2_000_000_000


def market_state(**changes):
    values = {
        "producer": "RP_AI_MT5_MARKET_STATE", "producer_version": "V1",
        "schema_version": "1.0",
        "source_uuid": "dc3777c6-cf0d-5a7b-bd58-8a5c44568475",
        "symbol": "XAUUSD", "timeframe": "M5",
        "time_sync": "RP_TIME_SYNC_STANDARD_V1", "heartbeat_unix": NOW,
        "sequence_id": 10, "server_time": "2033.05.18 03:33:20",
        "bar_time": "2033.05.18 03:30:00", "bid": 2000.1, "ask": 2000.2,
        "ma50": 1.0, "ma90": 1.0, "ma200": 1.0, "rsi": 50.0,
        "macd_main": 0.1, "macd_signal": 0.1, "macd_hist": 0.0,
        "bb_upper": 2.0, "bb_middle": 1.0, "bb_lower": 0.0,
        "bb3_upper": 3.0, "bb3_middle": 1.0, "bb3_lower": -1.0,
        "bb4_upper": 4.0, "bb4_middle": 1.0, "bb4_lower": -2.0,
        "buyScore": 2, "sellScore": 1,
    }
    values.update(changes)
    return values


def publish(path, values=None):
    path.write_text(json.dumps(values or market_state()), encoding="utf-8")


def test_reader_validates_canonical_state_and_context_has_exact_lineage(tmp_path):
    path = tmp_path / "market_state.json"
    publish(path)
    reader = GovernedMarketStateReader(clock=lambda: NOW)
    state = reader.read(path)
    context = DecisionContextLineage.from_market_state(state)

    assert (context.market_state_uuid, context.sequence_id, context.timestamp,
            context.symbol, context.timeframe, context.producer) == (
        state.market_state_uuid, 10, state.timestamp, "XAUUSD", "M5",
        "RP_AI_MT5_MARKET_STATE")
    assert reader.last_diagnostic.status == "OK"
    assert reader.last_diagnostic.render().startswith("[READER]\nProducer=")


@pytest.mark.parametrize(("mutation", "reason"), (
    (lambda value: value.pop("symbol"), "MISSING_REQUIRED_FIELDS"),
    (lambda value: value.update(producer="OTHER"), "UNKNOWN_PRODUCER"),
    (lambda value: value.update(schema_version="2.0"), "UNSUPPORTED_SCHEMA_VERSION"),
    (lambda value: value.update(heartbeat_unix=NOW + 3), "FUTURE_HEARTBEAT"),
    (lambda value: value.update(heartbeat_unix=NOW - 31), "STALE_HEARTBEAT"),
))
def test_reader_rejects_invalid_governed_publications(tmp_path, mutation, reason):
    values = market_state()
    mutation(values)
    path = tmp_path / "market_state.json"
    publish(path, values)
    reader = GovernedMarketStateReader(clock=lambda: NOW)
    with pytest.raises(MarketStateReaderError, match=reason):
        reader.read(path)
    assert reader.last_diagnostic.status == "REJECTED"


def test_reader_rejects_partial_invalid_utf8_and_sequence_rollback(tmp_path):
    path = tmp_path / "market_state.json"
    reader = GovernedMarketStateReader(clock=lambda: NOW)
    path.write_bytes(b'{"producer":')
    with pytest.raises(MarketStateReaderError, match="INVALID_OR_PARTIAL_JSON"):
        reader.read(path)
    path.write_bytes(b"\xff")
    with pytest.raises(MarketStateReaderError, match="INVALID_UTF8"):
        reader.read(path)
    publish(path)
    reader.read(path)
    publish(path, market_state(sequence_id=9))
    with pytest.raises(MarketStateReaderError, match="SEQUENCE_ROLLBACK"):
        reader.read(path)


def recommendation(context):
    return GovernedRecommendation(str(uuid4()), context.context_uuid, str(uuid4()),
        str(uuid4()), 0.8, "BUY", "BALANCED", {"policy": "PR223"},
        "2033-05-18T03:33:20Z")


def test_complete_package_is_immutable_deterministic_and_validated(tmp_path):
    path = tmp_path / "market_state.json"
    publish(path)
    context = DecisionContextLineage.from_market_state(
        GovernedMarketStateReader(clock=lambda: NOW).read(path))
    rec = recommendation(context)
    identities = [str(uuid4()) for _ in range(4)]
    kwargs = dict(recommendation=rec, parent_uuid=identities[0],
        readiness_uuid=identities[1], environment_uuid=identities[2],
        feasibility_uuid=identities[3], repository_digest="a" * 64,
        snapshot_digest="b" * 64,
        readiness_timestamp="2033-05-18T03:33:21Z",
        environment_timestamp="2033-05-18T03:33:22Z",
        feasibility_timestamp="2033-05-18T03:33:23Z")
    package = ExecutionPackageBuilder.build(**kwargs)
    assert ExecutionPackageBuilder.build(**kwargs) == package
    ExecutionPackageBuilder.validate(package, expected_parent_uuid=identities[0],
        expected_repository_digest="a" * 64, expected_snapshot_digest="b" * 64,
        expected_activation_uuid=rec.activation_uuid)
    assert package.diagnostics().startswith("[PACKAGE]\nUUID=")
    with pytest.raises(FrozenInstanceError):
        package.repository_digest = "c" * 64


def test_package_rejects_incomplete_lineage_digest_snapshot_and_order(tmp_path):
    path = tmp_path / "market_state.json"
    publish(path)
    context = DecisionContextLineage.from_market_state(
        GovernedMarketStateReader(clock=lambda: NOW).read(path))
    rec = recommendation(context)
    ids = [str(uuid4()) for _ in range(4)]
    args = dict(recommendation=rec, parent_uuid=ids[0], readiness_uuid=ids[1],
        environment_uuid=ids[2], feasibility_uuid=ids[3],
        repository_digest="a" * 64, snapshot_digest="b" * 64,
        readiness_timestamp="2033-05-18T03:33:21Z",
        environment_timestamp="2033-05-18T03:33:22Z",
        feasibility_timestamp="2033-05-18T03:33:23Z")
    with pytest.raises(GovernedPackageError, match="MISSING_PACKAGE_IDENTITY"):
        ExecutionPackageBuilder.build(**{**args, "readiness_uuid": ""})
    with pytest.raises(GovernedPackageError, match="TIMESTAMP_ORDERING"):
        ExecutionPackageBuilder.build(**{**args,
            "environment_timestamp": "2033-05-18T03:33:19Z"})
    package = ExecutionPackageBuilder.build(**args)
    with pytest.raises(GovernedPackageError, match="DIGEST_MISMATCH"):
        ExecutionPackageBuilder.validate(package, expected_parent_uuid=ids[0],
            expected_repository_digest="c" * 64, expected_snapshot_digest="b" * 64,
            expected_activation_uuid=rec.activation_uuid)
    with pytest.raises(GovernedPackageError, match="MULTIPLE_ACTIVATION_LINEAGE"):
        ExecutionPackageBuilder.validate(package, expected_parent_uuid=ids[0],
            expected_repository_digest="a" * 64, expected_snapshot_digest="b" * 64,
            expected_activation_uuid=str(uuid4()))


def test_recommendation_rejects_missing_governance_metadata(tmp_path):
    path = tmp_path / "market_state.json"
    publish(path)
    context = DecisionContextLineage.from_market_state(
        GovernedMarketStateReader(clock=lambda: NOW).read(path))
    with pytest.raises(GovernedPackageError, match="INCOMPLETE_RECOMMENDATION"):
        replace(recommendation(context), governance_metadata={})
