import pytest

from app.domain.models import NodeType
from app.ingestion.curriculum_extraction import CurriculumExtractionError, _parse_extraction


def test_parses_nodes_with_hierarchy_and_prerequisites():
    nodes = _parse_extraction(
        """
        {"nodes": [
          {"ref": "BIO.CELL", "type": "topic", "label": "Cell Biology", "parent_ref": null},
          {"ref": "BIO.CELL.01", "type": "objective", "label": "Describe mitosis",
           "parent_ref": "BIO.CELL", "prerequisite_refs": ["BIO.CELL.00"]}
        ]}
        """
    )
    assert len(nodes) == 2
    assert nodes[0].node_type is NodeType.TOPIC
    assert nodes[0].parent_ref is None
    assert nodes[1].node_type is NodeType.OBJECTIVE
    assert nodes[1].parent_ref == "BIO.CELL"
    assert nodes[1].prerequisite_refs == ["BIO.CELL.00"]


def test_missing_prerequisite_refs_defaults_to_empty():
    nodes = _parse_extraction('{"nodes": [{"ref": "A", "type": "topic", "label": "A"}]}')
    assert nodes[0].prerequisite_refs == []


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        '{"nodes": []}',  # empty tree is a failed extraction, not a valid one
        '{"nodes": [{"ref": "A"}]}',  # no label
        '{"nodes": [{"ref": "A", "type": "galaxy", "label": "A"}]}',  # unknown node type
        '["A", "B"]',  # bare list, not the documented shape
    ],
)
def test_malformed_responses_raise_rather_than_persist_a_partial_tree(raw):
    with pytest.raises(CurriculumExtractionError):
        _parse_extraction(raw)


@pytest.mark.parametrize("failure", [ValueError("no configured model"), RuntimeError("unused")])
async def test_provider_setup_and_outage_explain_how_to_recover(monkeypatch, failure):
    from uuid import uuid4

    from app.domain.models import SourceSpan
    from app.ingestion.curriculum_extraction import CurriculumExtractionService
    from app.providers.base import ProviderUnavailableError
    from tests.conftest import FakeSession

    doc_id = uuid4()
    session = FakeSession({SourceSpan: [SourceSpan(document_id=doc_id, text="Describe cells.", page=1, block_id="1")]})
    service = CurriculumExtractionService(session)

    class OfflineChain:
        async def call(self, fn):
            raise ProviderUnavailableError("all providers exhausted")

    async def chain():
        if isinstance(failure, ValueError):
            raise failure
        return OfflineChain()

    monkeypatch.setattr(service, "_get_chain", chain)
    with pytest.raises(CurriculumExtractionError, match="OLLAMA_MODEL"):
        await service.extract(doc_id)
    assert not session.committed


def test_blank_model_is_rejected_before_creating_a_provider():
    from app.providers.llm.openai_compatible import OpenAICompatibleLLMProvider

    with pytest.raises(ValueError, match="no model configured"):
        OpenAICompatibleLLMProvider(name="local", model=" ", base_url="http://localhost:11434/v1",
                                   api_key=None, requires_api_key=False)
