"""
Stub del adapter de Gemini (Google). Se activa cuando exista GEMINI_API_KEY.
Implementar con `google-genai` + grounding con Google Search para paridad.
"""
import os

from .base import EngineAdapter, EngineResponse


class GeminiAdapter(EngineAdapter):
    name = "gemini"

    def available(self) -> bool:
        return bool(os.getenv("GEMINI_API_KEY"))

    def run(self, prompt_text: str) -> EngineResponse:
        return EngineResponse(
            model="gemini-2.0-flash",
            error="Adapter Gemini no implementado — setear GEMINI_API_KEY y completar run().",
        )
