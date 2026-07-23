from learning.validation.confidence_interval import proportion_confidence_interval
from learning.validation.significance import calculate_significance, is_win_rate_significant

def test_win_rate_significance_and_interval_are_deterministic():
    assert is_win_rate_significant(80, 100)
    assert calculate_significance(80, 100) > 1.95
    low, high = proportion_confidence_interval(80, 100)
    assert 0 <= low < high <= 1
