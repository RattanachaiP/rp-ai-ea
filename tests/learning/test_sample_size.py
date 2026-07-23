import pytest
from learning.validation.sample_size import validate_sample_size

def test_minimum_sample_size_is_configurable():
    assert not validate_sample_size(29)
    assert validate_sample_size(29, 29)
    with pytest.raises(ValueError): validate_sample_size(1, 0)
