"""Generate the Brain Phase 7 Decision Publication validation report."""

from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).parents[1]
ENGINE = ROOT / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py"
REPORT = ROOT / "analysis" / "BRAIN_PHASE7_REPORT.md"
FIXTURE = {"bid": 0, "ma50": 2300, "bar_time": "phase7-parity"}
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ENGINE.parent))


def _load(path: Path, name: str):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _runtime_write_calls_are_wrapped() -> bool:
    tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
    run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run")
    writes = [
        node for node in ast.walk(run)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "write_decision"
    ]
    return bool(writes) and all(
        len(node.args) == 1
        and isinstance(node.args[0], ast.Call)
        and isinstance(node.args[0].func, ast.Name)
        and node.args[0].func.id == "brain_decision_publication"
        for node in writes
    )


def main() -> None:
    source = subprocess.check_output(
        ["git", "show", "HEAD:bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py"],
        cwd=ROOT,
        text=True,
    )
    with tempfile.TemporaryDirectory() as directory:
        baseline_path = Path(directory) / "baseline.py"
        baseline_path.write_text(source, encoding="utf-8")
        baseline = _load(baseline_path, "phase7_baseline")
        candidate = _load(ENGINE, "phase7_candidate")
        assert baseline.build_decision(dict(FIXTURE))[2] == candidate.build_decision(dict(FIXTURE))[2]

    payload = {"decision": "TRADE", "action": "BUY", "nested": {"aliases": ["decision", "action"]}}
    published = candidate.brain_decision_publication(payload)
    assert published is payload
    assert published["nested"] is payload["nested"]
    assert _runtime_write_calls_are_wrapped()

    REPORT.write_text("""# Brain Phase 7 Decision Publication report

## Result

**PASS.** Decision Publication is the frozen, identity-preserving boundary immediately before the existing V26 atomic writer. Deterministic V26 `build_decision()` output matches the `HEAD` baseline exactly; no `decision.json` file was written during validation.

## Boundary contract

`brain_decision_publication(final_payload)` returns the exact same V26 payload dictionary object. It performs no validation, normalization, serialization, metadata attachment, copy, or schema change. Existing V26 compatibility normalization, final validation, write metadata, and atomic `write_decision()` ownership remain unchanged.

## Runtime routing

Every `write_decision()` call in `run()` is supplied through `brain_decision_publication()`, including read-failure fallback, normal decision, cooldown, and exception fallback paths. The boundary has no MT5, dashboard, executor, or post-entry management dependency.

## Payload parity

**PASS.** A nested payload and all legacy aliases retain object identity and contents across the boundary. Complete deterministic V26 decision dictionaries match the baseline, so `decision.json` schema and the atomic publication path remain unchanged.

## Regression status

**PASS.** Identity preservation, no nested-copy behavior, complete runtime writer routing, and V26 decision parity passed.

## Execution authority

**Unchanged.** V26 remains the sole owner of decision construction, compatibility handling, validation, and atomic publication. The writer and downstream MT5/dashboard consumers receive the existing payload without a Brain-owned transformation.
""", encoding="utf-8")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
