"""Credenciales y firma de sesión."""
import time

from app import auth, config


def test_valid_credentials():
    assert auth.verify_credentials("ValeMurillo", "aeogaia2026")
    assert auth.verify_credentials("AXIO", "aeogaia2026")


def test_invalid_credentials():
    assert not auth.verify_credentials("AXIO", "wrong")
    assert not auth.verify_credentials("nobody", "aeogaia2026")
    assert not auth.verify_credentials("", "")


def test_session_roundtrip():
    tok = auth.make_session("AXIO")
    assert auth.verify_session(tok) == "AXIO"


def test_session_rejects_tampering():
    tok = auth.make_session("AXIO")
    body, sig = tok.rsplit(".", 1)
    assert auth.verify_session(body + "." + ("0" * len(sig))) is None   # firma mala
    assert auth.verify_session("garbage") is None
    assert auth.verify_session(None) is None


def test_session_expires():
    tok = auth.make_session("AXIO", ttl=-1)   # ya expirado
    assert auth.verify_session(tok) is None


def test_users_configured():
    assert set(config.AUTH_USERS.keys()) == {"ValeMurillo", "AXIO"}
