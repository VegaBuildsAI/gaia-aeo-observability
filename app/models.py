"""
Esquema de datos del motor. Una fila por (fecha, prompt, engine) — espeja la
lógica de deduplicación de jps_accumulate.py: acumula sin perder histórico.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProbeResult(SQLModel, table=True):
    """Resultado de un prompt corrido contra un motor de IA en una fecha dada."""
    __tablename__ = "probe_result"
    __table_args__ = (
        UniqueConstraint("date", "prompt_id", "engine", name="uq_date_prompt_engine"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Clave de deduplicación
    date: str = Field(index=True)               # "YYYY-MM-DD" (día de la corrida)
    prompt_id: str = Field(index=True)
    engine: str = Field(index=True)             # claude | openai | perplexity | gemini

    ts: datetime = Field(default_factory=_utcnow)
    model: str = ""
    prompt_text: str = ""
    prompt_class: str = ""                      # brand | nonbrand | comparative | longtail
    lang: str = "es"

    # Señales AEO extraídas de la respuesta
    answer_text: str = ""
    gaia_mentioned: bool = Field(default=False, index=True)
    gaia_in_citations: bool = Field(default=False)
    citation_rank: Optional[int] = None         # posición del dominio Gaia entre las fuentes
    sentiment: str = "neutral"                   # positive | neutral | negative | n/a

    latency_ms: int = 0
    cited_domains: list = Field(default_factory=list, sa_column=Column(JSON))
    competitors_mentioned: list = Field(default_factory=list, sa_column=Column(JSON))
    error: Optional[str] = None


class ProbeRun(SQLModel, table=True):
    """One complete probe run, triggered manually or by the scheduler."""
    __tablename__ = "probe_run"

    id: str = Field(primary_key=True)
    date: str = Field(index=True)
    started_at: datetime = Field(default_factory=_utcnow, index=True)
    completed_at: Optional[datetime] = None
    trigger: str = Field(default="manual", index=True)
    status: str = Field(default="running", index=True)
    engines: list = Field(default_factory=list, sa_column=Column(JSON))
    prompts_total: int = 0
    executions_written: int = 0
    errors: int = 0
    summary: dict = Field(default_factory=dict, sa_column=Column(JSON))


class ProbeRunResult(SQLModel, table=True):
    """Append-only prompt result belonging to one specific run."""
    __tablename__ = "probe_run_result"
    __table_args__ = (
        UniqueConstraint("run_id", "prompt_id", "engine", name="uq_run_prompt_engine"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(foreign_key="probe_run.id", index=True)
    date: str = Field(index=True)
    prompt_id: str = Field(index=True)
    engine: str = Field(index=True)
    ts: datetime = Field(default_factory=_utcnow, index=True)
    model: str = ""
    prompt_text: str = ""
    prompt_class: str = ""
    lang: str = "es"
    answer_text: str = ""
    gaia_mentioned: bool = Field(default=False, index=True)
    gaia_in_citations: bool = False
    citation_rank: Optional[int] = None
    sentiment: str = "neutral"
    latency_ms: int = 0
    cited_domains: list = Field(default_factory=list, sa_column=Column(JSON))
    competitors_mentioned: list = Field(default_factory=list, sa_column=Column(JSON))
    error: Optional[str] = None


class MetricSnapshot(SQLModel, table=True):
    """Foto diaria de una métrica agregada (para gráficas rápidas de tendencia)."""
    __tablename__ = "metric_snapshot"
    __table_args__ = (
        UniqueConstraint("date", "scope", "key", name="uq_date_scope_key"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    date: str = Field(index=True)
    scope: str = Field(index=True)              # overall | engine | class
    key: str = "all"                            # p.ej. "claude", "nonbrand"
    citation_rate: float = 0.0
    ci_low: float = 0.0
    ci_high: float = 0.0
    n: int = 0
    extra: dict = Field(default_factory=dict, sa_column=Column(JSON))
