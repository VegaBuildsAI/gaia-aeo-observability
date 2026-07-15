"""Inicialización de la base de datos (SQLite local / Postgres en Railway)."""
import os
import time
from contextlib import contextmanager

from sqlalchemy.exc import OperationalError
from sqlmodel import SQLModel, Session, create_engine

from . import config
from . import models  # noqa: F401 — registra las tablas en SQLModel.metadata

_url = config.database_url()

# check_same_thread solo aplica a SQLite (el scheduler corre en otro hilo).
_connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}

# Asegura la carpeta ./data para el archivo SQLite en local.
if _url.startswith("sqlite:///"):
    path = _url.replace("sqlite:///", "", 1)
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)

engine = create_engine(_url, echo=False, connect_args=_connect_args, pool_pre_ping=True)


def init_db(retries: int = 15, delay: float = 3.0) -> None:
    """Crea las tablas, reintentando mientras la DB se calienta.

    En Railway el Postgres privado (postgres.railway.internal) puede tardar unos
    segundos en ser alcanzable al arrancar el contenedor — sin reintento, el
    startup crashea y el healthcheck falla.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            SQLModel.metadata.create_all(engine)
            return
        except OperationalError as e:
            last_err = e
            print(f"[db] DB no lista (intento {attempt}/{retries}): {type(e).__name__} — reintento en {delay}s")
            time.sleep(delay)
    raise last_err


@contextmanager
def get_session() -> Session:
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
