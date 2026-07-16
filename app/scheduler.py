"""
Scheduler in-process (APScheduler). Corre el sondeo 1×/día según PROBE_CRON.
También expone un disparo manual (usado por POST /api/probe/run).
"""
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import config, probe

_scheduler: BackgroundScheduler | None = None
_run_lock = threading.Lock()


def _job(trigger: str = "scheduled", run_id: str | None = None,
         lock_already_held: bool = False) -> None:
    # Evita solapamiento si un ciclo previo aún corre.
    if not lock_already_held and not _run_lock.acquire(blocking=False):
        probe._log("Sondeo previo aún en curso — se omite este tick.", "warn")
        return
    try:
        probe.run(run_id=run_id, trigger=trigger)
    finally:
        _run_lock.release()


def start() -> None:
    global _scheduler
    if _scheduler:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    trigger = CronTrigger.from_crontab(config.PROBE_CRON, timezone="UTC")
    _scheduler.add_job(_job, trigger, args=["scheduled"], id="daily_probe", replace_existing=True,
                       misfire_grace_time=3600)
    _scheduler.start()
    probe._log(f"Scheduler iniciado · cron='{config.PROBE_CRON}' (UTC)", "head")


def run_now_async() -> str | None:
    """Dispara un sondeo y devuelve su run_id, o None si ya hay uno corriendo."""
    if not _run_lock.acquire(blocking=False):
        return None
    run_id = probe.new_run_id()
    threading.Thread(
        target=_job,
        args=("manual", run_id, True),
        daemon=True,
    ).start()
    return run_id


def next_run() -> str | None:
    if _scheduler:
        job = _scheduler.get_job("daily_probe")
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
    return None
