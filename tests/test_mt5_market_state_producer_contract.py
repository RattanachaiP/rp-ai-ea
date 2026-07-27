from pathlib import Path
import re


PRODUCER = Path("mt5/RP_Market_State_Writer_V13_FULL_LOGIC_ATOMIC_WRITE.mq5")


def test_canonical_mt5_writer_owns_pr212_identity():
    source = PRODUCER.read_text(encoding="utf-8")
    expected = {
        "MARKET_STATE_PRODUCER": "RP_AI_MT5_MARKET_STATE",
        "MARKET_STATE_PRODUCER_VERSION": "V1",
        "MARKET_STATE_SCHEMA_VERSION": "1.0",
        "MARKET_STATE_SOURCE_UUID": "dc3777c6-cf0d-5a7b-bd58-8a5c44568475",
    }

    for constant, value in expected.items():
        assert len(re.findall(rf"^#define {constant}[ \t]", source, re.MULTILINE)) == 1
        assert f'"{value}"' in source

    for field, constant in (
        ("producer", "MARKET_STATE_PRODUCER"),
        ("producer_version", "MARKET_STATE_PRODUCER_VERSION"),
        ("schema_version", "MARKET_STATE_SCHEMA_VERSION"),
        ("source_uuid", "MARKET_STATE_SOURCE_UUID"),
    ):
        assert f'\\"{field}\\":\\"" + {constant}' in source


def test_identity_cannot_be_injected_at_publication_boundary():
    source = PRODUCER.read_text(encoding="utf-8")
    signature = source.split("string BuildMarketStateJson(", 1)[1].split(")", 1)[0]
    assert "producer" not in signature
    assert "schema_version" not in signature
    assert "source_uuid" not in signature
