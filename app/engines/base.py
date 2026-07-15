"""Interfaz común de los adapters de motor."""
from dataclasses import dataclass, field


@dataclass
class Citation:
    url: str = ""
    domain: str = ""
    title: str = ""


@dataclass
class EngineResponse:
    """Respuesta normalizada de cualquier motor de IA."""
    answer_text: str = ""
    citations: list[Citation] = field(default_factory=list)
    model: str = ""
    latency_ms: int = 0
    error: str | None = None

    @property
    def cited_domains(self) -> list[str]:
        seen, out = set(), []
        for c in self.citations:
            if c.domain and c.domain not in seen:
                seen.add(c.domain)
                out.append(c.domain)
        return out


class EngineAdapter:
    """Contrato: `run(prompt_text) -> EngineResponse`."""
    name: str = "base"

    def available(self) -> bool:
        """¿Tiene la key/config necesaria para correr?"""
        return False

    def run(self, prompt_text: str) -> EngineResponse:
        raise NotImplementedError
