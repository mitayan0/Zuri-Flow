from datetime import datetime
from celery import Task, signature, group
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from engine_core.celery_app import celery_app
from engine_core.models import WorkflowDefinition, WorkflowRun, TaskInstance
from config import settings

engine = create_engine(settings.DATABASE_URL)

@celery_app.task(bind=True)
def workflow_orchestrator(self: Task, run_id: str, definition_id: str, completed_tasks: list):
    with Session(engine) as session:
        definition_record = session.query(WorkflowDefinition).filter_by(id=definition_id).first()
        if not definition_record:
            return {"status": "FAILURE", "reason": "Workflow not found"}

        workflow_def = definition_record.definition
        all_tasks = workflow_def["tasks"]
        next_tasks_to_run = []
        is_complete = True

        for task_name, task_details in all_tasks.items():
            if task_name not in completed_tasks and all(dep in completed_tasks for dep in task_details["dependencies"]):
                next_tasks_to_run.append(task_name)
                is_complete = False

        db_run = session.query(WorkflowRun).filter_by(id=run_id).first()
        if not next_tasks_to_run and is_complete:
            if db_run:
                db_run.status = "SUCCESS"
                db_run.completed_at = datetime.utcnow()
                session.commit()
            return {"status": "SUCCESS"}

        elif not next_tasks_to_run and not is_complete:
            if db_run:
                db_run.status = "FAILURE"
                db_run.completed_at = datetime.utcnow()
                session.commit()
            return {"status": "FAILURE"}

        task_signatures = []
        for task_name in next_tasks_to_run:
            task_details = all_tasks[task_name]
            executor_name = task_details.get("executor", "python")
            executor_task_name = f"runners.{executor_name}.executor_task"
            payload = {
                "run_id": run_id,
                "task_name": task_name,
                "task_payload": task_details
            }
            sig = signature(executor_task_name, kwargs=payload)
            task_signatures.append(sig)

        next_group = group(task_signatures)
        chord = next_group(workflow_orchestrator.s(run_id, definition_id, completed_tasks))
        chord.delay()
