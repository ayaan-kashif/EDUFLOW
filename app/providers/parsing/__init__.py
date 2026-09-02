import logging
from collections.abc import Callable

from app.config import get_provider_config, get_settings
from app.providers.router import FallbackChain, ProviderRouter

logger = logging.getLogger(__name__)

# docling is deliberately absent from this map. It's still importable via
# get_docling_router() below, but it downloads a layout model on first
# .convert() call, so it must never be reachable from the default chain —
# a document upload should not trigger a multi-hundred-MB download.
def _anydoc_provider():
    from app.providers.parsing.anydoc_provider import AnydocParserProvider

    return AnydocParserProvider()


def _pypdf_provider():
    from app.providers.parsing.pypdf_provider import PyPdfParserProvider

    return PyPdfParserProvider()


def _vision_llm_provider():
    from app.providers.parsing.vision_llm_provider import VisionLLMParserProvider

    return VisionLLMParserProvider(get_settings())


_PARSER_PROVIDERS: dict[str, Callable[[], object]] = {
    "anydoc": _anydoc_provider,
    "pypdf_text": _pypdf_provider,
    "vision_llm_ocr": _vision_llm_provider,
}


def get_parser_chain() -> FallbackChain:
    """Ordered parser fallback per config/providers.yaml's parsing.priority.

    Unlike the LLM chains, the ordering here isn't about provider
    reliability — it's a capability ladder. anydoc parses a text-layer PDF
    or office document deterministically and raises ProviderError on an
    image-only PDF; vision_llm_ocr then picks those up and OCRs them via a
    multimodal LLM, which is slower and costs tokens. Cheapest correct
    parser first, in other words, with the expensive one reached only when
    the cheap one genuinely can't read the file.
    """
    priority = get_provider_config()["parsing"]["priority"]
    routers: list[tuple[str, ProviderRouter]] = []
    for name in priority:
        try:
            provider = _PARSER_PROVIDERS[name]()
        except (ImportError, ValueError) as exc:
            # Same posture as the LLM chain: an optional provider
            # dependency missing, or an unconfigured provider
            # (vision_llm_ocr with no OPENROUTER_API_KEY), is skipped, not
            # a failure.
            logger.debug("parsing: skipping %s: %s", name, exc)
            continue
        # retry_attempts=1: a parser failure here is almost always "this
        # provider can't read this file", which retrying won't fix — the
        # chain moving to the next provider is the actual recovery. The
        # vision provider does its own per-page retry internally.
        routers.append((name, ProviderRouter(provider, retry_attempts=1)))
    if not routers:
        raise ValueError(
            f"parsing: no provider in {priority} is configured — see .env.example"
        )
    return FallbackChain(routers)


def get_docling_router() -> ProviderRouter:
    """Layout-aware parsing with true per-paragraph bounding boxes. NOT in
    the default chain: its layout model downloads on first use. Pass
    explicitly to IngestionService(parser_router=...) when that download is
    acceptable and paragraph-level provenance is worth it.
    """
    from app.providers.parsing.docling_provider import DoclingParserProvider

    return ProviderRouter(DoclingParserProvider())


def get_anydoc_router() -> ProviderRouter:
    """Office formats (docx/pptx/xlsx/odt/rtf/epub) and text-layer PDFs, no
    ML models. Raises ProviderError on scanned/image-only PDFs.
    """
    return ProviderRouter(_anydoc_provider())


def get_pypdf_router() -> ProviderRouter:
    """No-ML-model plain-text PDF fallback (app/providers/parsing/pypdf_provider.py)."""
    return ProviderRouter(_pypdf_provider())


def get_vision_llm_router() -> ProviderRouter:
    """OCR-via-multimodal-LLM for scanned PDFs with no text layer at all."""
    return ProviderRouter(_vision_llm_provider(), retry_attempts=2)
