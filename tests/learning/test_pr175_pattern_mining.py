from dataclasses import replace
import json
from uuid import uuid4

import pytest

from learning.learning_policy import GovernedLearningPolicyEngine
from learning.outcome_attribution import KnowledgeOutcomeAttributionEngine
from learning.pattern_mining import (ApprovedPatternMiningEvidenceEnvelope, ApprovedPatternMiningSample,
    PatternMiningConfig, PatternMiningEngine, PatternMiningError, PatternMiningReport, PatternMiningRepository)


def policy_and_evidence(values=(2.0, -1.0, 0.0), policy_uuid=None):
    knowledge_uuid = str(uuid4())
    rows = [{'knowledge_uuid': knowledge_uuid, 'knowledge_version': '1', 'timestamp': '2026-07-25T00:00:00Z',
             'replay_digest': 'a' * 64, 'outcome': values[i % len(values)], 'outcome_metric': 'REALIZED_PNL',
             'outcome_unit': 'USD', 'features': {'trend': 'up'}, 'indicators': {'rsi': 50},
             'risk_factors': {'tier': 'LOW'}, 'context': {'session': 'LONDON'}} for i in range(30)]
    attribution = KnowledgeOutcomeAttributionEngine().analyze(rows)
    policy = GovernedLearningPolicyEngine().evaluate(attribution)
    if policy_uuid: object.__setattr__(policy, 'policy_uuid', policy_uuid)
    samples = tuple(ApprovedPatternMiningSample(str(uuid4()), {'trend': 'up', 'rsi': 50, 'price': 2300 + i},
                    {'session': 'LONDON', 'timestamp': rows[i]['timestamp']}, {'side': 'BUY'}, {'kind': 'TARGET'},
                    {'tier': 'LOW'}, rows[i]['outcome'], rows[i]['timestamp']) for i in range(30))
    summary = policy.validation_summary
    envelope = ApprovedPatternMiningEvidenceEnvelope.create(policy_uuid=policy.policy_uuid, policy_version=policy.policy_version,
        source_attribution_uuid=summary['source_attribution_uuid'], source_digest=summary['source_digest'],
        replay_digest=summary['replay_digest'], knowledge_uuid=policy.knowledge_uuid, knowledge_version=policy.knowledge_version,
        outcome_contract=tuple(summary['outcome_contract']), approved_samples=samples, generated_at=policy.generated_at)
    return policy, envelope


def recreate(envelope, **changes):
    values = {"policy_uuid": envelope.policy_uuid, "policy_version": envelope.policy_version,
              "source_attribution_uuid": envelope.source_attribution_uuid, "source_digest": envelope.source_digest,
              "replay_digest": envelope.replay_digest, "knowledge_uuid": envelope.knowledge_uuid,
              "knowledge_version": envelope.knowledge_version, "outcome_contract": envelope.outcome_contract,
              "approved_samples": envelope.approved_samples, "generated_at": envelope.generated_at}
    values.update(changes)
    return ApprovedPatternMiningEvidenceEnvelope.create(**values)


def test_missing_evidence_and_non_policy_fail_closed():
    policy, _ = policy_and_evidence()
    with pytest.raises(PatternMiningError, match='MISSING_APPROVED_PATTERN_EVIDENCE'): PatternMiningEngine().mine(policy)
    with pytest.raises(PatternMiningError, match='INVALID_POLICY_REPORT'): PatternMiningEngine().mine({}, None)

@pytest.mark.parametrize('change,error', [
    ({'blocking_reasons': ('BLOCKED',)}, 'TAMPERED_POLICY_REPORT'),
    ({'hard_gates': {'structural_validity': False}}, 'TAMPERED_POLICY_REPORT'),
    ({'policy_version': 'PR174.UNSUPPORTED'}, 'UNSUPPORTED_POLICY_VERSION'),
    ({'advisory_only': False}, 'TAMPERED_POLICY_REPORT'),
])
def test_tampered_policy(change, error):
    policy, envelope = policy_and_evidence()
    for key, value in change.items(): object.__setattr__(policy, key, value)
    with pytest.raises(PatternMiningError, match=error): PatternMiningEngine().mine(policy, envelope)

