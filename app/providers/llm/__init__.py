import logging
from collections.abc import Callable

from app.config import Settings, get_provider_config, get_settings
from app.providers.router import FallbackChain, ProviderRouter

logger = logging.getLogger(__name__)


def _anthropic_provider():
    from app.providers.llm.anthropic_provider import AnthropicLLMProvider

    return AnthropicLLMProvider


def _openai_provider():
    from app.providers.llm.openai_provider import OpenAILLMProvider

    return OpenAILLMProvider


def _groq_provider():
    from app.providers.llm.groq_provider import GroqLLMProvider

    return GroqLLMProvider


def _openrouter_provider():
    from app.providers.llm.openrouter_provider import OpenRouterLLMProvider

    return OpenRouterLLMProvider


def _together_provider():
    from app.providers.llm.together_provider import TogetherLLMProvider

    return TogetherLLMProvider


def _fireworks_provider():
    from app.providers.llm.fireworks_provider import FireworksLLMProvider

    return FireworksLLMProvider


def _ollama_provider():
    from app.providers.llm.ollama_provider import OllamaLLMProvider

    return OllamaLLMProvider


def _ollama_verify_provider():
    from app.providers.llm.ollama_provider import OllamaVerifyLLMProvider

    return OllamaVerifyLLMProvider


_LLM_PROVIDERS: dict[str, Callable[[], type]] = {
    "anthropic": _anthropic_provider,
    "openai": _openai_provider,
    "groq": _groq_provider,
    "openrouter": _openrouter_provider,
    "together": _together_provider,
    "fireworks": _fireworks_provider,
    "ollama": _ollama_provider,
    "ollama_verify": _ollama_verify_provider,
}


def _build_chain(capability: str, settings: Settings) -> FallbackChain:
    config = get_provider_config()["llm"][capability]
    routers: list[tuple[str, ProviderRouter]] = []
    for name in config["priority"]:
        try:
            provider_cls = _LLM_PROVIDERS[name]()
            provider = provider_cls(settings)
        except (ImportError, ValueError) as exc:
            # Optional provider dependency missing or no API key
            # configured — skip it rather than fail the whole chain. Not a
            # runtime provider failure, so it isn't logged as a warning.
            logger.debug("llm.%s: skipping %s: %s", capability, name, exc)
            continue
        routers.append(
            (
                name,
                ProviderRouter(
                    provider,
                    retry_attempts=config["retry"]["attempts"],
                    backoff_seconds=config["retry"]["backoff_seconds"],
                    circuit_breaker_threshold=config["circuit_breaker"]["failure_threshold"],
                    circuit_breaker_cooldown_seconds=config["circuit_breaker"]["cooldown_seconds"],
                ),
            )
        )
    if not routers:
        raise ValueError(
            f"llm.{capability}: no provider in {config['priority']} is configured "
            "(missing API keys?) — see .env.example"
        )
    return FallbackChain(routers)


def get_generation_chain() -> FallbackChain:
    """LLM calls that draft content. Lower trust stakes than verification."""
    return _build_chain("generation", get_settings())


def get_verification_chain() -> FallbackChain:
    """LLM calls that check a generated claim against its cited evidence.

    The first *configured* provider in this chain must differ from
    generation's first configured provider — see config/providers.yaml.
    This is the product's core trust mechanism: a model should not grade
    its own homework. Config-time ordering isn't enough on its own once
    fallback is in play (if generation falls through to provider B, a
    verification chain that also starts with B would silently violate the
    rule) — callers that know which provider actually generated a claim
    should pass it in `exclude` on FallbackChain.call() too.
    """
    settings = get_settings()
    generation_primary = _build_chain("generation", settings).provider_names[0]
    verification_chain = _build_chain("verification", settings)
    if verification_chain.provider_names[0] == generation_primary:
        raise ValueError(
            "config/providers.yaml: the first configured provider in "
            "llm.verification.priority must differ from llm.generation.priority "
            "(see 04_PROVIDER_STRATEGY.md) — got "
            f"{generation_primary!r} for both"
        )
    return verification_chain
