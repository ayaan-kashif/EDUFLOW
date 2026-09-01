import uuid

import pytest
from fastapi import HTTPException

from app.api import mapping as mapping_api
from app.api.mapping import MapQuestionRequest, map_question
from app.domain.models import ExamQuestion
from app.providers.base import ProviderError


class FailingEmbeddingRouter:
    async def call(self, fn):
        raise ProviderError("embedding service unavailable")


class FakeSession:
    def __init__(self, question):
        self.question = question

    async def get(self, model, id_):
        if model is ExamQuestion and id_ == self.question.id:
            return self.question
        return None


async def test_map_question_auto_shortlist_embedding_failure_is_actionable(monkeypatch):
    question = ExamQuestion(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        question_ref="q1",
        text="Explain binary search.",
    )

    async def fake_get_embedding_router():
        return FailingEmbeddingRouter()

    monkeypatch.setattr(mapping_api, "_get_embedding_router", fake_get_embedding_router)

    with pytest.raises(HTTPException) as exc:
        await map_question(question.id, MapQuestionRequest(), FakeSession(question))

    assert exc.value.status_code == 400
    assert "node_ids required" in exc.value.detail
