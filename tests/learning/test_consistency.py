from learning.validation.consistency import coefficient_of_variation, consistency_score, stability_score

def test_consistency_metrics_are_bounded_and_stable():
    assert coefficient_of_variation([2, 2, 2]) == 0
    assert stability_score([2, 2, 2]) == 1
    assert 0 < consistency_score([1, 2], [2, 2]) <= 1
