import uuid
from datetime import timedelta
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import create_engine


from engine_core.models import WorkflowDefinition as ORMWorkflowDefinition, WorkflowRun, TaskInstance, StandaloneTask
from engine_core.celery_app import celery_app, settings
from engine_core.orchestrator import workflow_orchestrator

router = APIRouter(prefix="/api/v1")
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
        valid_executors = [q for q in settings.QUEUES if q != "orchestrator"]
        if v not in valid_executors:
            raise ValueError(f"Invalid executor '{v}'. Must be one of {valid_executors}")
        return v

class WorkflowDefinition(BaseModel):
    name: str
    start_tasks: list[str] = Field(default_factory=list)
    tasks: Dict[str, TaskDefinition]

class WorkflowRunResponse(BaseModel):
    message: str
    run_id: str

class TaskCreateRequest(BaseModel):
    task_name: str
    executor: str
    default_params: Optional[Dict[str, Any]] = None

# ----------------------
# Workflow Endpoints
# ----------------------

@router.post("/workflows/definitions", status_code=201)
def create_workflow_definition(workflow: WorkflowDefinition):
    """Create a new workflow definition."""
    try:
        with Session(engine) as session:
            db_workflow = ORMWorkflowDefinition(
                name=workflow.name,
                definition=workflow.dict()
            )
            session.add(db_workflow)
            session.commit()
            session.refresh(db_workflow)
            return {"message": "Workflow definition created successfully", "id": db_workflow.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create workflow: {str(e)}")

@router.post("/workflows/definitions/{definition_id}/run", response_model=WorkflowRunResponse)
def run_workflow(definition_id: str, background_tasks: BackgroundTasks):
    """Execute a workflow definition."""
    try:
        with Session(engine) as session:
            definition_record = session.query(ORMWorkflowDefinition).filter_by(id=definition_id).first()
            if not definition_record:
                raise HTTPException(status_code=404, detail="Workflow definition not found")

            db_run = WorkflowRun(definition_id=definition_id, status='RUNNING')
            session.add(db_run)
            session.commit()
            session.refresh(db_run)
            run_id = str(db_run.id)

        # Dispatch orchestrator with empty completed_tasks list
        workflow_orchestrator.apply_async(
            kwargs={'run_id': run_id, 'definition_id': definition_id, 'completed_tasks': []},
            queue='orchestrator'
        )

        return WorkflowRunResponse(message="Workflow execution started", run_id=run_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")

# ----------------------
# Standalone Task Endpoints
# ----------------------

@router.post("/tasks", status_code=201)
def create_standalone_task(request: TaskCreateRequest):
    """Create a standalone task definition."""
    valid_executors = [q for q in settings.QUEUES if q != "orchestrator"]
    if request.executor not in valid_executors:
        raise HTTPException(
            status_code=400, 
            detail=f"Executor must be one of {valid_executors}"
        )
    
    try:
        with Session(engine) as session:
            task = StandaloneTask(
                task_name=request.task_name,
                executor=request.executor,
                default_params=request.default_params or {}
            )
            session.add(task)
            session.commit()
            session.refresh(task)
            return {"message": "Standalone task created", "task_id": task.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")

@router.post("/tasks/{task_id}/run")
def run_standalone_task(task_id: str):
    """Execute a standalone task."""
    try:
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
            
            task_name = f"runners.{task.executor}_executor.executor_task"
            celery_app.send_task(task_name, kwargs=payload, queue=task.executor)
            
            return {"message": "Task dispatched", "run_id": run_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run task: {str(e)}")

@router.post("/tasks/{task_id}/schedule")
def schedule_standalone_task(task_id: str, interval_seconds: int):
    """
    Schedule a standalone task to run periodically using Celery beat schedule.
    """
    try:
        with Session(engine) as session:
            task = session.query(StandaloneTask).filter_by(id=task_id).first()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")

            run_id = str(uuid.uuid4())
            entry_name = f"standalone_task:{run_id}"

            # Schedule dynamically
            celery_app.add_periodic_task(
                interval_seconds,
                celery_app.signature(f"runners.{task.executor}_executor.executor_task", kwargs={
                    "run_id": run_id,
                    "task_name": task.task_name,
                    "task_payload": {"params": task.default_params}
                }),
                name=entry_name
            )

            return {"message": "Task scheduled", "entry_name": entry_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to schedule task: {str(e)}")

# ----------------------
# Workflow Run Status & Details
# ----------------------

@router.get("/workflows/runs/{run_id}")
def get_workflow_run_details(run_id: str):
    """Get detailed information about a workflow run including task history."""
    try:
        with Session(engine) as session:
            run_record = session.query(WorkflowRun).filter_by(id=run_id).first()
            if not run_record:
                raise HTTPException(status_code=404, detail="Workflow run not found")

            task_records = session.query(TaskInstance).filter_by(run_id=run_id).order_by(TaskInstance.started_at).all()
            
            return {
                "run_id": run_record.id,
                "definition_id": run_record.definition_id,
                "status": run_record.status,
                "started_at": run_record.started_at.isoformat() if run_record.started_at else None,
                "completed_at": run_record.completed_at.isoformat() if run_record.completed_at else None,
                "tasks": [
                    {
                        "task_name": t.task_name,
                        "status": t.status,
                        "language": t.language,
                        "started_at": t.started_at.isoformat() if t.started_at else None,
                        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                        "result": t.result
                    }
                    for t in task_records
                ]
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch run details: {str(e)}")

@router.get("/workflows/runs/{run_id}/status")
def get_workflow_run_status(run_id: str):
    """Get the current status of a workflow run."""
    try:
        with Session(engine) as session:
            record = session.query(WorkflowRun).filter_by(id=run_id).first()
            if not record:
                raise HTTPException(status_code=404, detail="Workflow run not found")
            return {"run_id": run_id, "status": record.status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch run status: {str(e)}")

