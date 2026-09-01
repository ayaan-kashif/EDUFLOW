import pytest
from fastapi import HTTPException

from app.api.corrections import parse_mapping_weight


def test_parse_mapping_weight_uses_current_when_missing():
    assert parse_mapping_weight(None, 0.4) == 0.4


def test_parse_mapping_weight_accepts_numeric_strings():
    assert parse_mapping_weight("0.75", 0.4) == 0.75


@pytest.mark.parametrize("value", ["high", {}, []])
def test_parse_mapping_weight_rejects_nonnumeric_values(value):
    with pytest.raises(HTTPException) as exc:
        parse_mapping_weight(value, 0.4)

    assert exc.value.status_code == 422
    assert "numeric" in exc.value.detail


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_parse_mapping_weight_rejects_out_of_range_values(value):
    with pytest.raises(HTTPException) as exc:
        parse_mapping_weight(value, 0.4)

    assert exc.value.status_code == 422
    assert "between 0 and 1" in exc.value.detail
