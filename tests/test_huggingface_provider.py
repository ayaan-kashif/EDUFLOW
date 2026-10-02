from types import SimpleNamespace

import pytest

from app.config import Settings
from app.providers.base import LLMMessage
from app.providers.llm import _build_chain
from app.providers.llm.huggingface_provider import (
    HuggingFaceLLMProvider,
    HuggingFaceVerifyLLMProvider,
)


def settings(**overrides):
    return Settings(_env_file=None, database_url="sqlite+aiosqlite:///:memory:",
                    hf_token="test-token", ollama_model="", ollama_verify_model="", **overrides)


def test_huggingface_is_primary_and_verification_uses_a_different_model():
    config = settings()
    assert _build_chain("generation", config).provider_names == ["huggingface"]
    assert _build_chain("verification", config).provider_names == ["huggingface_verify"]
    assert config.hf_model.split(":")[0] != config.hf_verify_model.split(":")[0]


def test_same_model_on_different_routes_cannot_verify_itself():
    config = settings(hf_model="Qwen/model:nscale", hf_verify_model="Qwen/model:other")
    with pytest.raises(ValueError, match="different model"):
        HuggingFaceVerifyLLMProvider(config)


async def test_provider_uses_backend_token_and_normalizes_response(monkeypatch):
    from app.providers.llm import openai_compatible

    captured = {}

    async def create(**body):
        captured["body"] = body
        return SimpleNamespace(model="Qwen/test", choices=[SimpleNamespace(
            message=SimpleNamespace(content='{"nodes":[]}'), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))

    def client(**config):
        captured["config"] = config
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    monkeypatch.setattr(openai_compatible,"AsyncOpenAI",client)
    provider = HuggingFaceLLMProvider(settings())
    result = await provider.complete([LLMMessage(role="user",content="Extract objectives")])
    assert captured["config"]["api_key"] == "test-token"
    assert captured["config"]["base_url"] == "https://router.huggingface.co/v1"
    assert captured["config"]["max_retries"] == 0
    assert "test-token" not in str(captured["body"])
    assert result.provider == "huggingface"
    assert result.text == '{"nodes":[]}'
    assert result.input_tokens == 10
