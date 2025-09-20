from celery import Celery
from config import settings

celery_app = Celery(
    "zuri_flow",
    broker=settings.REDIS_BROKER_URL,
    backend=settings.REDIS_BACKEND_URL,
    include=[
        "engine_core.orchestrator_tasks",
        "runners.python.executor",
        "runners.bash.executor",
        "runners.c.executor",
    ]
)

# --- Celery configuration ---
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={},  # We can dynamically add tasks via API
    timezone="UTC"
)
