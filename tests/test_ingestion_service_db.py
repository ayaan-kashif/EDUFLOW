"""Service-level tests for app/ingestion/service.py.

Exercises the real DB orchestration in IngestionService.ingest_document:
it calls the parser, persists a SourceDocument, and persists SourceSpan
rows — all verified against a FakeSession.
"""

import uuid
from dataclasses import dataclass

from app.domain.models import DocType, SourceDocument, SourceSpan
from app.ingestion.service import IngestionService
from app.providers.base import ParsedDocument
from tests.conftest import FakeSession


@dataclass
class _FakeBBox:
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class _FakeBlock:
    page: int
    block_id: str
    bbox: _FakeBBox
    text: str


class _FakeParser:
    """Returns a canned ParsedDocument when called."""

    _DEFAULT_BLOCKS = [
        _FakeBlock(1, "b1", _FakeBBox(0, 0, 100, 50), "Hello world"),
        _FakeBlock(1, "b2", _FakeBBox(0, 50, 100, 100), "Second block"),
    ]

    def __init__(self, blocks=None, parser_name="fake_parser", confidence=0.95):
        self._blocks = self._DEFAULT_BLOCKS if blocks is None else blocks
        self._parser_name = parser_name
        self._confidence = confidence

    async def call(self, fn):
        return ParsedDocument(
            blocks=self._blocks,
            parser_name=self._parser_name,
            parser_confidence=self._confidence,
        )


async def test_ingest_document_persists_document_and_spans():
    session = FakeSession()
    parser = _FakeParser()
    service = IngestionService(session, parser_router=parser)

    doc = await service.ingest_document(
        file_path="/tmp/test.pdf",
        title="Test Syllabus",
        doc_type=DocType.SYLLABUS,
    )

    assert doc.id is not None
    assert doc.title == "Test Syllabus"
    assert doc.parser_used == "fake_parser"
    assert doc.parser_confidence == 0.95

    # Verify document was committed
    assert session.committed

    # Verify spans were persisted (added during flush, committed)
    spans = [obj for obj in session.added if isinstance(obj, SourceSpan)]
    assert len(spans) == 2
    assert spans[0].document_id == doc.id
    assert spans[0].page == 1
    assert spans[0].text == "Hello world"
    assert spans[1].text == "Second block"


async def test_ingest_document_empty_blocks():
    session = FakeSession()
    parser = _FakeParser(blocks=[])
    service = IngestionService(session, parser_router=parser)

    doc = await service.ingest_document(
        file_path="/tmp/empty.pdf",
        title="Empty Doc",
        doc_type=DocType.TEXTBOOK,
    )

    assert doc.id is not None
    spans = [obj for obj in session.added if isinstance(obj, SourceSpan)]
    assert len(spans) == 0


async def test_ingest_document_propagates_parser_failure():
    class _FailingParser:
        async def call(self, fn):
            raise RuntimeError("parser crashed")

    session = FakeSession()
    service = IngestionService(session, parser_router=_FailingParser())

    import pytest
    with pytest.raises(RuntimeError, match="parser crashed"):
        await service.ingest_document(
            file_path="/tmp/bad.pdf",
            title="Bad Doc",
            doc_type=DocType.PAST_PAPER,
        )

    # Nothing should have been committed
    assert not session.committed
    assert len(session.added) == 0
