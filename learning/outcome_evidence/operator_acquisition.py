"""PR250 explicit operator acquisition and PR173 construction composition."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from learning.outcome_attribution import (KnowledgeOutcomeAttributionEngine,
                                          KnowledgeOutcomeAttributionRepository)
from .models import OutcomeEvidenceError, OutcomeEvidenceManifest
from .repository import OutcomeEvidenceRepository, build_evidence_record


def _read_manifest(path: Path) -> OutcomeEvidenceManifest:
    if not path.is_file():
        raise OutcomeEvidenceError("OUTCOME_EVIDENCE_FILE_MISSING",
                                   "supply one exact existing canonical evidence file path")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID",
                                   "supply valid UTF-8 JSON matching the PR250 schema") from exc
    return OutcomeEvidenceManifest.from_dict(value)


def validate(path: Path) -> dict:
    manifest = _read_manifest(path)
    report = KnowledgeOutcomeAttributionEngine().analyze([row.to_dict() for row in manifest.evidence_rows])
    record = build_evidence_record(manifest, report.source_digest, report.replay_digest)
    return {"mode": "VALIDATE", "mutation_occurred": False, "rerun_safe": True,
            "prospective_evidence_uuid": record["evidence_uuid"],
            "manifest_digest": manifest.manifest_digest, "source_digest": report.source_digest,
            "replay_digest": report.replay_digest, "row_count": len(manifest.evidence_rows),
            "next_action": "import this exact file after operator review"}


def import_evidence(path: Path, base: Path) -> dict:
    preview = validate(path)
    manifest = _read_manifest(path)
    repository = OutcomeEvidenceRepository(base)
    record = build_evidence_record(manifest, preview["source_digest"], preview["replay_digest"])
    _, created = repository.save(record)
    return {"mode": "IMPORT", "mutation_occurred": created, "rerun_safe": True,
            "duplicate_replay": not created, "evidence_uuid": record["evidence_uuid"],
            "manifest_digest": manifest.manifest_digest, "source_digest": preview["source_digest"],
            "replay_digest": preview["replay_digest"],
            "next_action": "construct PR173 with this exact evidence_uuid when explicitly authorized"}


def inspect(base: Path, evidence_uuid: str | None = None) -> dict:
    repository = OutcomeEvidenceRepository(base)
    records = repository.inspect()
    if evidence_uuid is not None:
        record = repository.load(evidence_uuid)
        records = [item for item in records if item["evidence_uuid"] == record["evidence_uuid"]]
        if len(records) != 1:
            raise OutcomeEvidenceError("AMBIGUOUS_EVIDENCE_IDENTITY", "audit duplicate exact identities")
    return {"mode": "INSPECT", "mutation_occurred": False, "rerun_safe": True,
            "repository": str(repository.root), "record_count": len(records), "records": records,
            "next_action": "select one exact imported evidence UUID; no latest selection is available"}


def construct_pr173(base: Path, evidence_uuid: str) -> dict:
    evidence_repository = OutcomeEvidenceRepository(base)
    record = evidence_repository.load(evidence_uuid)
    manifest = OutcomeEvidenceManifest.from_dict(record["manifest"])
    rows = [row.to_dict() for row in manifest.evidence_rows]
    prospective = KnowledgeOutcomeAttributionEngine().analyze(rows)
    if (prospective.source_digest != record["source_digest"] or
            prospective.replay_digest != record["replay_digest"]):
        raise OutcomeEvidenceError(
            "PR173_RESULT_PROVENANCE_MISMATCH",
            "audit the imported evidence record before any PR173 persistence",
        )
    attribution_repository = KnowledgeOutcomeAttributionRepository(base)
    path = attribution_repository.path_for(prospective.attribution_uuid)
    existed_before = path.is_file()
    try:
        owner_result = KnowledgeOutcomeAttributionEngine(attribution_repository).analyze(rows)
    except Exception as exc:
        raise OutcomeEvidenceError("PR173_CONSTRUCTION_FAILED",
                                   "audit the imported record and retry the exact evidence UUID",
                                   mutation_occurred=path.is_file() and not existed_before) from exc
    try:
        persisted = attribution_repository.load(prospective.attribution_uuid)
    except Exception as exc:
        raise OutcomeEvidenceError(
            "PR173_RESULT_PROVENANCE_MISMATCH",
            "quarantine the persisted PR173 artifact and audit repository integrity",
            mutation_occurred=path.is_file() and not existed_before,
        ) from exc
    persisted_verified = (
        path.is_file()
        and owner_result.attribution_uuid == prospective.attribution_uuid
        and persisted.attribution_uuid == prospective.attribution_uuid
        and persisted.source_digest == record["source_digest"]
        and persisted.replay_digest == record["replay_digest"]
        and persisted.to_dict() == owner_result.to_dict()
    )
    if not persisted_verified:
        raise OutcomeEvidenceError("PR173_RESULT_PROVENANCE_MISMATCH",
                                   "quarantine the persisted PR173 artifact and audit exact provenance",
                                   mutation_occurred=path.is_file() and not existed_before)
    created = not existed_before and path.is_file()
    duplicate_replay = existed_before and path.is_file()
    return {"mode": "CONSTRUCT-PR173", "mutation_occurred": created, "rerun_safe": True,
            "duplicate_replay": duplicate_replay, "evidence_uuid": evidence_uuid,
            "attribution_uuid": persisted.attribution_uuid, "source_digest": persisted.source_digest,
            "replay_digest": persisted.replay_digest,
            "next_action": "use this exact attribution UUID in the PR174 owner workflow"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PR250 governed outcome-evidence acquisition")
    parser.add_argument("--base", default="learning_data")
    commands = parser.add_subparsers(dest="mode", required=True)
    p = commands.add_parser("inspect"); p.add_argument("--evidence-uuid")
    p = commands.add_parser("validate"); p.add_argument("--input", required=True)
    p = commands.add_parser("import"); p.add_argument("--input", required=True)
    p = commands.add_parser("construct-pr173"); p.add_argument("--evidence-uuid", required=True)
    args = parser.parse_args(argv)
    try:
        if args.mode == "inspect":
            result = inspect(Path(args.base), args.evidence_uuid)
        elif args.mode == "validate":
            result = validate(Path(args.input))
        elif args.mode == "import":
            result = import_evidence(Path(args.input), Path(args.base))
        else:
            result = construct_pr173(Path(args.base), args.evidence_uuid)
    except OutcomeEvidenceError as exc:
        parser.exit(2, f"OUTCOME_EVIDENCE_FAILED {exc}\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
