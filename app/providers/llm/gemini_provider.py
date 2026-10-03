"""Gemini through Google's OpenAI-compatible chat endpoint."""

from app.config import Settings
from app.providers.llm.openai_compatible import OpenAICompatibleLLMProvider

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class GeminiLLMProvider(OpenAICompatibleLLMProvider):
    def __init__(self, settings: Settings):
        super().__init__(name="gemini", model=settings.gemini_model,
                         base_url=BASE_URL, api_key=settings.gemini_api_key)
