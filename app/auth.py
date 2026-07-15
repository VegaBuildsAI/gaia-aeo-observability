"""
Autenticación mínima con cookie de sesión firmada (sin dependencias extra).

- Credenciales en config.AUTH_USERS (usuario → contraseña).
- La sesión es un token `base64(user|exp).hmac` firmado con SESSION_SECRET.
- Comparaciones con hmac.compare_digest para evitar timing attacks.
"""
import base64
import hashlib
import hmac
import time

from . import config


def verify_credentials(username: str, password: str) -> bool:
    stored = config.AUTH_USERS.get(username)
    if stored is None:
        # Comparación dummy para no filtrar por timing si el usuario no existe.
        hmac.compare_digest(password.encode(), password.encode())
        return False
    return hmac.compare_digest(password.encode(), stored.encode())


def _sign(msg: str) -> str:
    return hmac.new(config.SESSION_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def make_session(username: str, ttl: int | None = None) -> str:
    ttl = config.SESSION_TTL if ttl is None else ttl
    payload = f"{username}|{int(time.time()) + ttl}"
    b = base64.urlsafe_b64encode(payload.encode()).decode()
    return f"{b}.{_sign(b)}"


def verify_session(token: str | None) -> str | None:
    """Devuelve el username si la cookie es válida y no expiró; si no, None."""
    if not token or "." not in token:
        return None
    b, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(b)):
        return None
    try:
        username, exp = base64.urlsafe_b64decode(b.encode()).decode().split("|")
        if int(exp) < time.time():
            return None
        return username
    except Exception:
        return None
