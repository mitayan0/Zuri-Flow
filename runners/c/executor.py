import json
from datetime import datetime
from celery import Task
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from engine_core.celery_app import celery_app, settings
from engine_core.models import TaskInstance

import subprocess

engine = create_engine(settings.DATABASE_URL)

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

@celery_app.task(bind=True, name="runners.c.executor_task", queue="c")
def executor_task(self: Task, run_id: str, task_name: str, task_payload: dict):
    record_task_start(run_id, task_name, self.request.id, "c")
    try:
        binary_path = task_payload.get("params", {}).get("binary_path")
        if not binary_path:
            raise ValueError("C task requires a 'binary_path' parameter")

        # Run the C binary
        process = subprocess.run(binary_path, shell=True, capture_output=True, text=True)
        result = {"stdout": process.stdout, "stderr": process.stderr, "exit_code": process.returncode}
        status = "SUCCESS" if process.returncode == 0 else "FAILURE"
        record_task_end(run_id, task_name, status, json.dumps(result))
        return result
    except Exception as e:
        record_task_end(run_id, task_name, "FAILURE", json.dumps({"error": str(e)}))
        raise
