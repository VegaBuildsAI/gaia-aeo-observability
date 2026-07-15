"""
Analítica AEO — estadística propia, sin dependencias pesadas (espeja el enfoque
de jps_edge_tool.py: CI binomial de Wilson, z-score, ventanas móviles).

Métricas:
  • Citation Rate (global / por motor / por clase) con intervalo de confianza.
  • Share of Voice: Gaia vs competidores.
  • Tendencia en la ventana de 2 meses (pendiente + z-score del cambio).
  • Prompt effectiveness (qué prompts elicitan mejor a Gaia).
  • Ranking de dominios citados (mapa competitivo de fuentes).
  • Anomalías (caídas/saltos abruptos).
"""
import math
from collections import Counter, defaultdict

from sqlmodel import select

from . import config
from .db import get_session
from .models import MetricSnapshot, ProbeResult


# ─── Primitivas estadísticas (estilo jps_edge_tool) ─────────────────────────
def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de confianza de Wilson para una proporción (95% por defecto)."""
    if n == 0:
        return 0.0, 0.0
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = (z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))) / denom
    return round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)


def _z_score(observed: float, mean: float, sd: float) -> float:
    return round((observed - mean) / sd, 3) if sd > 0 else 0.0


# ─── Carga de datos ─────────────────────────────────────────────────────────
def _rows(since: str | None = None) -> list[ProbeResult]:
    with get_session() as s:
        q = select(ProbeResult).where(ProbeResult.error.is_(None))
        if since:
            q = q.where(ProbeResult.date >= since)
        return list(s.exec(q).all())


def _is_hit(r: ProbeResult) -> bool:
    return bool(r.gaia_mentioned or r.gaia_in_citations)


# ─── Métricas agregadas ─────────────────────────────────────────────────────
def citation_rate(rows: list[ProbeResult]) -> dict:
    n = len(rows)
    k = sum(1 for r in rows if _is_hit(r))
    lo, hi = wilson_ci(k, n)
    return {"n": n, "hits": k, "rate": round(k / n, 4) if n else 0.0,
            "ci_low": lo, "ci_high": hi}


def by_dimension(rows: list[ProbeResult], attr: str) -> dict:
    buckets: dict[str, list[ProbeResult]] = defaultdict(list)
    for r in rows:
        buckets[getattr(r, attr)].append(r)
    return {key: citation_rate(rs) for key, rs in sorted(buckets.items())}


def share_of_voice(rows: list[ProbeResult]) -> dict:
    counts = Counter()
    counts[config.BRAND_NAME] = sum(1 for r in rows if _is_hit(r))
    for r in rows:
        for c in (r.competitors_mentioned or []):
            counts[c] += 1
    total = sum(counts.values())
    return {"total_mentions": total,
            "share": {k: round(v / total, 4) if total else 0.0 for k, v in counts.most_common()},
            "counts": dict(counts.most_common())}


def cited_domains_ranking(rows: list[ProbeResult], top: int = 15) -> list[dict]:
    counts = Counter()
    for r in rows:
        for d in (r.cited_domains or []):
            counts[d] += 1
    brand = config.BRAND_DOMAIN.lower()
    return [{"domain": d, "count": c, "is_brand": brand in d}
            for d, c in counts.most_common(top)]


def prompt_effectiveness(rows: list[ProbeResult]) -> list[dict]:
    """Por prompt: cuántas veces elicitó a Gaia. Feedback para afinar la batería."""
    buckets: dict[str, list[ProbeResult]] = defaultdict(list)
    for r in rows:
        buckets[r.prompt_id].append(r)
    out = []
    for pid, rs in buckets.items():
        cr = citation_rate(rs)
        out.append({"prompt_id": pid, "prompt_class": rs[0].prompt_class,
                    "lang": rs[0].lang, **cr})
    return sorted(out, key=lambda x: x["rate"], reverse=True)


def daily_series(rows: list[ProbeResult]) -> list[dict]:
    """Serie temporal de citation rate por día (para la gráfica de tendencia)."""
    buckets: dict[str, list[ProbeResult]] = defaultdict(list)
    for r in rows:
        buckets[r.date].append(r)
    series = []
    for d in sorted(buckets):
        cr = citation_rate(buckets[d])
        series.append({"date": d, **cr})
    return series


def trend(rows: list[ProbeResult], window: int = 7) -> dict:
    """Tendencia: compara la media de las últimas `window` observaciones con la previa."""
    series = daily_series(rows)
    rates = [pt["rate"] for pt in series]
    if len(rates) < 2:
        return {"direction": "flat", "delta": 0.0, "z": 0.0, "points": len(rates)}
    recent = rates[-window:]
    base = rates[:-window] or rates[:1]
    mean_recent = sum(recent) / len(recent)
    mean_base = sum(base) / len(base)
    sd_base = (sum((x - mean_base) ** 2 for x in base) / len(base)) ** 0.5
    delta = round(mean_recent - mean_base, 4)
    z = _z_score(mean_recent, mean_base, sd_base) if sd_base else 0.0
    direction = "up" if delta > 0.02 else "down" if delta < -0.02 else "flat"
    return {"direction": direction, "delta": delta, "z": z,
            "mean_recent": round(mean_recent, 4), "mean_base": round(mean_base, 4),
            "points": len(rates)}


def anomalies(rows: list[ProbeResult], z_thresh: float = 2.0) -> list[dict]:
    """Días cuyo citation rate se desvía |z| > z_thresh de la media de la serie."""
    series = daily_series(rows)
    rates = [pt["rate"] for pt in series]
    if len(rates) < 3:
        return []
    mean = sum(rates) / len(rates)
    sd = (sum((x - mean) ** 2 for x in rates) / len(rates)) ** 0.5
    out = []
    for pt in series:
        z = _z_score(pt["rate"], mean, sd)
        if abs(z) >= z_thresh:
            out.append({"date": pt["date"], "rate": pt["rate"], "z": z,
                        "kind": "spike" if z > 0 else "drop"})
    return out


# ─── Vista completa para el dashboard / chatbot ─────────────────────────────
def full_report(since: str | None = None) -> dict:
    rows = _rows(since)
    return {
        "brand": config.BRAND_NAME,
        "domain": config.BRAND_DOMAIN,
        "campaign_days": config.CAMPAIGN_DAYS,
        "overall": citation_rate(rows),
        "by_engine": by_dimension(rows, "engine"),
        "by_class": by_dimension(rows, "prompt_class"),
        "share_of_voice": share_of_voice(rows),
        "cited_domains": cited_domains_ranking(rows),
        "prompt_effectiveness": prompt_effectiveness(rows),
        "daily_series": daily_series(rows),
        "trend": trend(rows),
        "anomalies": anomalies(rows),
    }


def snapshot_day(date: str) -> None:
    """Persiste un MetricSnapshot por día/scope para consultas rápidas de tendencia."""
    rows = [r for r in _rows() if r.date == date]
    if not rows:
        return
    snaps = [("overall", "all", citation_rate(rows))]
    for eng, cr in by_dimension(rows, "engine").items():
        snaps.append(("engine", eng, cr))
    for cls, cr in by_dimension(rows, "prompt_class").items():
        snaps.append(("class", cls, cr))

    with get_session() as s:
        for scope, key, cr in snaps:
            existing = s.exec(
                select(MetricSnapshot).where(
                    MetricSnapshot.date == date,
                    MetricSnapshot.scope == scope,
                    MetricSnapshot.key == key,
                )
            ).first()
            payload = dict(citation_rate=cr["rate"], ci_low=cr["ci_low"],
                           ci_high=cr["ci_high"], n=cr["n"])
            if existing:
                for f, v in payload.items():
                    setattr(existing, f, v)
                s.add(existing)
            else:
                s.add(MetricSnapshot(date=date, scope=scope, key=key, **payload))
        s.commit()
