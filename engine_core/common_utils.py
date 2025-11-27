import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create engine once for reuse
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)


def record_task_start(run_id: str, task_name: str, celery_task_id: str, language: str):
    """
    Record the start of a task execution in the database.
    
    Args:
        run_id: Unique identifier for the workflow run
        task_name: Name of the task being executed
        celery_task_id: Celery task ID for tracking
        language: Programming language/executor type
    """
    from engine_core.models import TaskInstance
    
    try:
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
            logger.info(f"Task started: {task_name} (run_id={run_id}, language={language})")
    except Exception as e:
        logger.error(f"Failed to record task start: {e}")
        raise


def record_task_end(run_id: str, task_name: str, status: str, result: dict):
    """
    Record the completion of a task execution in the database.
    
    Args:
        run_id: Unique identifier for the workflow run
        task_name: Name of the task being executed
        status: Task status (SUCCESS or FAILURE)
        result: Task execution result (dict will be converted to JSON)
    """
    from engine_core.models import TaskInstance
    
    try:
        with Session(engine) as session:
            db_task = session.query(TaskInstance).filter_by(
                run_id=run_id, 
                task_name=task_name
            ).first()
            
            if db_task:
                db_task.status = status
                # Store result as dict, not JSON string
                db_task.result = result if isinstance(result, dict) else json.loads(result)
                db_task.completed_at = datetime.utcnow()
                session.commit()
                logger.info(f"Task completed: {task_name} (status={status})")
            else:
                logger.warning(f"Task instance not found for update: {task_name} (run_id={run_id})")
    except Exception as e:
        logger.error(f"Failed to record task end: {e}")
        raise


def safe_execute(executor_func):
    """
    Decorator for safe task execution with comprehensive error handling.
    
    Usage:
        @safe_execute
        def my_executor_task(self, run_id, task_name, task_payload):
            # your code here
    """
    def wrapper(self, run_id: str, task_name: str, task_payload: dict, language: str):
        record_task_start(run_id, task_name, self.request.id, language)
        
        try:
            # Execute the actual task logic
            result = executor_func(self, run_id, task_name, task_payload)
            record_task_end(run_id, task_name, "SUCCESS", result)
            return result
        except Exception as e:
            error_result = {
                "error": str(e),
                "error_type": type(e).__name__,
                "task_name": task_name
            }
            record_task_end(run_id, task_name, "FAILURE", error_result)
            logger.error(f"Task execution failed: {task_name} - {str(e)}")
            raise
    
    return wrapper


def validate_executor_params(params: dict, required_keys: list, executor_name: str):
    """
    Validate that required parameters are present in the task payload.
    
    Args:
        params: Task parameters dictionary
        required_keys: List of required parameter keys
        executor_name: Name of the executor (for error messages)
    
    Raises:
        ValueError: If required parameters are missing
    """
    missing_keys = [key for key in required_keys if key not in params]
    if missing_keys:
        raise ValueError(
            f"{executor_name} executor requires the following parameters: {missing_keys}"
        )


def get_db_engine():
    """Get the database engine instance."""
    return engine
