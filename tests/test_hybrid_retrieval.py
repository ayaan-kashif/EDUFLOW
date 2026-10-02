from uuid import uuid4

import pytest

from app.domain.models import CurriculumNode, SourceSpan
from app.generation import retrieval
from app.providers.base import EmbeddingResponse


@pytest.mark.parametrize("failure", [False, True])
async def test_semantic_reranking_and_outage_fallback(monkeypatch, failure):
    node = CurriculumNode(id=uuid4(), label="Enzyme catalysts")
    lexical = SourceSpan(id=uuid4(), text="Enzyme catalysts")
    semantic = SourceSpan(id=uuid4(), text="Catalysts lower activation energy")

    async def candidates(session, node):
        return [lexical, semantic]

    class Router:
        async def call(self, fn):
            if failure:
                raise RuntimeError("offline")
            return EmbeddingResponse([[1, 0], [0, 1], [1, 0]], "test", "test")

    monkeypatch.setattr(retrieval, "_candidate_spans", candidates)
    result = await retrieval.retrieve_evidence(None, node, k=2, embedding_router=Router())
    assert result[0].id == (lexical.id if failure else semantic.id)
    assert {s.id for s in result} == {lexical.id, semantic.id}