@pytest.mark.parametrize('field,value', [('source_digest', 'bad'), ('replay_digest', 'bad')])
def test_invalid_policy_digests(field, value):
    policy, envelope = policy_and_evidence(); summary = dict(policy.validation_summary); summary[field] = value
    object.__setattr__(policy, 'validation_summary', summary)
    with pytest.raises(PatternMiningError, match='INVALID_POLICY_PROVENANCE'): PatternMiningEngine().mine(policy, envelope)

@pytest.mark.parametrize('field,error', [('policy_uuid', 'MIXED_POLICY_UUID'), ('replay_digest', 'MIXED_REPLAY_DIGEST'),
                                          ('source_digest', 'MIXED_SOURCE_DIGEST'), ('knowledge_version', 'MIXED_KNOWLEDGE_VERSION')])
def test_mixed_envelope_provenance(field, error):
    policy, envelope = policy_and_evidence()
    value = str(uuid4()) if field == 'policy_uuid' else ('b' * 64 if 'digest' in field else '2')
    envelope = recreate(envelope, **{field: value})
    with pytest.raises(PatternMiningError, match=error): PatternMiningEngine().mine(policy, envelope)


def test_mixed_outcome_contract():
    policy, envelope = policy_and_evidence(); envelope = recreate(envelope, outcome_contract=('RETURN', 'PERCENT'))
    with pytest.raises(PatternMiningError, match='MIXED_OUTCOME_CONTRACT'): PatternMiningEngine().mine(policy, envelope)


def test_pattern_statistics_provenance_normalization_and_replay():
    policy, envelope = policy_and_evidence()
    first = PatternMiningEngine().mine(policy, envelope); second = PatternMiningEngine().mine(policy, envelope)
    assert first == second and first.pattern_count == 1
    pattern = first.candidate_patterns[0]
    assert (pattern.win_count, pattern.loss_count, pattern.neutral_count) == (10, 10, 10)
    assert pattern.expectancy == pytest.approx(1 / 3) and pattern.support == 1 and pattern.confidence == .5
    assert pattern.policy_uuid == policy.policy_uuid and pattern.policy_version == policy.policy_version
    assert pattern.source_attribution_uuid == envelope.source_attribution_uuid
    assert pattern.source_digest == envelope.source_digest
    assert pattern.outcome_contract == ('REALIZED_PNL', 'USD') and pattern.advisory_only
    # Volatile price/timestamp values cannot split otherwise identical patterns.
    assert first.pattern_count == 1


def test_rsi_normalization_groups_continuous_values():
    policy, envelope = policy_and_evidence(); samples = []
    for i, sample in enumerate(envelope.approved_samples):
        features = dict(sample.features); features['rsi'] = 40 + i
        samples.append(replace(sample, features=features))
    envelope = recreate(envelope, approved_samples=tuple(samples))
    report = PatternMiningEngine(PatternMiningConfig(excluded_volatile_fields=('timestamp', 'price', 'atr'))).mine(policy, envelope)
    assert report.pattern_count == 1


def test_different_policy_uuid_changes_pattern_uuid():
    policy, envelope = policy_and_evidence(); first = PatternMiningEngine().mine(policy, envelope)
    changed = str(uuid4()); object.__setattr__(policy, 'policy_uuid', changed); envelope = recreate(envelope, policy_uuid=changed)
    second = PatternMiningEngine().mine(policy, envelope)
    assert first.candidate_patterns[0].pattern_uuid != second.candidate_patterns[0].pattern_uuid


def test_duplicate_conflicting_sample_uuid():
    policy, envelope = policy_and_evidence(); samples = list(envelope.approved_samples)
    samples[1] = replace(samples[1], sample_uuid=samples[0].sample_uuid, outcome=-99)
    with pytest.raises(ValueError, match='DUPLICATE_CONFLICTING_IDENTITY'):
        replace(envelope, approved_samples=tuple(samples))


