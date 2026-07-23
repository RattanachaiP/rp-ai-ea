from learning.pattern import PatternRepository, discover, discover_incremental, load_pattern, query_patterns

def record(profit, **features):
    return {"features": features, "net_profit": profit, "rr": 2, "mae": 1, "mfe": 3, "duration": 60}

def test_discovery_groups_deterministically_and_calculates_statistics(tmp_path):
    repo = PatternRepository(tmp_path)
    rows = [record(5, trend="UP", session="LONDON") for _ in range(29)] + [record(-2, session="LONDON", trend="UP")]
    patterns = discover(reversed(rows), repository=repo)
    assert len(patterns) == 1
    stats = patterns[0].statistics
    assert patterns[0].status == "CANDIDATE"
    assert (stats["samples"], stats["wins"], stats["losses"], stats["win_rate"]) == (30, 29, 1, 29 / 30)
    assert stats["avg_profit"] == 5 and stats["avg_loss"] == -2 and stats["median_profit"] == 5

def test_insufficient_data_incremental_and_public_load_query(tmp_path):
    repo = PatternRepository(tmp_path)
    patterns = discover([record(0, trend="DOWN")], repository=repo)
    pattern = patterns[0]
    assert pattern.status == "INSUFFICIENT_DATA"
    assert load_pattern(pattern.pattern_uuid, repository=repo) == pattern
    assert query_patterns(repository=repo, conditions={"trend": "DOWN"}) == [pattern]
    assert discover_incremental([record(1, trend="DOWN")], repository=repo) == []
