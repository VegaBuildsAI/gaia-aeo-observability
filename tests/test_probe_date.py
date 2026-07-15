"""La fecha del sondeo siempre es la del día (UTC) — nunca hardcodeada."""
from datetime import datetime, timezone

import app.probe as probe_mod


def test_today_is_utc_now(monkeypatch):
    """Fija el contrato: _today() deriva de datetime.now(UTC), no de un literal."""
    class FakeDT:
        @staticmethod
        def now(tz=None):
            assert tz is timezone.utc, "la fecha debe calcularse en UTC"
            return datetime(2030, 1, 2, 3, 4, tzinfo=timezone.utc)

    monkeypatch.setattr(probe_mod, "datetime", FakeDT)
    assert probe_mod._today() == "2030-01-02"


def test_today_matches_real_utc_date():
    assert probe_mod._today() == datetime.now(timezone.utc).strftime("%Y-%m-%d")


def test_today_format_is_iso_date():
    d = probe_mod._today()
    datetime.strptime(d, "%Y-%m-%d")     # no lanza → formato correcto
    assert len(d) == 10
