"""
Extracción de señales AEO desde la respuesta de un motor.

Detecta: mención de Gaia (nombre y dominio), presencia en las fuentes citadas,
ranking de la cita, competidores mencionados y un sentimiento simple del
fragmento donde aparece Gaia.
"""
import re
from urllib.parse import urlparse

from . import config


def domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _mentions(text: str, aliases: list[str]) -> bool:
    low = text.lower()
    return any(a.lower() in low for a in aliases)


def brand_mentioned(text: str) -> bool:
    return _mentions(text, config.BRAND_ALIASES)


def competitors_in(text: str) -> list[str]:
    low = text.lower()
    found = []
    for c in config.COMPETITORS:
        if any(a.lower() in low for a in c["aliases"]):
            found.append(c["name"])
    return found


def brand_citation_rank(cited_domains: list[str]) -> tuple[bool, int | None]:
    """¿Aparece el dominio de la marca entre las fuentes? ¿En qué posición (1-indexed)?"""
    target = config.BRAND_DOMAIN.lower()
    for i, d in enumerate(cited_domains):
        if target in d:
            return True, i + 1
    return False, None


# Léxico mínimo para sentimiento del fragmento sobre la marca.
_POS = ("excellent", "best", "top", "recommend", "great", "leading", "renowned",
        "excelente", "mejor", "recomend", "destacad", "líder", "reconocid", "prestigios")
_NEG = ("not recommended", "avoid", "closed", "poor", "controvers", "complaint",
        "no recomend", "cerrad", "problema", "queja", "mala")


def sentiment_around_brand(text: str) -> str:
    """Sentimiento simple basado en la(s) oración(es) que mencionan la marca."""
    if not brand_mentioned(text):
        return "n/a"
    low = text.lower()
    # Toma ±160 caracteres alrededor de la primera mención de la marca.
    idx = min((low.find(a.lower()) for a in config.BRAND_ALIASES
               if a.lower() in low), default=-1)
    window = low[max(0, idx - 160): idx + 160] if idx >= 0 else low
    neg = any(n in window for n in _NEG)
    pos = any(p in window for p in _POS)
    if neg and not pos:
        return "negative"
    if pos and not neg:
        return "positive"
    return "neutral"
