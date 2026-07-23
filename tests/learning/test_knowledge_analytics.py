from __future__ import annotations
import math
from dataclasses import replace
from learning.analytics import AnalyticsConfig, KnowledgeAnalyticsEngine
from learning.knowledge import Knowledge
class Reader:
 def __init__(self, records): self.records=tuple(records)
 def query(self, **kwargs): return self.records
def record(uuid, version=1, win=.5, rr=1., pattern='p'):
 return Knowledge(uuid,version,pattern,'v'+uuid,'2026-01-%02dT00:00:00Z'%version,('XAUUSD',),('LONDON',),('TREND',),40,win,rr,None)
def test_artifact_identity_and_canonical_replay_are_config_aware():
 reader=Reader((record('a'),)); first=KnowledgeAnalyticsEngine(reader).analyze(); second=KnowledgeAnalyticsEngine(reader).analyze()
 assert first.to_dict()==second.to_dict()
 assert first.analytics_uuid != KnowledgeAnalyticsEngine(reader, config=AnalyticsConfig(conflict_rr_delta=.9)).analyze().analytics_uuid
 assert first.analytics_uuid != KnowledgeAnalyticsEngine(reader, analytics_version='2.0').analyze().analytics_uuid
def test_conflicts_never_coerce_invalid_metrics_to_zero():
 left=record('a',win=math.nan,rr=math.inf); right=record('b',win=.9,rr=2.)
 assert KnowledgeAnalyticsEngine(Reader((left,right))).detect_conflicts()==()
def test_stability_bands_and_non_contiguous_lineage():
 assert KnowledgeAnalyticsEngine(Reader((record('a',1,.5,1),record('b',2,.52,1.1)))).analyze_stability()['lineages'][0]['classification']=='STABLE'
 assert KnowledgeAnalyticsEngine(Reader((record('a',1,.5,1),record('b',2,.6,1.3)))).analyze_stability()['lineages'][0]['classification']=='IMPROVING'
 assert KnowledgeAnalyticsEngine(Reader((record('a',1,.5,1),record('b',2,.4,.7)))).analyze_stability()['lineages'][0]['classification']=='DEGRADING'
 assert KnowledgeAnalyticsEngine(Reader((record('a',1),record('b',3)))).analyze_stability()['lineages'][0]['classification']=='INSUFFICIENT_HISTORY'
def test_repository_latest_uses_snapshot_timestamp_not_uuid_order(tmp_path):
 from learning.analytics import AnalyticsRepository
 repo=AnalyticsRepository(tmp_path)
 old=replace(KnowledgeAnalyticsEngine(Reader((record('zzz',1),))).analyze(), analytics_uuid='zzz')
 new=replace(KnowledgeAnalyticsEngine(Reader((record('aaa',2),))).analyze(), analytics_uuid='aaa')
 repo.save(old); repo.save(new)
 assert repo.latest().analytics_uuid == 'aaa'

def test_storage_replay_and_collision_are_append_only(tmp_path):
 from learning.analytics import AnalyticsRepository
 repo=AnalyticsRepository(tmp_path); report=KnowledgeAnalyticsEngine(Reader((record('a'),)),repo).analyze()
 assert repo.save(report)==repo.storage.path_for(report.analytics_uuid)
 from pytest import raises
 with raises(FileExistsError): repo.storage.write(replace(report, status='EMPTY_INPUT'))
def test_snapshot_permutation_has_identical_canonical_report():
 records=(record('a', 1, pattern='z'), record('b', 1, pattern='a'))
 assert KnowledgeAnalyticsEngine(Reader(records)).analyze().to_dict() == KnowledgeAnalyticsEngine(Reader(tuple(reversed(records)))).analyze().to_dict()

def test_orphan_temp_is_ignored_and_interrupted_temp_never_publishes(tmp_path, monkeypatch):
 from learning.analytics import AnalyticsRepository
 repo=AnalyticsRepository(tmp_path); (repo.storage.root / '.report_orphan.json.dead.tmp').write_text('partial')
 assert repo.history() == ()
 import learning.analytics.storage as module
 def fail(*args, **kwargs): raise OSError('interrupted')
 monkeypatch.setattr(module.os, 'replace', fail)
 with __import__('pytest').raises(OSError): repo.save(KnowledgeAnalyticsEngine(Reader((record('a'),))).analyze())
 assert not list(repo.storage.root.glob('report_*.json'))
