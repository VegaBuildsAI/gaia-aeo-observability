"""Integridad de la batería de prompts."""
from app.prompts import PROMPTS, by_id


def test_battery_size():
    """18 originales (baseline 2026-07-09) + 2 comparativos añadidos 2026-07-15."""
    assert len(PROMPTS) == 20


def test_prompt_ids_are_unique():
    ids = [p["id"] for p in PROMPTS]
    assert len(ids) == len(set(ids))


def test_new_comparative_prompts_present():
    for pid in ("cmp_gaia_vs_hermosavalley_en", "cmp_gaia_vs_arkadia_es"):
        p = by_id(pid)
        assert p is not None, pid
        assert p["cls"] == "comparative"


def test_original_18_still_intact():
    """La serie comparable contra el baseline depende de que estos ids no cambien."""
    baseline = {
        "nb_waldorf_nicoya_en", "nb_bilingual_nature_st_en", "nb_intl_malpais_en",
        "nb_waldorf_bilingue_cr_es", "br_gaia_programs_en", "br_gaia_es",
        "lt_move_family_st_en", "lt_homeschool_alt_es", "lt_expat_options_en",
        "lt_puntarenas_alt_es", "cmp_gaia_vs_futuroverde_en", "cmp_gaia_vs_estrellas_es",
        "cmp_best_waldorf_ranked_en", "nb_montessori_waldorf_es", "nb_bilingual_primary_en",
        "nb_nature_curriculum_en", "nb_admissions_process_es", "br_gaia_location_en",
    }
    assert baseline <= {p["id"] for p in PROMPTS}
    assert len(baseline) == 18


def test_every_prompt_well_formed():
    for p in PROMPTS:
        assert p["text"].strip()
        assert p["lang"] in ("en", "es")
        assert p["cls"] in ("brand", "nonbrand", "comparative", "longtail")
