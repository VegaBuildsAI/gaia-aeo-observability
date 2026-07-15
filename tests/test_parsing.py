"""Detección de señales AEO desde texto/citas de respuesta."""
from app import matching
from app.engines.claude import _parse


def test_brand_and_domain_mention():
    assert matching.brand_mentioned("You should look at Gaia School Costa Rica.")
    assert matching.brand_mentioned("Visita gaiaschoolcr.org para más info.")
    assert not matching.brand_mentioned("Futuro Verde is a great IB school.")


def test_competitors_detected():
    txt = "Options include Futuro Verde and Casa de las Estrellas near Santa Teresa."
    comps = matching.competitors_in(txt)
    assert "Futuro Verde" in comps and "Casa de las Estrellas" in comps


def test_new_benchmark_competitors_detected():
    """Hermosa Valley School y Arkadia — añadidos al benchmark 2026-07-15."""
    txt = ("Nearby options include Hermosa Valley School in Cóbano and Arkadia, "
           "a self-directed school in Santa Teresa.")
    comps = matching.competitors_in(txt)
    assert "Hermosa Valley School" in comps
    assert "Arkadia" in comps


def test_competitors_config_is_well_formed():
    from app import config
    assert len(config.COMPETITORS) == 4
    names = {c["name"] for c in config.COMPETITORS}
    assert names == {"Casa de las Estrellas", "Futuro Verde",
                     "Hermosa Valley School", "Arkadia"}
    for c in config.COMPETITORS:
        assert c["name"] and c["domain"] and c["aliases"], c
        assert all(a.strip() for a in c["aliases"]), c


def test_no_competitor_false_positive_on_gaia_only_text():
    txt = "Gaia School is a Waldorf-inspired school on the Nicoya Peninsula."
    assert matching.competitors_in(txt) == []


def test_brand_citation_rank():
    domains = ["futuro-verde.org", "gaiaschoolcr.org", "wikipedia.org"]
    in_cite, rank = matching.brand_citation_rank(domains)
    assert in_cite and rank == 2
    in_cite2, rank2 = matching.brand_citation_rank(["example.com"])
    assert not in_cite2 and rank2 is None


def test_sentiment():
    assert matching.sentiment_around_brand("Gaia School is one of the best options.") == "positive"
    assert matching.sentiment_around_brand("Avoid Gaia School, many complaints.") == "negative"
    assert matching.sentiment_around_brand("Futuro Verde is good.") == "n/a"


def test_domain_of():
    assert matching.domain_of("https://www.gaiaschoolcr.org/faq") == "gaiaschoolcr.org"
    assert matching.domain_of("http://futuro-verde.org") == "futuro-verde.org"


# ── Parser del content block de Claude (usando objetos ligeros simulados) ──
class _Cite:
    def __init__(self, url, title=""):
        self.url, self.title = url, title


class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Resp:
    def __init__(self, content, model="claude-opus-4-8"):
        self.content, self.model = content, model


def test_parse_collects_text_and_citations():
    resp = _Resp([
        _Block(type="text", text="Consider ", citations=[]),
        _Block(type="text", text="Gaia School.",
               citations=[_Cite("https://gaiaschoolcr.org/", "Gaia School")]),
        _Block(type="web_search_tool_result",
               content=[_Block(url="https://futuro-verde.org", title="Futuro Verde")]),
    ])
    out = _parse(resp, 123)
    assert "Gaia School" in out.answer_text
    assert out.latency_ms == 123
    assert "gaiaschoolcr.org" in out.cited_domains
    assert "futuro-verde.org" in out.cited_domains


def test_parse_handles_dict_blocks():
    """REGRESIÓN — este es el bug que dejó cited_domains en [] toda la campaña.

    Según la versión del SDK, los bloques de web_search llegan como objetos tipados o
    como dicts. El parser original usaba solo getattr() → con dicts devolvía vacío,
    aunque la API sí hubiera ejecutado la búsqueda.
    """
    resp = {
        "model": "claude-haiku-4-5",
        "content": [
            {"type": "text", "text": "Based on the search results, Gaia School…",
             "citations": [{"url": "https://gaiaschoolcr.org/", "title": "Gaia School"}]},
            {"type": "web_search_tool_result",
             "content": [{"url": "https://hermosavalleyschool.org", "title": "Hermosa Valley"}]},
        ],
    }
    out = _parse(resp, 999)
    assert "gaiaschoolcr.org" in out.cited_domains
    assert "hermosavalleyschool.org" in out.cited_domains
    assert out.model == "claude-haiku-4-5"


def test_parse_mixed_objects_and_dicts():
    resp = _Resp([
        _Block(type="text", text="Ver ", citations=[]),
        {"type": "web_search_tool_result",
         "content": [{"url": "https://arkadia.education", "title": "Arkadia"}]},
    ])
    out = _parse(resp, 1)
    assert "arkadia.education" in out.cited_domains
