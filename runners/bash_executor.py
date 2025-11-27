import json
import subprocess
from celery import Task
from engine_core.celery_app import celery_app
from engine_core.common_utils import record_task_start, record_task_end


@celery_app.task(bind=True, name="runners.bash_executor.executor_task", queue="bash")
def executor_task(self: Task, run_id: str, task_name: str, task_payload: dict):
    """
    Execute Bash commands/scripts.
    Supports inline commands, script files, and environment configuration.
    """
    record_task_start(run_id, task_name, self.request.id, "bash")
    
    try:
        params = task_payload.get("params", {})
        command = params.get("command")
        
        if not command:
            raise ValueError("Bash task requires a 'command' parameter")
        
        # Get optional parameters
        timeout = params.get("timeout", 3600)  # Default 1 hour
        cwd = params.get("cwd")  # Working directory
        env_vars = params.get("env", {})  # Environment variables
        
        # Execute bash command
        process = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env={**subprocess.os.environ.copy(), **env_vars} if env_vars else None
        )
        
        result = {
            "stdout": process.stdout,
            "stderr": process.stderr,
            "exit_code": process.returncode,
            "command": command
        }
        
        status = "SUCCESS" if process.returncode == 0 else "FAILURE"
        record_task_end(run_id, task_name, status, result)
        return result
        
    except subprocess.TimeoutExpired as e:
        error_result = {
            "error": "Command execution timed out",
            "timeout": timeout,
            "command": command
        }
        record_task_end(run_id, task_name, "FAILURE", error_result)
        raise
    except Exception as e:
        error_result = {
            "error": str(e),
            "error_type": type(e).__name__,
            "task_name": task_name
        }
        record_task_end(run_id, task_name, "FAILURE", error_result)
        raise

