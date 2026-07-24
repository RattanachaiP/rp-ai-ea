from __future__ import annotations
import math
from dataclasses import replace
import pytest
from learning.analytics import AnalyticsConfig, KnowledgeAnalyticsEngine
from learning.knowledge import Knowledge

BASELINE = "cb751c0747ee567016bc322834b6105684514c63"


class Reader:
    def __init__(self, records):
        self.records = tuple(records)

    def query(self, **kwargs):
        return self.records


def record(uuid, version=1, win=.5, rr=1., pattern="p"):
    return Knowledge(uuid, version, pattern, "v" + uuid, "2026-01-%02dT00:00:00Z" % version, ("XAUUSD",), ("LONDON",), ("TREND",), 40, win, rr, None)


def test_artifact_identity_and_canonical_replay_are_config_aware():
    reader = Reader((record("a"),))
    first = KnowledgeAnalyticsEngine(reader).analyze()
    second = KnowledgeAnalyticsEngine(reader).analyze()
    assert first.to_dict() == second.to_dict()
    assert first.analytics_uuid != KnowledgeAnalyticsEngine(reader, config=AnalyticsConfig(conflict_rr_delta=.9)).analyze().analytics_uuid
    assert first.analytics_uuid != KnowledgeAnalyticsEngine(reader, analytics_version="2.0").analyze().analytics_uuid
    assert first.analytics_uuid != KnowledgeAnalyticsEngine(reader, source_baseline=BASELINE).analyze().analytics_uuid


def test_persisted_report_requires_explicit_source_baseline(tmp_path):
    from learning.analytics import AnalyticsRepository

    with pytest.raises(ValueError, match="SOURCE_BASELINE_REQUIRED_FOR_PERSISTENCE"):
        KnowledgeAnalyticsEngine(Reader((record("a"),)), AnalyticsRepository(tmp_path))


def test_conflicts_never_coerce_invalid_metrics_to_zero():
    left = record("a", win=math.nan, rr=math.inf)
    right = record("b", win=.9, rr=2.)
    assert KnowledgeAnalyticsEngine(Reader((left, right))).detect_conflicts() == ()


def test_stability_bands_and_non_contiguous_lineage():
    assert KnowledgeAnalyticsEngine(Reader((record("a", 1, .5, 1), record("b", 2, .52, 1.1)))).analyze_stability()["lineages"][0]["classification"] == "STABLE"
    assert KnowledgeAnalyticsEngine(Reader((record("a", 1, .5, 1), record("b", 2, .6, 1.3)))).analyze_stability()["lineages"][0]["classification"] == "IMPROVING"
    assert KnowledgeAnalyticsEngine(Reader((record("a", 1, .5, 1), record("b", 2, .4, .7)))).analyze_stability()["lineages"][0]["classification"] == "DEGRADING"
    assert KnowledgeAnalyticsEngine(Reader((record("a", 1), record("b", 3)))).analyze_stability()["lineages"][0]["classification"] == "INSUFFICIENT_HISTORY"


def test_repository_latest_uses_snapshot_timestamp_not_uuid_order(tmp_path):
    from learning.analytics import AnalyticsRepository

    repo = AnalyticsRepository(tmp_path)
    old = replace(KnowledgeAnalyticsEngine(Reader((record("zzz", 1),))).analyze(), analytics_uuid="f" * 32)
    new = replace(KnowledgeAnalyticsEngine(Reader((record("aaa", 2),))).analyze(), analytics_uuid="0" * 32)
    repo.save(old)
    repo.save(new)
    assert repo.latest().analytics_uuid == "0" * 32


def test_storage_replay_and_collision_are_append_only(tmp_path):
    from learning.analytics import AnalyticsRepository

    repo = AnalyticsRepository(tmp_path)
    report = KnowledgeAnalyticsEngine(Reader((record("a"),)), repo, source_baseline=BASELINE).analyze()
    assert repo.save(report) == repo.storage.path_for(report.analytics_uuid)
    with pytest.raises(FileExistsError):
        repo.storage.write(replace(report, source_baseline="DIFFERENT"))


def test_snapshot_permutation_has_identical_canonical_report():
    records = (record("a", 1, pattern="z"), record("b", 1, pattern="a"))
    assert KnowledgeAnalyticsEngine(Reader(records)).analyze().to_dict() == KnowledgeAnalyticsEngine(Reader(tuple(reversed(records)))).analyze().to_dict()


def test_orphan_temp_is_ignored_and_interrupted_temp_never_publishes(tmp_path, monkeypatch):
    from learning.analytics import AnalyticsRepository
    import learning.analytics.storage as module

    repo = AnalyticsRepository(tmp_path)
    (repo.storage.root / ".report_orphan.json.dead.tmp").write_text("partial")
    assert repo.history() == ()

    def fail(*args, **kwargs):
        raise OSError("interrupted")

    monkeypatch.setattr(module.os, "link", fail)
    with pytest.raises(OSError):
        repo.save(KnowledgeAnalyticsEngine(Reader((record("a"),)), source_baseline=BASELINE).analyze())
    assert not list(repo.storage.root.glob("report_*.json"))


def test_stale_lock_file_cannot_block_publication(tmp_path):
    from learning.analytics import AnalyticsRepository

    repo = AnalyticsRepository(tmp_path)
    report = KnowledgeAnalyticsEngine(Reader((record("a"),)), source_baseline=BASELINE).analyze()
    stale_lock = repo.storage.root / f".report_{report.analytics_uuid}.json.lock"
    stale_lock.write_text("dead writer", encoding="utf-8")
    assert repo.save(report) == repo.storage.path_for(report.analytics_uuid)


def test_directory_sync_failure_is_platform_safe(tmp_path, monkeypatch):
    from learning.analytics import AnalyticsRepository
    import learning.analytics.storage as module

    repo = AnalyticsRepository(tmp_path)
    report = KnowledgeAnalyticsEngine(Reader((record("a"),)), source_baseline=BASELINE).analyze()
    monkeypatch.setattr(module.os, "fsync", lambda *_: (_ for _ in ()).throw(OSError("unsupported")))
    with pytest.raises(OSError):
        # File fsync remains mandatory; only directory fsync is best effort.
        repo.save(report)
