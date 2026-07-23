# RAIP V14.1 — Learning Engine Core

V14.1 is an offline, asynchronous, immutable-materialization domain. It consumes only
the V10 `learning_candidate_registry.json` and only accepts records that are `QUALIFIED`
under the explicit `learning_engine_policy.json`. It writes V14.1 `learning_material.json`
artefacts below `learning_engine/materials/`.

V14.1 is deliberately **not training**: it cannot change model weights, thresholds,
recommendations, governance, executive decisions, runtime payloads, deployment, or live
trading. Its output is passive, traceable learning material for future architecture-approved
consumers. Publication is atomic and write-once; replaying a registry produces the same
material identity and does not overwrite the historical artefact.

Input registry failures and unsupported schema versions fail closed for V14.1 only. The
coordinator uses a single worker and has no imports from runtime or execution packages, so
failure or delay cannot block trading.