def test_report_summary_validation_and_repository(tmp_path):
    policy, envelope = policy_and_evidence(); report = PatternMiningEngine().mine(policy, envelope)
    with pytest.raises(ValueError, match='INVALID_PATTERN_MINING_REPORT'):
        replace(report, statistics_summary={'sample_count': 999})
    repository = PatternMiningRepository(tmp_path); path = repository.save(report)
    assert repository.save(report) == path
    assert path.read_bytes() == json.dumps(report.to_dict(), sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    with pytest.raises(FileExistsError): repository.save(replace(report, report_uuid=report.report_uuid,
        candidate_patterns=report.candidate_patterns, statistics_summary=report.statistics_summary, generated_at='2026-07-26T00:00:00Z'))


def test_duplicate_identical_sample_rejected_at_model_boundary():
    _, envelope = policy_and_evidence(); samples = list(envelope.approved_samples); samples[1] = samples[0]
    with pytest.raises(ValueError, match='DUPLICATE_EVIDENCE_IDENTITY'):
        replace(envelope, approved_samples=tuple(samples))


def test_envelope_content_addressing_and_canonical_order():
    _, envelope = policy_and_evidence()
    recreated = ApprovedPatternMiningEvidenceEnvelope.create(policy_uuid=envelope.policy_uuid,
        policy_version=envelope.policy_version, source_attribution_uuid=envelope.source_attribution_uuid,
        source_digest=envelope.source_digest, replay_digest=envelope.replay_digest, knowledge_uuid=envelope.knowledge_uuid,
        knowledge_version=envelope.knowledge_version, outcome_contract=envelope.outcome_contract,
        approved_samples=tuple(reversed(envelope.approved_samples)), generated_at=envelope.generated_at)
    assert recreated == envelope
    changed_sample = replace(envelope.approved_samples[0], outcome=99)
    changed = ApprovedPatternMiningEvidenceEnvelope.create(policy_uuid=envelope.policy_uuid,
        policy_version=envelope.policy_version, source_attribution_uuid=envelope.source_attribution_uuid,
        source_digest=envelope.source_digest, replay_digest=envelope.replay_digest, knowledge_uuid=envelope.knowledge_uuid,
        knowledge_version=envelope.knowledge_version, outcome_contract=envelope.outcome_contract,
        approved_samples=(changed_sample, *envelope.approved_samples[1:]), generated_at=envelope.generated_at)
    assert changed.envelope_digest != envelope.envelope_digest and changed.envelope_uuid != envelope.envelope_uuid
    changed_uuid = replace(envelope.approved_samples[0], sample_uuid=str(uuid4()))
    assert recreate(envelope, approved_samples=(changed_uuid, *envelope.approved_samples[1:])).envelope_uuid != envelope.envelope_uuid
    assert recreate(envelope, source_digest='b' * 64).envelope_uuid != envelope.envelope_uuid


@pytest.mark.parametrize('field,value,error', [
    ('envelope_digest', 'b' * 64, 'EVIDENCE_ENVELOPE_DIGEST_MISMATCH'),
    ('envelope_uuid', str(uuid4()), 'EVIDENCE_ENVELOPE_UUID_MISMATCH'),
    ('envelope_version', 'UNSUPPORTED', 'UNSUPPORTED_EVIDENCE_ENVELOPE_VERSION'),
])
def test_tampered_envelope_identity(field, value, error):
    _, envelope = policy_and_evidence()
    with pytest.raises(ValueError, match=error): replace(envelope, **{field: value})


def test_report_retains_envelope_and_config_identity():
    policy, envelope = policy_and_evidence(); report = PatternMiningEngine().mine(policy, envelope)
    assert report.evidence_envelope_uuid == envelope.envelope_uuid
    assert report.evidence_envelope_digest == envelope.envelope_digest
    assert len(report.mining_config_digest) == 64 and report.mining_config
    with pytest.raises(ValueError, match='INVALID_PATTERN_MINING_REPORT'):
        replace(report, evidence_envelope_digest='b' * 64)
    with pytest.raises(ValueError, match='INVALID_PATTERN_MINING_REPORT'):
        replace(report, mining_config_digest='b' * 64)


def test_pattern_identity_binds_source_replay_and_config():
    policy, envelope = policy_and_evidence(); original = PatternMiningEngine().mine(policy, envelope).candidate_patterns[0]
    summary = dict(policy.validation_summary); summary['source_digest'] = 'b' * 64
    object.__setattr__(policy, 'validation_summary', summary)
    source_changed_envelope = recreate(envelope, source_digest='b' * 64)
    source_changed = PatternMiningEngine().mine(policy, source_changed_envelope).candidate_patterns[0]
    summary['replay_digest'] = 'c' * 64; object.__setattr__(policy, 'validation_summary', summary)
    replay_changed = PatternMiningEngine().mine(policy, recreate(source_changed_envelope, replay_digest='c' * 64)).candidate_patterns[0]
    configured = PatternMiningEngine(PatternMiningConfig(allowed_feature_fields=('trend',))).mine(
        policy, recreate(source_changed_envelope, replay_digest='c' * 64)).candidate_patterns[0]
    assert len({original.pattern_uuid, source_changed.pattern_uuid, replay_changed.pattern_uuid, configured.pattern_uuid}) == 4


def test_different_envelope_changes_report_uuid():
    policy, envelope = policy_and_evidence(); first = PatternMiningEngine().mine(policy, envelope)
    samples = list(envelope.approved_samples); samples[0] = replace(samples[0], outcome=5)
    changed = recreate(envelope, approved_samples=tuple(samples))
    second = PatternMiningEngine().mine(policy, changed)
    assert first.report_uuid != second.report_uuid


def test_config_is_strict():
    with pytest.raises(ValueError): PatternMiningConfig(allowed_feature_fields=())
    with pytest.raises(ValueError): PatternMiningConfig(allowed_feature_fields=('trend', 'trend'))
    with pytest.raises(ValueError): PatternMiningConfig(allowed_feature_fields=('price',))
    with pytest.raises(ValueError): PatternMiningConfig(allowed_context_fields={'unsupported': ('x',)})
    with pytest.raises(ValueError): PatternMiningConfig(rsi_bucket_boundaries=(70, 30))


@pytest.mark.parametrize('field,value', [('features', {'trend': 'up', 'rsi': float('nan')}),
                                          ('market_context', {'session': float('inf')})])
def test_non_finite_sample_content_rejected(field, value):
    _, envelope = policy_and_evidence(); sample = envelope.approved_samples[0]
    with pytest.raises(ValueError, match='INVALID_APPROVED_PATTERN_MINING_SAMPLE'):
        replace(sample, **{field: value})


@pytest.mark.parametrize('outcome', [float('nan'), float('inf'), True])
def test_invalid_outcome_rejected(outcome):
    _, envelope = policy_and_evidence()
    with pytest.raises(ValueError, match='INVALID_APPROVED_PATTERN_MINING_SAMPLE'):
        replace(envelope.approved_samples[0], outcome=outcome)


def test_repository_filename_and_path_safety(tmp_path):
    repository = PatternMiningRepository(tmp_path)
    with pytest.raises(ValueError): repository.path_for('not-a-uuid')
    with pytest.raises(ValueError): repository.path_for('../escape')


def test_repository_removes_temporary_file_after_failure(tmp_path, monkeypatch):
    import learning.pattern_mining.repository as module
    policy, envelope = policy_and_evidence(); report = PatternMiningEngine().mine(policy, envelope)
    monkeypatch.setattr(module.os, 'link', lambda *_: (_ for _ in ()).throw(OSError('failure')))
    with pytest.raises(OSError): PatternMiningRepository(tmp_path).save(report)
    assert list(tmp_path.iterdir()) == []
