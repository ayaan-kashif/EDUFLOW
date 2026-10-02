from uuid import uuid4

from app.domain.models import SourceSpan
from app.generation.claims import GeneratedClaim
from app.generation.evidence import check_evidence
from app.ingestion.service import hash_span_text


def span(text="Enzymes are biological catalysts."):
    return SourceSpan(id=uuid4(), text=text, content_hash=hash_span_text(text))


def test_fabricated_span_id_is_rejected_even_when_other_citations_resolve():
    s = span()
    claim = GeneratedClaim(s.text, [str(s.id), str(uuid4())])
    assert not check_evidence(claim, [s]).valid


def test_fabricated_quotation_is_rejected():
    s = span()
    claim = GeneratedClaim(
        "Enzymes are immortal.", [str(s.id)], {str(s.id): "Enzymes never decay."}
    )
    assert not check_evidence(claim, [s]).valid


def test_source_hash_drift_is_rejected():
    s = span()
    s.text = "Changed content"
    assert not check_evidence(GeneratedClaim(s.text, [str(s.id)]), [s]).valid


def test_resolvable_exact_quote_still_requires_semantic_verification():
    s = span()
    check = check_evidence(GeneratedClaim(s.text, [str(s.id)], {str(s.id): s.text}), [s])
    assert check.valid and check.exact_match
    assert "semantic verification still required" in check.reason
