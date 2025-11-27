import logging
from datetime import datetime
from celery import Task, signature, group, chord
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from engine_core.celery_app import celery_app
from engine_core.models import WorkflowDefinition, WorkflowRun, TaskInstance
from config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(settings.DATABASE_URL)


def orchestrator_callback(results, run_id: str, definition_id: str, completed_tasks: list):
    """
    Callback function that gets called after a group of tasks completes.
    This continues the workflow orchestration.
    
    Args:
        results: Results from completed tasks
        run_id: Workflow run ID
        definition_id: Workflow definition ID
        completed_tasks: List of task names that have been completed
    """
    logger.info(f"Orchestrator callback invoked for run_id={run_id}, completed_tasks={completed_tasks}")
    
    # Extract task names from results and add to completed list
    new_completed_tasks = []
    for result in results:
        if isinstance(result, dict) and 'task_name' in result:
            new_completed_tasks.append(result['task_name'])
    
    # Continue orchestration with updated completed tasks list
    workflow_orchestrator.apply_async(
        kwargs={
            'run_id': run_id,
            'definition_id': definition_id,
            'completed_tasks': completed_tasks + new_completed_tasks
        }
    )


@celery_app.task(bind=True, name="engine_core.orchestrator.workflow_orchestrator", queue="orchestrator")
def workflow_orchestrator(self: Task, run_id: str, definition_id: str, completed_tasks: list = None):
    """
    Orchestrates workflow execution by managing task dependencies and execution order.
    
    Args:
        self: Celery task instance
        run_id: Unique identifier for this workflow run
        definition_id: ID of the workflow definition to execute
        completed_tasks: List of task names that have been completed so far
    """
    if completed_tasks is None:
        completed_tasks = []
    
    logger.info(f"Orchestrator starting: run_id={run_id}, completed_tasks={completed_tasks}")
    
    with Session(engine) as session:
        # Fetch workflow definition
        definition_record = session.query(WorkflowDefinition).filter_by(id=definition_id).first()
        if not definition_record:
            logger.error(f"Workflow definition not found: {definition_id}")
            return {"status": "FAILURE", "reason": "Workflow definition not found"}
        
        workflow_def = definition_record.definition
        all_tasks = workflow_def.get("tasks", {})
        
        if not all_tasks:
            logger.warning(f"No tasks defined in workflow {definition_id}")
            return {"status": "SUCCESS", "reason": "No tasks to execute"}
        
        # Determine which tasks are ready to run
        next_tasks_to_run = []
        all_tasks_completed = True
        
        for task_name, task_details in all_tasks.items():
            if task_name in completed_tasks:
                # Task already completed, skip
                continue
            
            all_tasks_completed = False
            
            # Check if all dependencies are satisfied
            dependencies = task_details.get("dependencies", [])
            if all(dep in completed_tasks for dep in dependencies):
                next_tasks_to_run.append(task_name)
        
        # Update workflow run status
        db_run = session.query(WorkflowRun).filter_by(id=run_id).first()
        
        # Check completion conditions
        if all_tasks_completed:
            # All tasks have been completed
            if db_run:
                db_run.status = "SUCCESS"
                db_run.completed_at = datetime.utcnow()
                session.commit()
            logger.info(f"Workflow completed successfully: run_id={run_id}")
            return {"status": "SUCCESS", "completed_tasks": completed_tasks}
        
        if not next_tasks_to_run:
            # No tasks ready to run but not all completed - deadlock or dependency issue
            if db_run:
                db_run.status = "FAILURE"
                db_run.completed_at = datetime.utcnow()
                session.commit()
            logger.error(f"Workflow deadlock detected: run_id={run_id}, completed={completed_tasks}")
            return {
                "status": "FAILURE",
                "reason": "No tasks ready to run - possible dependency deadlock",
                "completed_tasks": completed_tasks
            }
        
        # Build task signatures for next batch
        task_signatures = []
        logger.info(f"Preparing to execute tasks: {next_tasks_to_run}")
        
        for task_name in next_tasks_to_run:
            task_details = all_tasks[task_name]
            executor_name = task_details.get("executor", "python")
            
            # Validate executor
            if executor_name not in settings.QUEUES:
                logger.error(f"Invalid executor '{executor_name}' for task '{task_name}'")
                continue
            
            executor_task_name = f"runners.{executor_name}_executor.executor_task"
            
            payload = {
                "run_id": run_id,
                "task_name": task_name,
                "task_payload": task_details
            }
            
            sig = signature(executor_task_name, kwargs=payload)
            task_signatures.append(sig)
        
        if not task_signatures:
            logger.error(f"No valid tasks to execute for run_id={run_id}")
            return {"status": "FAILURE", "reason": "No valid tasks to execute"}
        
        # Execute tasks in parallel using group and continue orchestration after completion
        # CRITICAL FIX: Add completed task names to the list after execution
        updated_completed_tasks = completed_tasks + next_tasks_to_run
        
        # Create a group of tasks and chain it with the orchestrator callback
        task_group = group(task_signatures)
        
        # Use a callback signature to continue orchestration
        callback_sig = workflow_orchestrator.si(
            run_id=run_id,
            definition_id=definition_id,
            completed_tasks=updated_completed_tasks
        )
        
        # Execute the group and chain with callback
        chord(task_group)(callback_sig)
        
        logger.info(f"Dispatched {len(task_signatures)} tasks for execution")
        return {"status": "RUNNING", "dispatched_tasks": next_tasks_to_run}

