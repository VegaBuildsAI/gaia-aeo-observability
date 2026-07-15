"""
Gaia AEO Assistant — chatbot montado sobre el motor (misma funcionalidad y
tratamiento visual que el chat de JPS Tiempos Lab).

Usa Claude con *tools* que leen la base de datos en vivo, así que responde solo
con datos reales del motor de observabilidad. La respuesta final se emite como
SSE (streaming por chunks) para el widget del dashboard.
"""
import json

import anthropic

from . import analytics, config

SYSTEM = f"""Eres el "Gaia AEO Assistant", analista de observabilidad AEO para {config.BRAND_NAME} ({config.BRAND_DOMAIN}).
Respondes preguntas sobre si los motores de IA citan a {config.BRAND_NAME}, cómo evoluciona en el tiempo y cómo se compara con competidores (Casa de las Estrellas, Futuro Verde).
Reglas:
- Usa SIEMPRE las herramientas para leer datos reales; nunca inventes cifras.
- Sé conciso y concreto. Reporta tasas como porcentaje con su intervalo de confianza cuando exista.
- No prometas posiciones de ranking ni resultados garantizados; describe lo observado.
- Responde en el idioma del usuario (español por defecto)."""

TOOLS = [
    {"name": "get_citation_rate",
     "description": "Tasa de citación de la marca (global, por motor y por clase de query) con intervalo de confianza.",
     "input_schema": {"type": "object", "properties": {
         "since": {"type": "string", "description": "Fecha ISO opcional YYYY-MM-DD para filtrar desde."}}}},
    {"name": "get_trend",
     "description": "Tendencia de la tasa de citación en la ventana de la campaña (dirección, delta, z-score) y serie diaria.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_competitors",
     "description": "Share of voice: menciones de la marca vs competidores.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_recent_probes",
     "description": "Ranking de dominios citados por las IA y efectividad por prompt.",
     "input_schema": {"type": "object", "properties": {}}},
]


def _tool(name: str, args: dict) -> dict:
    rep = analytics.full_report(since=args.get("since"))
    if name == "get_citation_rate":
        return {"overall": rep["overall"], "by_engine": rep["by_engine"], "by_class": rep["by_class"]}
    if name == "get_trend":
        return {"trend": rep["trend"], "daily_series": rep["daily_series"], "anomalies": rep["anomalies"]}
    if name == "get_competitors":
        return rep["share_of_voice"]
    if name == "get_recent_probes":
        return {"cited_domains": rep["cited_domains"], "prompt_effectiveness": rep["prompt_effectiveness"][:10]}
    return {"error": f"tool desconocida: {name}"}


def _sse(event: str, data: dict | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def stream_reply(messages: list[dict]):
    """Generator SSE: resuelve el loop de tools y luego emite el texto final por chunks."""
    if not config.ANTHROPIC_API_KEY:
        yield _sse("error", {"message": "ANTHROPIC_API_KEY no configurada."})
        yield _sse("done", "1")
        return

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    convo = list(messages)

    try:
        # Loop de herramientas (máx 4 rondas para evitar bucles).
        for _ in range(4):
            resp = client.messages.create(
                model=config.CHAT_MODEL, max_tokens=1024,
                system=SYSTEM, tools=TOOLS, messages=convo,
            )
            if resp.stop_reason != "tool_use":
                final = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
                for i in range(0, len(final), 40):     # emula streaming
                    yield _sse("token", final[i:i + 40])
                yield _sse("done", "1")
                return

            convo.append({"role": "assistant", "content": resp.content})
            results = []
            for b in resp.content:
                if getattr(b, "type", "") == "tool_use":
                    yield _sse("tool", {"name": b.name})
                    out = _tool(b.name, b.input or {})
                    results.append({"type": "tool_result", "tool_use_id": b.id,
                                    "content": json.dumps(out, ensure_ascii=False)})
            convo.append({"role": "user", "content": results})

        yield _sse("token", "No pude completar el análisis en los pasos disponibles.")
        yield _sse("done", "1")
    except Exception as e:
        yield _sse("error", {"message": f"{type(e).__name__}: {e}"})
        yield _sse("done", "1")
