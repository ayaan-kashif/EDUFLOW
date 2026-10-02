"""Hugging Face routed inference using the existing OpenAI-compatible client."""

from app.config import Settings
from app.providers.llm.openai_compatible import OpenAICompatibleLLMProvider

BASE_URL = "https://router.huggingface.co/v1"


class HuggingFaceLLMProvider(OpenAICompatibleLLMProvider):
    def __init__(self, settings: Settings):
        super().__init__(name="huggingface", model=settings.hf_model,
                         base_url=BASE_URL, api_key=settings.hf_token)


class HuggingFaceVerifyLLMProvider(OpenAICompatibleLLMProvider):
    def __init__(self, settings: Settings):
        if settings.hf_verify_model.split(":")[0] == settings.hf_model.split(":")[0]:
            raise ValueError("Hugging Face verification must use a different model")
        super().__init__(name="huggingface_verify", model=settings.hf_verify_model,
                         base_url=BASE_URL, api_key=settings.hf_token)
