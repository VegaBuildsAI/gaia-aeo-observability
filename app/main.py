"""
FastAPI: sirve el dashboard (static/index.html), la API JSON, el SSE del chat y
arranca el scheduler. Un solo servicio — espíritu del jps_server.py.
"""
import os
from contextlib import asynccontextmanager

from fastapi import Body, Cookie, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import analytics, auth, chat, config, probe, scheduler
from .db import get_session, init_db
from .engines import get_adapter
from .models import ProbeResult
from .prompts import PROMPTS
from sqlmodel import select

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(os.path.dirname(HERE), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if config.SCHEDULER_ENABLED:
        scheduler.start()
    else:
        probe._log("Scheduler automático DESACTIVADO — sondeos solo por disparo manual.", "warn")
    yield


app = FastAPI(title="Gaia AEO Observability Engine", version="1.0.0", lifespan=lifespan)


def _require_admin(token: str | None):
    if token != config.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="ADMIN_TOKEN inválido.")


# ─── Autenticación ──────────────────────────────────────────────────────────
def current_user(aeo_session: str | None = Cookie(default=None)) -> str | None:
    return auth.verify_session(aeo_session)


def require_user(user: str | None = Depends(current_user)) -> str:
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado.")
    return user


@app.get("/login")
def login_page():
    return FileResponse(os.path.join(STATIC, "login.html"))


@app.post("/api/login")
def login(payload: dict = Body(...)):
    u = (payload.get("username") or "").strip()
    p = payload.get("password") or ""
    if not auth.verify_credentials(u, p):
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")
    resp = JSONResponse({"ok": True, "user": u})
    resp.set_cookie("aeo_session", auth.make_session(u), httponly=True,
                    samesite="lax", secure=config.COOKIE_SECURE, max_age=config.SESSION_TTL)
    return resp


@app.post("/api/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("aeo_session")
    return resp


# ─── Dashboard ──────────────────────────────────────────────────────────────
@app.get("/")
def dashboard(user: str | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    return FileResponse(os.path.join(STATIC, "index.html"))


# ─── API JSON ─────────────────────────────────────────────────────────────
@app.get("/api/status")
def status():
    engines = {name: get_adapter(name).available() for name in
               ("claude", "openai", "perplexity", "gemini")}
    return {"ok": True, "brand": config.BRAND_NAME, "domain": config.BRAND_DOMAIN,
            "engines_available": engines, "active_engines": config.active_engines(),
            "probe_status": probe.STATE["status"], "last_run": probe.STATE["last_run"],
            "scheduler_enabled": config.SCHEDULER_ENABLED,
            "next_run": scheduler.next_run(), "prompts": len(PROMPTS),
            "campaign_days": config.CAMPAIGN_DAYS, "cron": config.PROBE_CRON}


@app.get("/api/state")
def state(user: str = Depends(require_user)):
    """Estado en vivo del sondeo (para la consola del dashboard)."""
    return {"status": probe.STATE["status"], "progress": probe.STATE["progress"],
            "last_run": probe.STATE["last_run"], "log": probe.STATE["log"][-120:]}


@app.get("/api/metrics")
def metrics(since: str | None = Query(default=None), user: str = Depends(require_user)):
    return analytics.full_report(since=since)


@app.get("/api/probes")
def probes(since: str | None = Query(default=None), limit: int = Query(default=200, le=1000),
           user: str = Depends(require_user)):
    with get_session() as s:
        q = select(ProbeResult).order_by(ProbeResult.ts.desc())
        if since:
            q = q.where(ProbeResult.date >= since)
        rows = list(s.exec(q.limit(limit)).all())
    return [r.model_dump() for r in rows]


@app.post("/api/probe/run")
def probe_run(x_admin_token: str | None = Header(default=None),
              user: str = Depends(require_user)):
    _require_admin(x_admin_token)
    started = scheduler.run_now_async()
    if not started:
        return JSONResponse({"started": False, "reason": "Ya hay un sondeo en curso."}, status_code=409)
    return {"started": True}


# ─── Chatbot (SSE) ────────────────────────────────────────────────────────
@app.post("/api/chat")
def chat_endpoint(payload: dict = Body(...), user: str = Depends(require_user)):
    messages = payload.get("messages") or []
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=400, detail="messages requerido.")
    return StreamingResponse(chat.stream_reply(messages), media_type="text/event-stream")


# Sirve assets estáticos (logo, etc.) bajo /static.
if os.path.isdir(STATIC):
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
