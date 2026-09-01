import uuid

from app.domain.models import (
    CurriculumNode,
    ExamQuestion,
    MappingMethod,
    NodeType,
    Origin,
    QuestionNodeMapping,
)
from app.mapping.mapper import EnsembleMapper, MappingCandidate
from app.mapping.mapper import _llm_scores
from app.mapping.signals import SignalScores
from app.providers.base import LLMResponse


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return FakeScalarResult(self._rows)


class FakeSession:
    def __init__(self, existing=None):
        self.existing = existing or []
        self.added = []
        self.committed = False

    async def execute(self, query):
        return FakeResult(self.existing)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


class FakeLLMChain:
    async def call(self, fn):
        return LLMResponse(
            text='```json\n{"11111111-1111-1111-1111-111111111111": 0.75}\n```',
            model="fake-model",
            provider="fake",
            input_tokens=1,
            output_tokens=1,
        )


class FixedScoreMapper(EnsembleMapper):
    def __init__(self, session, scored):
        super().__init__(session)
        self._scored = scored

    async def score_candidates(self, question, candidates, *, acceptable_terms=None):
        return self._scored


def _question() -> ExamQuestion:
    return ExamQuestion(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        question_ref="q1",
        text="Explain binary search.",
    )


def _node() -> CurriculumNode:
    return CurriculumNode(
        id=uuid.uuid4(),
        node_type=NodeType.OBJECTIVE,
        label="Binary search",
        origin=Origin.OFFICIAL,
        confidence=1.0,
    )


def _candidate(node: CurriculumNode, weight: float, confidence: float) -> MappingCandidate:
    return MappingCandidate(
        node=node,
        scores=SignalScores(lexical=confidence),
        weight=weight,
        confidence=confidence,
    )


async def test_llm_scores_accepts_markdown_fenced_json():
    node = CurriculumNode(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        node_type=NodeType.OBJECTIVE,
        label="Binary search",
        origin=Origin.OFFICIAL,
        confidence=1.0,
    )

    scores = await _llm_scores(FakeLLMChain(), "Explain binary search.", [node])

    assert scores == {node.id: 0.75}


async def test_map_question_updates_existing_machine_mapping_instead_of_duplicating():
    question = _question()
    node = _node()
    existing = QuestionNodeMapping(
        question_id=question.id,
        node_id=node.id,
        weight=0.2,
        confidence=0.2,
        mapping_method=MappingMethod.HYBRID,
    )
    session = FakeSession(existing=[existing])

    mappings = await FixedScoreMapper(session, [_candidate(node, 0.8, 0.8)]).map_question(
        question, [node]
    )

    assert mappings == [existing]
    assert session.added == []
    assert existing.weight == 0.8
    assert existing.confidence == 0.8
    assert existing.mapping_method == MappingMethod.HYBRID
    assert session.committed


async def test_map_question_preserves_human_corrected_mapping():
    question = _question()
    node = _node()
    existing = QuestionNodeMapping(
        question_id=question.id,
        node_id=node.id,
        weight=1.0,
        confidence=1.0,
        mapping_method=MappingMethod.HUMAN_CORRECTED,
        corrected_by="teacher-1",
    )
    session = FakeSession(existing=[existing])

    mappings = await FixedScoreMapper(session, [_candidate(node, 0.3, 0.3)]).map_question(
        question, [node]
    )

    assert mappings == [existing]
    assert session.added == []
    assert existing.weight == 1.0
    assert existing.confidence == 1.0
    assert existing.mapping_method == MappingMethod.HUMAN_CORRECTED
    assert existing.corrected_by == "teacher-1"
    assert session.committed
