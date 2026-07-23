from learning.pattern.candidate import CandidatePattern
from learning.pattern.statistics import calculate_statistics
from learning.validation import StatisticalValidator, ValidationRepository

def test_validator_promotes_only_verified_patterns(tmp_path):
    rows = [{"net_profit": 2, "mae": 1, "mfe": 2, "duration": 60} for _ in range(30)]
    pattern = CandidatePattern.create({"session": "LONDON"}, calculate_statistics(rows), pattern_uuid="valid")
    result = StatisticalValidator(ValidationRepository(tmp_path)).validate(pattern, rows)
    assert result.status == "VERIFIED"
    assert (tmp_path / "verified_patterns" / "verified_valid.json").exists()

def test_validator_retains_insufficient_pattern_for_audit(tmp_path):
    rows = [{"net_profit": 2} for _ in range(2)]
    pattern = CandidatePattern.create({"session": "LONDON"}, calculate_statistics(rows), pattern_uuid="small")
    result = StatisticalValidator(ValidationRepository(tmp_path)).validate(pattern, rows)
    assert result.status == "INSUFFICIENT_DATA"
    assert (tmp_path / "validation_results" / "validation_small.json").exists()
