import pytest
from pydantic import ValidationError

from app.api.generation import GenerateQuestionsRequest


def test_generate_questions_request_defaults_to_three():
    assert GenerateQuestionsRequest().count == 3


@pytest.mark.parametrize("count", [1, 50])
def test_generate_questions_request_accepts_reasonable_counts(count):
    assert GenerateQuestionsRequest(count=count).count == count


@pytest.mark.parametrize("count", [0, -1, 51])
def test_generate_questions_request_rejects_invalid_counts(count):
    with pytest.raises(ValidationError):
        GenerateQuestionsRequest(count=count)
