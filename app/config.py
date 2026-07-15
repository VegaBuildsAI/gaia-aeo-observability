"""
Configuración central del motor de observabilidad AEO.
Todo se lee de variables de entorno (.env en local, secretos en Railway).
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Identidad del cliente ──────────────────────────────────────────────────
BRAND_NAME     = os.getenv("BRAND_NAME", "Gaia School")
BRAND_DOMAIN   = os.getenv("BRAND_DOMAIN", "gaiaschoolcr.org")
# Aliases con los que un modelo puede referirse a la marca (para el matcher)
BRAND_ALIASES  = [a.strip() for a in os.getenv(
    "BRAND_ALIASES",
    "Gaia School,Gaia School Costa Rica,Escuela Gaia,gaiaschoolcr.org"
).split(",") if a.strip()]

# Benchmark competitivo — escuelas de la misma zona (Cóbano / Santa Teresa / Nicoya)
# que compiten por el mismo perfil de familia.
# Nota: matching.competitors_in() detecta SOLO por `aliases` sobre el texto de la respuesta;
# `domain` se conserva para referencia y para el ranking de fuentes.
COMPETITORS = [
    {"name": "Casa de las Estrellas", "domain": "casadelasestrellas.ed.cr",
     "aliases": ["Casa de las Estrellas", "Casa Estrellas"]},
    {"name": "Futuro Verde",          "domain": "futuro-verde.org",
     "aliases": ["Futuro Verde", "Futuro-Verde"]},
    # Privada bilingüe en Playa Hermosa, Cóbano; reconocida por el MEP desde 2005.
    {"name": "Hermosa Valley School", "domain": "hermosavalleyschool.org",
     "aliases": ["Hermosa Valley School", "Hermosa Valley"]},
    # Autodirigida / Montessori-inspired (3–12 años) en Santa Teresa; parte de The ARK.
    {"name": "Arkadia",               "domain": "arkadia.education",
     "aliases": ["Arkadia School", "Arkadia"]},
]

# ─── Motor de sondeo ────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Probe = tarea de detección (¿aparece Gaia en respuesta/citas?), no de razonamiento
# → Haiku 4.5 es 5× más barato que Opus y parsea las citaciones web igual de bien.
CLAUDE_MODEL      = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")
# Chatbot también en Haiku 4.5 (máxima eficiencia; responde sobre datos ya calculados).
CHAT_MODEL        = os.getenv("CHAT_MODEL", "claude-haiku-4-5")
# 2 búsquedas bastan para revelar las mismas escuelas; recortar aquí baja tanto la
# tarifa por búsqueda como los tokens de resultados inyectados (el costo dominante).
WEB_SEARCH_MAX_USES = int(os.getenv("WEB_SEARCH_MAX_USES", "2"))
# La respuesta del probe solo se usa para detectar menciones — no necesita ser larga.
PROBE_MAX_TOKENS  = int(os.getenv("PROBE_MAX_TOKENS", "512"))

# Motores activos (los que tienen key). Claude siempre; los demás se activan
# automáticamente si su API key está presente en el entorno.
def active_engines() -> list[str]:
    engines = ["claude"]
    if os.getenv("OPENAI_API_KEY"):     engines.append("openai")
    if os.getenv("PERPLEXITY_API_KEY"): engines.append("perplexity")
    if os.getenv("GEMINI_API_KEY"):     engines.append("gemini")
    return engines

# ─── Cadencia ───────────────────────────────────────────────────────────────
# Scheduler automático DESACTIVADO por defecto: los sondeos solo corren cuando
# Michael los dispara manualmente (control total del gasto del token Claude).
# Poner SCHEDULER_ENABLED=true para reactivar el tick diario según PROBE_CRON.
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "false").lower() in ("1", "true", "yes", "on")
# Formato cron de APScheduler (solo aplica si SCHEDULER_ENABLED=true).
PROBE_CRON = os.getenv("PROBE_CRON", "0 9 * * *")
# Ventana total de la campaña (para el dashboard). 2 meses ≈ 60 días.
CAMPAIGN_DAYS = int(os.getenv("CAMPAIGN_DAYS", "60"))

# ─── Base de datos ──────────────────────────────────────────────────────────
def database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./data/aeo.db")
    # Railway entrega "postgres://"; SQLAlchemy requiere "postgresql://".
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

# ─── Seguridad ──────────────────────────────────────────────────────────────
# Token para disparar probes manuales y endpoints de escritura.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-me-in-prod")

# ─── Login (acceso al dashboard) ────────────────────────────────────────────
# Usuarios permitidos. Formato env: "user1:pass1,user2:pass2".
def _parse_users() -> dict[str, str]:
    raw = os.getenv("AUTH_USERS", "ValeMurillo:aeogaia2026,AXIO:aeogaia2026")
    users: dict[str, str] = {}
    for pair in raw.split(","):
        if ":" in pair:
            u, p = pair.split(":", 1)
            users[u.strip()] = p.strip()
    return users

AUTH_USERS     = _parse_users()
# Secreto para firmar la cookie de sesión (deriva del ADMIN_TOKEN si no se setea).
SESSION_SECRET = os.getenv("SESSION_SECRET", ADMIN_TOKEN + "::aeo-session")
SESSION_TTL    = int(os.getenv("SESSION_TTL", str(60 * 60 * 12)))  # 12 h
# secure=True exige HTTPS (Railway). En local (http) poner COOKIE_SECURE=false.
COOKIE_SECURE  = os.getenv("COOKIE_SECURE", "true").lower() in ("1", "true", "yes", "on")

# ─── Servidor ───────────────────────────────────────────────────────────────
PORT = int(os.getenv("PORT", "8000"))
