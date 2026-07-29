"""Adversarial PR272 independent model-evaluation governance tests."""
from dataclasses import replace
import pytest
from bridge.v28.offline_learning import build_learning_dataset, create_learning_registry, publish_learning_evidence
from bridge.v28.outcome_analytics import analyze_learning_evidence
from bridge.v28.outcome_evidence import publish_outcome_evidence
from bridge.v28.outcome_registry import create_outcome_registry
from learning.evaluation import (DatasetNonOverlapProof, EvaluationDatasetLoader, EvaluationPolicy,
 EvaluationRegistry, ModelEvaluator, ReplayValidation)
from learning.training import CandidateRegistry, TrainingConfiguration, TrainingDataset, TrainingRow, TrainingSession
from tests.test_v28_outcome_intelligence import outcome


def learning_authority(name):
    outcomes=create_outcome_registry().append(outcome(name)); oe=publish_outcome_evidence(outcomes)
    evidence=publish_learning_evidence(outcomes,oe,build_learning_dataset(outcomes,oe))
    registry=create_learning_registry().append(evidence)
    return registry,evidence,analyze_learning_evidence(evidence)

@pytest.fixture(scope='module')
def governed():
    training=learning_authority('evaluation-source')
    row=TrainingRow(0,'training-outcome','training-example',{'confidence':.5,'spread':1.0},.1)
    td=TrainingDataset((row,),1,training[0].registry_identity,training[1].evidence_identity,
      training[2].report_identity,training[1].dataset.dataset_identity,training[1].dataset.dataset_version_identity)
    config=TrainingConfiguration(('confidence','spread'),policy_identity='training-v1',code_version='git:pr271')
    result=TrainingSession(config).run(td); candidates=CandidateRegistry().append(result.candidate,result.evidence)
    ed=EvaluationDatasetLoader().load(*training,td)
    return candidates,result,training,td,ed

def evaluate(values, policy=None):
    candidates,result,training,td,ed=values
    engine=ModelEvaluator(policy or EvaluationPolicy('evaluation-governance-v2'))
    inputs=(candidates,result.candidate,result.evidence,training[0],training[2],td,*training,ed)
    return engine,inputs,engine.evaluate(*inputs)

def test_independent_dataset_and_exact_training_lineage(governed):
    _,_,training,td,ed=governed
    assert ed.source_learning_registry_identity==training[0].registry_identity
    assert ed.source_learning_evidence_identity==training[1].evidence_identity
    assert ed.non_overlap_proof.training_row_identities==tuple(x.row_identity for x in td.rows)
    assert ed.non_overlap_proof.overlap_count==0
    engine,inputs,report=evaluate(governed)
    assert report.training_learning_registry_identity==training[0].registry_identity
    assert report.training_analytics_identity==training[2].report_identity
    assert engine.replay(report,*inputs)

def test_cross_dataset_overlap_duplicate_rows_and_lineage_fail_closed(governed):
    _,result,training,td,ed=governed
    with pytest.raises(ValueError,match='OVERLAP'):
        EvaluationDatasetLoader().load(*training,replace(td,rows=(replace(td.rows[0],
          outcome_identity=training[1].dataset.examples[0].outcome_identity,
          example_identity=training[1].dataset.examples[0].example_identity,row_identity=''),),dataset_identity=''))
    with pytest.raises(ValueError,match='DATASET_INVALID'):
        replace(ed,rows=(ed.rows[0],ed.rows[0]),dataset_identity='')
    candidates=CandidateRegistry().append(result.candidate,result.evidence)
    engine=ModelEvaluator(EvaluationPolicy('evaluation-governance-v2'))
    with pytest.raises(ValueError,match='IDENTITY'):
        engine.evaluate(candidates,result.candidate,result.evidence,training[0],replace(training[2],report_identity='forged'),
          td,*training,ed)

