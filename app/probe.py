"""
Orquestador de sondeos. Corre la batería de prompts × motores activos, extrae
las señales AEO y las persiste deduplicando por (fecha, prompt, engine) — espeja
la lógica acumulativa de jps_accumulate.py.
"""
from datetime import datetime, timezone

from sqlmodel import select

from . import config, matching
from .db import get_session
from .engines import get_adapter
from .models import ProbeResult
from .prompts import PROMPTS

# Log en memoria para que el dashboard muestre la consola en vivo (estilo JPS).
STATE = {"status": "idle", "log": [], "last_run": None, "progress": 0.0}


def _log(msg: str, level: str = "info") -> None:
    line = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg}
    STATE["log"].append(line)
    STATE["log"] = STATE["log"][-300:]  # cap
    # Print defensivo: consolas Windows (cp1252) no codifican ✓/·/emoji → no crashear.
    try:
        print(f"[probe:{level}] {msg}")
    except UnicodeEncodeError:
        import sys
        sys.stdout.buffer.write(f"[probe:{level}] {msg}\n".encode("utf-8", "replace"))


def run(engines: list[str] | None = None, date: str | None = None) -> dict:
    """Corre un ciclo completo de sondeo. Devuelve un resumen."""
    engines = engines or config.active_engines()
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    STATE.update(status="running", progress=0.0)
    _log(f"Inicio de sondeo · fecha={date} · motores={engines}", "head")

    total = len(PROMPTS) * len(engines)
    done = 0
    inserted = updated = errors = 0

    for engine_name in engines:
        adapter = get_adapter(engine_name)
        if not adapter.available():
            _log(f"Motor '{engine_name}' sin key — se omite.", "warn")
            done += len(PROMPTS)
            continue

        for p in PROMPTS:
            resp = adapter.run(p["text"])
            if resp.error:
                errors += 1
                _log(f"{engine_name}/{p['id']} → ERROR: {resp.error}", "err")
            else:
                cited = resp.cited_domains
                in_cite, rank = matching.brand_citation_rank(cited)
                mentioned = matching.brand_mentioned(resp.answer_text)
                status = "✓ cita" if (mentioned or in_cite) else "· sin cita"
                _log(f"{engine_name}/{p['id']} {status} "
                     f"(fuentes={len(cited)}, comp={len(matching.competitors_in(resp.answer_text))})",
                     "ok" if (mentioned or in_cite) else "info")

            row = _to_row(engine_name, p, resp, date)
            ins = _upsert(row)
            inserted += ins
            updated += (0 if ins else 1)

            done += 1
            STATE["progress"] = round(done / total, 3)

    STATE.update(status="done", last_run=datetime.now(timezone.utc).isoformat())
    summary = {"date": date, "engines": engines, "prompts": len(PROMPTS),
               "inserted": inserted, "updated": updated, "errors": errors}
    _log(f"Sondeo completo · {summary}", "head")

    # Congela snapshots diarios de métricas para gráficas de tendencia.
    from . import analytics
    analytics.snapshot_day(date)
    return summary


def _to_row(engine_name, p, resp, date) -> ProbeResult:
    if resp.error:
        return ProbeResult(
            date=date, prompt_id=p["id"], engine=engine_name, model=resp.model,
            prompt_text=p["text"], prompt_class=p["cls"], lang=p["lang"],
            latency_ms=resp.latency_ms, error=resp.error, sentiment="n/a",
        )
    cited = resp.cited_domains
    in_cite, rank = matching.brand_citation_rank(cited)
    return ProbeResult(
        date=date, prompt_id=p["id"], engine=engine_name, model=resp.model,
        prompt_text=p["text"], prompt_class=p["cls"], lang=p["lang"],
        answer_text=resp.answer_text[:6000],
        gaia_mentioned=matching.brand_mentioned(resp.answer_text),
        gaia_in_citations=in_cite, citation_rank=rank,
        sentiment=matching.sentiment_around_brand(resp.answer_text),
        latency_ms=resp.latency_ms, cited_domains=cited,
        competitors_mentioned=matching.competitors_in(resp.answer_text),
    )


def _upsert(row: ProbeResult) -> int:
    """Devuelve 1 si insertó, 0 si actualizó una fila existente (misma clave)."""
    with get_session() as s:
        existing = s.exec(
            select(ProbeResult).where(
                ProbeResult.date == row.date,
                ProbeResult.prompt_id == row.prompt_id,
                ProbeResult.engine == row.engine,
            )
        ).first()
        if existing:
            for f in ("model", "prompt_text", "prompt_class", "lang", "answer_text",
                      "gaia_mentioned", "gaia_in_citations", "citation_rank", "sentiment",
                      "latency_ms", "cited_domains", "competitors_mentioned", "error", "ts"):
                setattr(existing, f, getattr(row, f))
            s.add(existing)
            s.commit()
            return 0
        s.add(row)
        s.commit()
        return 1
