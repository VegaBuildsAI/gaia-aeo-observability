"""
Stub del adapter de Perplexity. Se activa cuando exista PERPLEXITY_API_KEY.
La API Sonar devuelve `citations` nativas — ideal para AEO.
"""
import os

from .base import EngineAdapter, EngineResponse


class PerplexityAdapter(EngineAdapter):
    name = "perplexity"

    def available(self) -> bool:
        return bool(os.getenv("PERPLEXITY_API_KEY"))

    def run(self, prompt_text: str) -> EngineResponse:
        return EngineResponse(
            model="sonar",
            error="Adapter Perplexity no implementado — setear PERPLEXITY_API_KEY y completar run().",
        )
