"""
Adapter de Claude con la herramienta nativa `web_search`.

Cada probe envía el prompt; Claude busca en la web en vivo y responde CON
citaciones. Extraemos: (a) el texto de la respuesta y (b) las fuentes citadas
(URLs/dominios). Esto convierte a Claude en un motor de IA real que medimos y,
a la vez, en un telescopio de lo que la web accesible-a-IA dice sobre Gaia.

Doc de la herramienta: tool type "web_search_20250305".
"""
import time

import anthropic

from .. import config
from .base import Citation, EngineAdapter, EngineResponse

_SYSTEM = (
    "You are answering a parent's question about schools. Search the web and give "
    "a concise, factual answer. Name specific schools with their websites when relevant."
)


class ClaudeWebSearchAdapter(EngineAdapter):
    name = "claude"

    def available(self) -> bool:
        return bool(config.ANTHROPIC_API_KEY)

    def run(self, prompt_text: str) -> EngineResponse:
        if not self.available():
            return EngineResponse(model=config.CLAUDE_MODEL,
                                  error="ANTHROPIC_API_KEY no configurada")
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        t0 = time.time()
        try:
            resp = client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.PROBE_MAX_TOKENS,
                system=_SYSTEM,
                messages=[{"role": "user", "content": prompt_text}],
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": config.WEB_SEARCH_MAX_USES,
                }],
            )
        except Exception as e:  # red, auth, rate-limit
            return EngineResponse(model=config.CLAUDE_MODEL,
                                  latency_ms=int((time.time() - t0) * 1000),
                                  error=f"{type(e).__name__}: {e}")

        latency = int((time.time() - t0) * 1000)
        return _parse(resp, latency)


def _parse(resp, latency_ms: int) -> EngineResponse:
    """Recorre los content blocks: junta texto y recolecta citaciones (en orden)."""
    text_parts: list[str] = []
    citations: list[Citation] = []
    seen: set[str] = set()

    def add_cite(url: str, title: str = ""):
        url = (url or "").strip()
        if not url or url in seen:
            return
        seen.add(url)
        from ..matching import domain_of
        citations.append(Citation(url=url, domain=domain_of(url), title=title or ""))

    for block in getattr(resp, "content", []) or []:
        btype = getattr(block, "type", "")
        # 1) Bloques de texto: pueden llevar citations embebidas (orden de aparición).
        if btype == "text":
            text_parts.append(getattr(block, "text", "") or "")
            for c in (getattr(block, "citations", None) or []):
                add_cite(getattr(c, "url", ""), getattr(c, "title", ""))
        # 2) Resultado de la búsqueda web (fuentes que Claude consultó).
        elif btype == "web_search_tool_result":
            content = getattr(block, "content", None) or []
            for r in content:
                add_cite(getattr(r, "url", ""), getattr(r, "title", ""))

    return EngineResponse(
        answer_text="".join(text_parts).strip(),
        citations=citations,
        model=getattr(resp, "model", config.CLAUDE_MODEL),
        latency_ms=latency_ms,
    )
