import uuid
from datetime import timedelta
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, validator
from typing import Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import create_engine


from engine_core.models import WorkflowDefinition as ORMWorkflowDefinition, WorkflowRun, TaskInstance, StandaloneTask
from engine_core.celery_app import celery_app, settings
from engine_core.orchestrator_tasks import workflow_orchestrator

router = APIRouter()
engine = create_engine(settings.DATABASE_URL)

# ----------------------
# Pydantic Models
# ----------------------

class TaskDefinition(BaseModel):
    executor: str
    dependencies: list[str] = Field(default_factory=list)
    task_name: str
    params: Dict[str, Any] = Field(default_factory=dict)

    @validator('executor')
    def validate_executor(cls, v):
        if v not in settings.QUEUES:
            raise ValueError(f"Invalid executor '{v}'. Must be one of {settings.QUEUES}")
        return v

class WorkflowDefinition(BaseModel):
    name: str
    start_tasks: list[str] = Field(default_factory=list)
    tasks: Dict[str, TaskDefinition]

# ----------------------
# Workflow Endpoints
# ----------------------

@router.post("/definitions", status_code=201)
def create_workflow_definition(workflow: WorkflowDefinition):
    with Session(engine) as session:
        db_workflow = ORMWorkflowDefinition(
            name=workflow.name,
            definition=workflow.dict()
        )
        session.add(db_workflow)
        session.commit()
        session.refresh(db_workflow)
        return {"message": "Workflow definition created successfully", "id": db_workflow.id}

@router.post("/definitions/{definition_id}/run")
def run_workflow(definition_id: str, background_tasks: BackgroundTasks):
    with Session(engine) as session:
        definition_record = session.query(ORMWorkflowDefinition).filter_by(id=definition_id).first()
        if not definition_record:
            raise HTTPException(status_code=404, detail="Workflow definition not found")

        db_run = WorkflowRun(definition_id=definition_id, status='RUNNING')
        session.add(db_run)
        session.commit()
        session.refresh(db_run)
        run_id = str(db_run.id)

    # Dispatch orchestrator
    background_tasks.add_task(
        workflow_orchestrator.apply_async,
        kwargs={'run_id': run_id, 'definition_id': definition_id, 'completed_tasks': []}
    )

    return {"message": "Workflow execution started", "run_id": run_id}

# ----------------------
# Standalone Task Endpoints
# ----------------------

@router.post("/tasks", status_code=201)
def create_standalone_task(task_name: str, executor: str, default_params: dict = None):
    if executor not in settings.QUEUES:
        raise HTTPException(status_code=400, detail=f"Executor must be one of {settings.QUEUES}")
    with Session(engine) as session:
        task = StandaloneTask(task_name=task_name, executor=executor, default_params=default_params or {})
        session.add(task)
        session.commit()
        session.refresh(task)
        return {"message": "Standalone task created", "task_id": task.id}

@router.post("/tasks/{task_id}/run")
def run_standalone_task(task_id: str):
    with Session(engine) as session:
        task = session.query(StandaloneTask).filter_by(id=task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        run_id = str(uuid.uuid4())
        payload = {
            "run_id": run_id,
            "task_name": task.task_name,
            "task_payload": {"params": task.default_params}
        }
        celery_app.send_task(f"runners.{task.executor}.executor_task", kwargs=payload)
        return {"message": "Task dispatched", "run_id": run_id}

@router.post("/tasks/{task_id}/schedule")
def schedule_standalone_task(task_id: str, interval_seconds: int):
    """
    Schedule a standalone task to run periodically using Celery beat schedule.
    """
    with Session(engine) as session:
        task = session.query(StandaloneTask).filter_by(id=task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        run_id = str(uuid.uuid4())
        entry_name = f"standalone_task:{run_id}"

        # Schedule dynamically
        celery_app.add_periodic_task(
            interval_seconds,
            celery_app.signature(f"runners.{task.executor}.executor_task", kwargs={
                "run_id": run_id,
                "task_name": task.task_name,
                "task_payload": {"params": task.default_params}
            }),
            name=entry_name
        )

        return {"message": "Task scheduled", "entry_name": entry_name}

# ----------------------
# Workflow Run Status & Details
# ----------------------

@router.get("/runs/{run_id}")
def get_workflow_run_details(run_id: str):
    with Session(engine) as session:
        run_record = session.query(WorkflowRun).filter_by(id=run_id).first()
        if not run_record:
            raise HTTPException(status_code=404, detail="Workflow run not found")

        task_records = session.query(TaskInstance).filter_by(run_id=run_id).order_by(TaskInstance.started_at).all()
        return {"run_details": run_record, "task_history": task_records}

@router.get("/runs/{run_id}/status")
def get_workflow_run_status(run_id: str):
    with Session(engine) as session:
        record = session.query(WorkflowRun).filter_by(id=run_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Workflow run not found")
        return {"status": record.status}
