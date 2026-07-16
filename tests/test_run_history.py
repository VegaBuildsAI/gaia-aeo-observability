"""Every token-backed probe execution is preserved, including same-day reruns."""
from contextlib import contextmanager

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import analytics, probe
from app.engines.base import Citation, EngineResponse
from app.models import ProbeResult, ProbeRun, ProbeRunResult


class FakeAdapter:
    def available(self) -> bool:
        return True

    def run(self, prompt_text: str) -> EngineResponse:
        return EngineResponse(
            answer_text=f"Gaia School: {prompt_text}",
            citations=[Citation(
                url="https://www.gaiaschoolcr.org/",
                domain="gaiaschoolcr.org",
                title="Gaia School",
            )],
            model="fake-model",
            latency_ms=17,
        )


def _memory_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    @contextmanager
    def get_test_session():
        with Session(engine) as session:
            yield session

    return engine, get_test_session


def test_same_day_reruns_are_append_only(monkeypatch):
    engine, get_test_session = _memory_db()
    prompt = {
        "id": "gaia_test",
        "text": "Best Waldorf school in Nicoya?",
        "cls": "nonbrand",
        "lang": "en",
    }
    monkeypatch.setattr(probe, "get_session", get_test_session)
    monkeypatch.setattr(analytics, "get_session", get_test_session)
    monkeypatch.setattr(probe, "get_adapter", lambda _: FakeAdapter())
    monkeypatch.setattr(probe, "PROMPTS", [prompt])

    first = probe.run(
        engines=["claude"], date="2026-07-15", run_id="run-1", trigger="manual"
    )
    second = probe.run(
        engines=["claude"], date="2026-07-15", run_id="run-2", trigger="manual"
    )

    with Session(engine) as session:
        runs = list(session.exec(select(ProbeRun).order_by(ProbeRun.id)).all())
        events = list(
            session.exec(select(ProbeRunResult).order_by(ProbeRunResult.run_id)).all()
        )
        daily = list(session.exec(select(ProbeResult)).all())

    assert first["run_id"] == "run-1"
    assert second["run_id"] == "run-2"
    assert [run.id for run in runs] == ["run-1", "run-2"]
    assert all(run.status == "done" for run in runs)
    assert all(run.executions_written == 1 for run in runs)
    assert [event.run_id for event in events] == ["run-1", "run-2"]
    assert len(daily) == 1
    assert daily[0].date == "2026-07-15"
    assert daily[0].prompt_id == "gaia_test"


def test_error_response_is_also_preserved(monkeypatch):
    engine, get_test_session = _memory_db()

    class ErrorAdapter(FakeAdapter):
        def run(self, prompt_text: str) -> EngineResponse:
            return EngineResponse(model="fake-model", latency_ms=5, error="provider error")

    monkeypatch.setattr(probe, "get_session", get_test_session)
    monkeypatch.setattr(analytics, "get_session", get_test_session)
    monkeypatch.setattr(probe, "get_adapter", lambda _: ErrorAdapter())
    monkeypatch.setattr(probe, "PROMPTS", [{
        "id": "error_test",
        "text": "test",
        "cls": "brand",
        "lang": "en",
    }])

    summary = probe.run(
        engines=["claude"], date="2026-07-15", run_id="run-error", trigger="scheduled"
    )

    with Session(engine) as session:
        event = session.exec(select(ProbeRunResult)).one()
        run = session.get(ProbeRun, "run-error")

    assert event.error == "provider error"
    assert summary["errors"] == 1
    assert run is not None and run.status == "done" and run.errors == 1
