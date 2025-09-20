import json
from datetime import datetime
from celery import Task
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from engine_core.celery_app import celery_app, settings
from engine_core.models import TaskInstance


engine = create_engine(settings.DATABASE_URL)

TASK_REGISTRY = {}  # Optional: pre-registered Python functions

def register_task(func):
    TASK_REGISTRY[func.__name__] = func
    return func

def record_task_start(run_id, task_name, celery_task_id, language):
    with Session(engine) as session:
        db_task = TaskInstance(
            run_id=run_id,
            task_name=task_name,
            language=language,
            status='RUNNING',
            celery_task_id=celery_task_id
        )
        session.add(db_task)
        session.commit()

def record_task_end(run_id, task_name, status, result):
    with Session(engine) as session:
        db_task = session.query(TaskInstance).filter_by(run_id=run_id, task_name=task_name).first()
        if db_task:
            db_task.status = status
            db_task.result = json.loads(result)
            db_task.completed_at = datetime.utcnow()
            session.commit()

@celery_app.task(bind=True, name="runners.python.executor_task", queue="python")
def executor_task(self: Task, run_id: str, task_name: str, task_payload: dict):
    record_task_start(run_id, task_name, self.request.id, "python")
    try:
        task_logic = TASK_REGISTRY.get(task_name)
        if task_logic:
            result = task_logic(task_payload.get("params", {}))
        else:
            # Dynamic execution: just echo params
            result = {"message": f"Executed Python task '{task_name}' dynamically", "params": task_payload.get("params")}
        record_task_end(run_id, task_name, "SUCCESS", json.dumps(result))
        return result
    except Exception as e:
        record_task_end(run_id, task_name, "FAILURE", json.dumps({"error": str(e)}))
        raise
