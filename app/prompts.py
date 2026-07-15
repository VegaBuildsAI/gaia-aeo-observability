"""
Batería de prompts AEO — "agresiva en cobertura".

Deriva de las 5 queries base de AEO_Roadmap.md y las expande por ejes:
marca/no-marca, ES/EN, long-tail y comparativos. Corrección regional aplicada:
Santa Teresa / Mal País / Cóbano son Puntarenas (NO Guanacaste).

Cada prompt está redactado como preguntaría un padre real a una IA — la meta es
MEDIR si Gaia aparece, no manipular al modelo.

HISTORIAL DE LA BATERÍA (importante para leer las métricas):
- 2026-07-09: batería original de 18 prompts → es el baseline.
- 2026-07-15: +2 comparativos (Hermosa Valley, Arkadia) al ampliar el benchmark → 20 prompts.
  El citation rate GLOBAL de una fecha ≥ 2026-07-15 no es 1:1 comparable con el baseline.
  Para una serie comparable, filtrar por los 18 prompt_id originales (cada fila los guarda).
"""
from typing import TypedDict


class Prompt(TypedDict):
    id: str
    text: str
    lang: str          # es | en
    cls: str           # brand | nonbrand | comparative | longtail
    expects_gaia: bool  # True si esperaríamos que Gaia idealmente aparezca


PROMPTS: list[Prompt] = [
    # ── No-marca · núcleo (Q1–Q4) ──────────────────────────────────────────
    {"id": "nb_waldorf_nicoya_en", "lang": "en", "cls": "nonbrand", "expects_gaia": True,
     "text": "What are the best Waldorf schools on the Nicoya Peninsula in Costa Rica?"},
    {"id": "nb_bilingual_nature_st_en", "lang": "en", "cls": "nonbrand", "expects_gaia": True,
     "text": "Recommend a bilingual, nature-based school near Santa Teresa, Costa Rica for a young family."},
    {"id": "nb_intl_malpais_en", "lang": "en", "cls": "nonbrand", "expects_gaia": True,
     "text": "What international or alternative schools exist in Mal País / Santa Teresa, Costa Rica?"},
    {"id": "nb_waldorf_bilingue_cr_es", "lang": "es", "cls": "nonbrand", "expects_gaia": True,
     "text": "¿Cuáles son las mejores escuelas Waldorf bilingües en Costa Rica?"},

    # ── Marca (Q5) ─────────────────────────────────────────────────────────
    {"id": "br_gaia_programs_en", "lang": "en", "cls": "brand", "expects_gaia": True,
     "text": "Tell me about Gaia School Costa Rica — its programs and admissions."},
    {"id": "br_gaia_es", "lang": "es", "cls": "brand", "expects_gaia": True,
     "text": "¿Qué es Gaia School Costa Rica y qué ofrece? ¿Cómo son las admisiones?"},

    # ── Long-tail (cómo pregunta un padre de verdad) ───────────────────────
    {"id": "lt_move_family_st_en", "lang": "en", "cls": "longtail", "expects_gaia": True,
     "text": "We're moving to Santa Teresa, Costa Rica with two kids and want a Waldorf-inspired bilingual school. Where should we enroll them?"},
    {"id": "lt_homeschool_alt_es", "lang": "es", "cls": "longtail", "expects_gaia": True,
     "text": "Busco una escuela con pedagogía Waldorf y enfoque en la naturaleza cerca de Cóbano o Santa Teresa para mi hijo de 6 años. ¿Qué opciones hay?"},
    {"id": "lt_expat_options_en", "lang": "en", "cls": "longtail", "expects_gaia": True,
     "text": "As an expat family in the Nicoya Peninsula, what are our K-12 school options that teach in both English and Spanish?"},
    {"id": "lt_puntarenas_alt_es", "lang": "es", "cls": "longtail", "expects_gaia": True,
     "text": "¿Qué escuelas alternativas o bilingües hay en la zona de Puntarenas costera (Santa Teresa, Mal País)?"},

    # ── Comparativos (Gaia vs competidores conocidos) ──────────────────────
    {"id": "cmp_gaia_vs_futuroverde_en", "lang": "en", "cls": "comparative", "expects_gaia": True,
     "text": "How does Gaia School compare to Futuro Verde for a bilingual education near Santa Teresa, Costa Rica?"},
    {"id": "cmp_gaia_vs_estrellas_es", "lang": "es", "cls": "comparative", "expects_gaia": True,
     "text": "Comparación entre Gaia School y Casa de las Estrellas para educación Waldorf/bilingüe en la Península de Nicoya."},
    {"id": "cmp_best_waldorf_ranked_en", "lang": "en", "cls": "comparative", "expects_gaia": True,
     "text": "Rank the top Waldorf/alternative schools in the Nicoya Peninsula and Puntarenas coast by reputation."},
    # Añadidos 2026-07-15 al ampliar el benchmark (batería 18 → 20). Ver nota en el header.
    {"id": "cmp_gaia_vs_hermosavalley_en", "lang": "en", "cls": "comparative", "expects_gaia": True,
     "text": "How does Gaia School compare to Hermosa Valley School for a bilingual education in the Cóbano / Santa Teresa area of Costa Rica?"},
    {"id": "cmp_gaia_vs_arkadia_es", "lang": "es", "cls": "comparative", "expects_gaia": True,
     "text": "¿Qué diferencia hay entre Gaia School y Arkadia para educación alternativa en Santa Teresa, Costa Rica?"},

    # ── No-marca · variantes de intención ──────────────────────────────────
    {"id": "nb_montessori_waldorf_es", "lang": "es", "cls": "nonbrand", "expects_gaia": True,
     "text": "¿Dónde puedo encontrar educación Montessori o Waldorf en la costa del Pacífico de Costa Rica?"},
    {"id": "nb_bilingual_primary_en", "lang": "en", "cls": "nonbrand", "expects_gaia": True,
     "text": "Best bilingual primary schools in the Santa Teresa / Cóbano area of Costa Rica?"},
    {"id": "nb_nature_curriculum_en", "lang": "en", "cls": "nonbrand", "expects_gaia": True,
     "text": "Which schools in coastal Puntarenas, Costa Rica use a nature-based or outdoor curriculum?"},
    {"id": "nb_admissions_process_es", "lang": "es", "cls": "nonbrand", "expects_gaia": True,
     "text": "¿Cómo es el proceso de admisión en las escuelas Waldorf bilingües de la Península de Nicoya?"},

    # ── Marca · verificación de hechos ─────────────────────────────────────
    {"id": "br_gaia_location_en", "lang": "en", "cls": "brand", "expects_gaia": True,
     "text": "Where is Gaia School located and what pedagogy does it follow?"},
]


def by_id(pid: str) -> Prompt | None:
    return next((p for p in PROMPTS if p["id"] == pid), None)
