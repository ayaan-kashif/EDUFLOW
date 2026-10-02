"""Mechanical citation checks. Text overlap is a retrieval signal, not truth verification."""

import hashlib
import re
from dataclasses import dataclass


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


@dataclass(frozen=True)
class EvidenceCheck:
    valid: bool
    reason: str
    exact_match: bool = False


def check_evidence(claim, spans):
    available = {str(s.id): s for s in spans}
    if not claim.evidence_span_ids or any(eid not in available for eid in claim.evidence_span_ids):
        return EvidenceCheck(False, "Missing or unresolvable evidence citation")
    for span in spans:
        if re.fullmatch(r"sha256:[a-f0-9]{64}", span.content_hash or ""):
            actual = "sha256:" + hashlib.sha256(span.text.encode()).hexdigest()
            if actual != span.content_hash:
                return EvidenceCheck(False, "Source text no longer matches its stored hash")
    for sid, quote in claim.evidence_quotes.items():
        if (
            sid not in available
            or not quote.strip()
            or normalize(quote) not in normalize(available[sid].text)
        ):
            return EvidenceCheck(False, "A quoted passage does not occur in its cited source")
    exact = any(normalize(claim.text) in normalize(s.text) for s in spans)
    return EvidenceCheck(True, "Citations resolve; semantic verification still required", exact)
