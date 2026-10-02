"""Shared implementation for the many LLM providers that speak the OpenAI
chat-completions wire format (Groq, OpenRouter, Together, Fireworks,
Ollama, ...). Only base_url / api_key / default model differ between them
— see the thin per-provider modules in this package.
"""

from typing import cast

from openai import APIError, APIStatusError, AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.providers.base import LLMMessage, LLMProvider, LLMResponse, ProviderError


class OpenAICompatibleLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        name: str,
        model: str,
        base_url: str,
        api_key: str | None,
        requires_api_key: bool = True,
    ):
        if requires_api_key and not api_key:
            raise ValueError(f"{name}: no API key configured")
        if not model or not model.strip():
            raise ValueError(f"{name}: no model configured")
        self.name = name
        self._model = model
        # Local providers (Ollama) don't check the key; the SDK still wants
        # a non-empty string.
        # ProviderRouter owns retries; SDK retries would multiply every attempt.
        self._client = AsyncOpenAI(api_key=api_key or "not-required", base_url=base_url,
                                   max_retries=0)

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[cast(ChatCompletionMessageParam, {"role": m.role, "content": m.content}) for m in messages],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except APIStatusError as exc:
            reason = {401: "Invalid or expired API token", 403: "Token lacks inference permission or model access",
                      402: "Inference credits exhausted; check provider billing", 404: "Model or endpoint unavailable",
                      429: "Provider rate limit reached"}.get(exc.status_code, "Provider request failed")
            raise ProviderError(f"{self.name}: HTTP {exc.status_code}: {reason}") from exc
        except APIError as exc:
            raise ProviderError(f"{self.name}: connection or timeout failure") from exc

        choice = response.choices[0]
        usage = response.usage

        # An empty completion is a failed call, not a valid answer. It
        # happens for real: a reasoning model can burn the whole max_tokens
        # budget on internal thinking and return finish_reason="length"
        # with no content at all. Passing "" up the stack turns that into a
        # JSON parse error at the call site, which the generation pipeline
        # then records as NOT_CHECKED — a provider truncation quietly
        # becoming an unverifiable claim. Raising instead lets the router
        # retry and the fallback chain move on.
        text = choice.message.content or ""
        if not text.strip():
            raise ProviderError(
                f"{self.name}: empty completion from {response.model} "
                f"(finish_reason={choice.finish_reason!r}) — "
                "raise max_tokens if this model reasons before answering"
            )

        return LLMResponse(
            text=text,
            model=response.model,
            provider=self.name,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
