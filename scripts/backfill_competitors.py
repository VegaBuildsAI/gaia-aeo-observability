#!/usr/bin/env python3
"""
Backfill de `competitors_mentioned` sobre sondeos ya guardados.

Por qué existe: `competitors_mentioned` se calcula al momento del sondeo y se persiste. Cuando se
amplía el benchmark (config.COMPETITORS), las filas viejas no reflejan a los competidores nuevos.
Como `answer_text` sí está guardado, se puede recalcular SIN gastar API.

Es idempotente: solo escribe las filas que cambian; una segunda corrida reporta 0 modificadas.

Uso:
    # Local (SQLite de ./data)
    python scripts/backfill_competitors.py
    python scripts/backfill_competitors.py --dry-run

    # Producción (usa el DATABASE_URL que inyecta Railway)
    railway run python scripts/backfill_competitors.py
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import select  # noqa: E402

from app import config, matching  # noqa: E402
from app.db import get_session, init_db  # noqa: E402
from app.models import ProbeResult  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Recalcula competitors_mentioned desde answer_text.")
    ap.add_argument("--dry-run", action="store_true", help="No escribe; solo reporta.")
    args = ap.parse_args()

    init_db()
    names = [c["name"] for c in config.COMPETITORS]
    print(f"Benchmark actual ({len(names)}): {', '.join(names)}")
    print(f"DB: {config.database_url().split('@')[-1]}")   # no imprime credenciales
    print("-" * 70)

    changed = scanned = 0
    with get_session() as s:
        rows = list(s.exec(select(ProbeResult)).all())
        for r in rows:
            scanned += 1
            if not r.answer_text:
                continue
            fresh = matching.competitors_in(r.answer_text)
            before = list(r.competitors_mentioned or [])
            if sorted(fresh) != sorted(before):
                changed += 1
                added = sorted(set(fresh) - set(before))
                removed = sorted(set(before) - set(fresh))
                delta = []
                if added:
                    delta.append("+" + ", +".join(added))
                if removed:
                    delta.append("-" + ", -".join(removed))
                print(f"  {r.date} {r.engine}/{r.prompt_id}: {' | '.join(delta)}")
                if not args.dry_run:
                    r.competitors_mentioned = fresh
                    s.add(r)
        if not args.dry_run and changed:
            s.commit()

    print("-" * 70)
    verb = "cambiarían" if args.dry_run else "actualizadas"
    print(f"Filas escaneadas: {scanned} · {verb}: {changed}")
    if args.dry_run:
        print("(dry-run — no se escribió nada)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
