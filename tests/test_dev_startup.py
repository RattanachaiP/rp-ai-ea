"""PR240 development startup boundary tests."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(1, str(Path(__file__).parent / "learning"))

from runtime import dev_startup


def test_dev_startup_delegates_arguments_and_result_to_production(monkeypatch):
    calls = []
    monkeypatch.setattr(
        dev_startup.production_startup,
        "main",
        lambda argv=None: calls.append(argv) or "RUNNING",
    )

    assert dev_startup.main(["--observation-window", "1.0"]) == "RUNNING"
    assert calls == [["--observation-window", "1.0"]]


def test_dev_startup_has_no_direct_decision_engine_launch():
    source = Path(dev_startup.__file__).read_text(encoding="utf-8")

    assert "ai_decision_engine_xauusd_v26_execution_confidence_engine" not in source
    assert "production_startup.main(argv)" in source


def test_powershell_launcher_starts_established_demo_engine_directly():
    launcher = Path(__file__).parents[1] / "start_ai_runtime.ps1"
    source = launcher.read_text(encoding="utf-8")

    assert "$MyInvocation.MyCommand.Path" in source
    assert "Get-Command python" in source
    assert "from bridge.ai_decision_engine_xauusd_v26_execution_confidence_engine import FILE_PATH" in source
    assert "Test-Path -LiteralPath $MarketStatePath -PathType Leaf" in source
    assert "-m bridge.ai_decision_engine_xauusd_v26_execution_confidence_engine" in source
    assert "-m runtime.dev_startup" not in source
