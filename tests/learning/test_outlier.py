from learning.validation.outlier import detect_outliers, mark_outliers

def test_outliers_are_marked_without_removing_records():
    rows = [{"net_profit": value, "duration": 10 if value != 100 else 1000} for value in [1, 1, 1, 1, 100]]
    marked = mark_outliers(rows)
    assert len(marked) == len(rows)
    assert marked[-1]["outliers"] == {"extreme_profit": True, "extreme_loss": False, "extreme_holding_time": True}
    assert detect_outliers([1, 1, 1, 1, 100])[-1]