def test_evaluation_side_authorities_are_mandatory(governed):
    engine,inputs,_=evaluate(governed); *prefix,registry,evidence,analytics,dataset=inputs
    forged=replace(dataset,source_learning_registry_identity='arbitrary-registry',
      source_learning_evidence_identity='arbitrary-evidence',source_analytics_identity='arbitrary-analytics',dataset_identity='')
    with pytest.raises(ValueError,match='PROVENANCE'):
        engine.evaluate(*prefix,registry,evidence,analytics,forged)
    with pytest.raises(ValueError,match='NOT_REGISTERED'):
        engine.evaluate(*prefix,create_learning_registry(),evidence,analytics,dataset)
    original=analytics.source_learning_evidence_identity
    object.__setattr__(analytics,'source_learning_evidence_identity','different-evidence')
    with pytest.raises(ValueError,match='IDENTITY|REPLAY'):
        engine.evaluate(*prefix,registry,evidence,analytics,dataset)
    object.__setattr__(analytics,'source_learning_evidence_identity',original)

def test_non_overlap_proof_cannot_mix_identity_domains(governed):
    *_,td,ed=governed
    mismatched=DatasetNonOverlapProof(ed.non_overlap_proof.training_row_identities,
      ed.non_overlap_proof.training_example_identities,('source-row-domain-value',),0)
    with pytest.raises(ValueError,match='PROOF_BINDING'):
        replace(ed,non_overlap_proof=mismatched,dataset_identity='')

def test_policy_dimensions_statistics_and_qualification_cannot_be_forged(governed):
    engine,inputs,report=evaluate(governed)
    assert not report.qualified and 'INSUFFICIENT_EVALUATION_RECORDS' in report.qualification_reasons
    with pytest.raises(ValueError,match='POLICY_IDENTITY'):
        replace(report.policy,maximum_mse=2.0)
    dimension=report.dimensions[0]
    with pytest.raises(ValueError,match='DIMENSION'):
        replace(dimension,passed=not dimension.passed)
    with pytest.raises(ValueError,match='STATISTICAL'):
        replace(report.statistical_validation,mean_squared_error=99)
    with pytest.raises(ValueError,match='REPORT_INVALID'):
        replace(report,qualified=True,qualification_reasons=('FORGED',),report_identity='')
    with pytest.raises(ValueError,match='REPLAY'):
        ReplayValidation('a','b',True)

def test_confidence_semantics_and_actual_replay_verification(governed):
    engine,inputs,report=evaluate(governed)
    expected=sum((row.confidence-(1. if row.label>0 else 0.))**2 for row in governed[-1].rows)/len(governed[-1].rows)
    assert report.statistical_validation.confidence_brier_score==expected
    confidence=next(x for x in report.dimensions if x.dimension=='confidence_reliability')
    assert confidence.score==max(0.,1.-expected/report.policy.maximum_confidence_brier_score)
    assert report.replay_validation.first_computation_digest==report.replay_validation.second_computation_digest
    object.__setattr__(report.replay_validation,'second_computation_digest','forged')
    assert not engine.replay(report,*inputs)

def test_registry_order_ancestry_and_composite_uniqueness(governed):
    _,_,report=evaluate(governed); empty=EvaluationRegistry(); one=empty.append(report)
    assert one.previous_registry_identity==empty.registry_identity
    with pytest.raises(ValueError,match='DUPLICATE'): one.append(report)
    entry=one.entries[0]
    with pytest.raises(ValueError,match='ENTRY_INVALID'):
        replace(one,entries=(replace(entry,sequence=2,entry_identity=''),),registry_identity='')
    with pytest.raises(ValueError,match='PREDECESSOR'):
        replace(one,previous_registry_identity='forged',registry_identity='')
    # Same candidate/dataset under a different content-addressed policy is a distinct governed evaluation.
    _,_,second=evaluate(governed,EvaluationPolicy('evaluation-governance-v2b',maximum_mse=2.0))
    assert len(one.append(second).entries)==2
