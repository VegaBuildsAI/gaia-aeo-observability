"""
Stub del adapter de OpenAI (ChatGPT). Se activa cuando exista OPENAI_API_KEY.
Implementar con la Responses API + herramienta `web_search` para paridad con Claude.
"""
import os

from .base import EngineAdapter, EngineResponse


class OpenAIAdapter(EngineAdapter):
    name = "openai"

    def available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def run(self, prompt_text: str) -> EngineResponse:
        return EngineResponse(
            model="gpt-4o",
            error="Adapter OpenAI no implementado — setear OPENAI_API_KEY y completar run().",
        )
