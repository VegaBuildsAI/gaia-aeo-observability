"""Métricas estadísticas sobre datos sintéticos (sin tocar la DB)."""
from app import analytics
from app.models import ProbeResult


def _row(date, engine, cls, hit, comps=None, domains=None):
    return ProbeResult(
        date=date, prompt_id=f"p_{date}_{engine}_{cls}", engine=engine,
        prompt_class=cls, gaia_mentioned=hit, gaia_in_citations=hit,
        competitors_mentioned=comps or [], cited_domains=domains or [],
    )


def test_wilson_ci_bounds():
    lo, hi = analytics.wilson_ci(5, 10)
    assert 0.0 <= lo <= 0.5 <= hi <= 1.0
    assert analytics.wilson_ci(0, 0) == (0.0, 0.0)


def test_citation_rate():
    rows = [_row("2026-07-01", "claude", "brand", True),
            _row("2026-07-01", "claude", "nonbrand", False),
            _row("2026-07-01", "claude", "nonbrand", False)]
    cr = analytics.citation_rate(rows)
    assert cr["n"] == 3 and cr["hits"] == 1
    assert abs(cr["rate"] - 0.3333) < 0.01


def test_by_dimension_and_class():
    rows = [_row("2026-07-01", "claude", "brand", True),
            _row("2026-07-01", "claude", "brand", True),
            _row("2026-07-01", "claude", "nonbrand", False)]
    by_cls = analytics.by_dimension(rows, "prompt_class")
    assert by_cls["brand"]["rate"] == 1.0
    assert by_cls["nonbrand"]["rate"] == 0.0


def test_share_of_voice():
    rows = [_row("2026-07-01", "claude", "brand", True, comps=["Futuro Verde"]),
            _row("2026-07-01", "claude", "nonbrand", False, comps=["Futuro Verde", "Casa de las Estrellas"])]
    sov = analytics.share_of_voice(rows)
    assert sov["counts"]["Futuro Verde"] == 2
    assert sov["counts"]["Casa de las Estrellas"] == 1
    assert abs(sum(sov["share"].values()) - 1.0) < 1e-6


def test_share_of_voice_includes_competitors_with_zero_mentions():
    """El benchmark debe mostrarse completo: un 0 es información, no una ausencia.

    Antes, un competidor sin menciones desaparecía del gráfico y no se podía
    distinguir "no lo mencionan" de "no lo estamos midiendo".
    """
    from app import config
    rows = [_row("2026-07-01", "claude", "brand", True, comps=["Futuro Verde"])]
    sov = analytics.share_of_voice(rows)
    for c in config.COMPETITORS:
        assert c["name"] in sov["counts"], f"{c['name']} falta en el benchmark"
    assert sov["counts"]["Arkadia"] == 0
    assert sov["counts"]["Hermosa Valley School"] == 0
    assert sov["counts"]["Futuro Verde"] == 1


def test_share_of_voice_with_no_rows_still_lists_benchmark():
    from app import config
    sov = analytics.share_of_voice([])
    assert sov["total_mentions"] == 0
    assert len(sov["counts"]) == 1 + len(config.COMPETITORS)   # marca + competidores
    assert all(v == 0 for v in sov["counts"].values())


def test_cited_domains_ranking_flags_brand():
    rows = [_row("2026-07-01", "claude", "brand", True, domains=["gaiaschoolcr.org", "wikipedia.org"]),
            _row("2026-07-02", "claude", "brand", True, domains=["gaiaschoolcr.org"])]
    ranking = analytics.cited_domains_ranking(rows)
    top = ranking[0]
    assert top["domain"] == "gaiaschoolcr.org" and top["count"] == 2 and top["is_brand"]


def test_trend_direction_up():
    rows = []
    # base days low, recent days high
    for d in ["2026-07-01", "2026-07-02", "2026-07-03"]:
        rows += [_row(d, "claude", "nonbrand", False) for _ in range(4)]
    for d in ["2026-07-10", "2026-07-11", "2026-07-12"]:
        rows += [_row(d, "claude", "nonbrand", True) for _ in range(4)]
    t = analytics.trend(rows, window=3)
    assert t["direction"] == "up" and t["delta"] > 0


def test_prompt_effectiveness_sorted():
    rows = [_row("2026-07-01", "claude", "brand", True),
            _row("2026-07-01", "claude", "nonbrand", False)]
    rows[0].prompt_id = "good"; rows[1].prompt_id = "bad"
    eff = analytics.prompt_effectiveness(rows)
    assert eff[0]["prompt_id"] == "good" and eff[0]["rate"] == 1.0
