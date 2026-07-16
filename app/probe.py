"""
Orquestador de sondeos. Corre la batería de prompts × motores activos, extrae
las señales AEO y las persiste deduplicando por (fecha, prompt, engine) — espeja
la lógica acumulativa de jps_accumulate.py.
"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import select

from . import config, matching
from .db import get_session
from .engines import get_adapter
from .models import ProbeResult, ProbeRun, ProbeRunResult
from .prompts import PROMPTS

# Log en memoria para que el dashboard muestre la consola en vivo (estilo JPS).
STATE = {
    "status": "idle",
    "log": [],
    "last_run": None,
    "last_run_id": None,
    "progress": 0.0,
}


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


def _today() -> str:
    """Fecha del día en UTC. Única fuente de la fecha del sondeo — nunca hardcodear."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def new_run_id() -> str:
    return str(uuid4())


def run(
    engines: list[str] | None = None,
    date: str | None = None,
    run_id: str | None = None,
    trigger: str = "manual",
) -> dict:
    """Corre un ciclo completo de sondeo. Devuelve un resumen."""
    engines = engines or config.active_engines()
    date = date or _today()
    run_id = run_id or new_run_id()

    STATE.update(status="running", progress=0.0, last_run_id=run_id)
    _create_run(run_id, date, trigger, engines)
    _log(f"Inicio de sondeo · run_id={run_id} · fecha={date} · motores={engines}", "head")

    total = len(PROMPTS) * len(engines)
    done = 0
    inserted = updated = errors = executions_written = 0

    try:
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
                _append_run_result(run_id, row)
                executions_written += 1
                ins = _upsert(row)
                inserted += ins
                updated += (0 if ins else 1)

                done += 1
                STATE["progress"] = round(done / total, 3)

        completed_at = datetime.now(timezone.utc)
        STATE.update(status="done", last_run=completed_at.isoformat())
        summary = {
            "run_id": run_id,
            "date": date,
            "engines": engines,
            "prompts": len(PROMPTS),
            "executions_written": executions_written,
            "inserted": inserted,
            "updated": updated,
            "errors": errors,
        }
        _finish_run(run_id, "done", summary, completed_at)
        _log(f"Sondeo completo · {summary}", "head")

        # Congela snapshots diarios de métricas para gráficas de tendencia.
        from . import analytics
        analytics.snapshot_day(date)
        return summary
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        summary = {
            "run_id": run_id,
            "date": date,
            "engines": engines,
            "prompts": len(PROMPTS),
            "executions_written": executions_written,
            "inserted": inserted,
            "updated": updated,
            "errors": errors + 1,
            "failure": str(exc)[:1000],
        }
        STATE.update(status="failed", last_run=completed_at.isoformat())
        _finish_run(run_id, "failed", summary, completed_at)
        _log(f"Sondeo fallido · run_id={run_id} · {exc}", "err")
        raise


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


def _create_run(run_id: str, date: str, trigger: str, engines: list[str]) -> None:
    with get_session() as s:
        s.add(ProbeRun(
            id=run_id,
            date=date,
            trigger=trigger,
            status="running",
            engines=list(engines),
            prompts_total=len(PROMPTS),
        ))
        s.commit()


def _append_run_result(run_id: str, row: ProbeResult) -> None:
    """Persist one immutable result before refreshing the daily dashboard row."""
    event = ProbeRunResult(
        run_id=run_id,
        date=row.date,
        prompt_id=row.prompt_id,
        engine=row.engine,
        ts=row.ts,
        model=row.model,
        prompt_text=row.prompt_text,
        prompt_class=row.prompt_class,
        lang=row.lang,
        answer_text=row.answer_text,
        gaia_mentioned=row.gaia_mentioned,
        gaia_in_citations=row.gaia_in_citations,
        citation_rank=row.citation_rank,
        sentiment=row.sentiment,
        latency_ms=row.latency_ms,
        cited_domains=list(row.cited_domains),
        competitors_mentioned=list(row.competitors_mentioned),
        error=row.error,
    )
    with get_session() as s:
        s.add(event)
        s.commit()


def _finish_run(
    run_id: str,
    status: str,
    summary: dict,
    completed_at: datetime,
) -> None:
    with get_session() as s:
        record = s.get(ProbeRun, run_id)
        if not record:
            return
        record.status = status
        record.completed_at = completed_at
        record.executions_written = int(summary.get("executions_written", 0))
        record.errors = int(summary.get("errors", 0))
        record.summary = summary
        s.add(record)
        s.commit()
