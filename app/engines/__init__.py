"""Adapters de motores de IA. Claude implementado; el resto son stubs."""
from .base import EngineAdapter, EngineResponse
from .claude import ClaudeWebSearchAdapter
from .openai import OpenAIAdapter
from .perplexity import PerplexityAdapter
from .gemini import GeminiAdapter

_REGISTRY: dict[str, type[EngineAdapter]] = {
    "claude": ClaudeWebSearchAdapter,
    "openai": OpenAIAdapter,
    "perplexity": PerplexityAdapter,
    "gemini": GeminiAdapter,
}


def get_adapter(name: str) -> EngineAdapter:
    if name not in _REGISTRY:
        raise ValueError(f"Motor desconocido: {name}")
    return _REGISTRY[name]()


__all__ = ["EngineAdapter", "EngineResponse", "get_adapter"]
