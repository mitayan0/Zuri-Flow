import json
import subprocess
import sys
import tempfile
import os
from celery import Task
from engine_core.celery_app import celery_app
from engine_core.common_utils import record_task_start, record_task_end


TASK_REGISTRY = {}  # Optional: pre-registered Python functions

def register_task(func):
    """Decorator to register Python functions for execution"""
    TASK_REGISTRY[func.__name__] = func
    return func


@celery_app.task(bind=True, name="runners.python_executor.executor_task", queue="python")
def executor_task(self: Task, run_id: str, task_name: str, task_payload: dict):
    """
    Execute Python code. Supports three modes:
    1. Registered function execution (if task_name is in TASK_REGISTRY)
    2. Inline Python code execution (if 'code' param is provided)
    3. Python script file execution (if 'script_path' param is provided)
    """
    record_task_start(run_id, task_name, self.request.id, "python")
    
    try:
        params = task_payload.get("params", {})
        
        # Mode 1: Registered function
        if task_name in TASK_REGISTRY:
            task_logic = TASK_REGISTRY[task_name]
            result = task_logic(params)
            record_task_end(run_id, task_name, "SUCCESS", result)
            return result
        
        # Mode 2: Inline code execution
        if "code" in params:
            code = params["code"]
            env_vars = params.get("env", {})
            
            # Create isolated namespace for execution
            exec_namespace = {"params": params, **env_vars}
            
            try:
                exec(code, exec_namespace)
                # Extract result if 'result' variable is set in code
                result = exec_namespace.get("result", {"message": "Code executed successfully", "namespace": str(exec_namespace.keys())})
            except Exception as e:
                raise RuntimeError(f"Python code execution error: {str(e)}")
            
            record_task_end(run_id, task_name, "SUCCESS", result)
            return result
        
        # Mode 3: Script file execution
        if "script_path" in params:
            script_path = params["script_path"]
            script_args = params.get("args", [])
            
            if not os.path.exists(script_path):
                raise FileNotFoundError(f"Script not found: {script_path}")
            
            # Execute Python script
            cmd = [sys.executable, script_path] + script_args
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=params.get("timeout", 3600)
            )
            
            result = {
                "stdout": process.stdout,
                "stderr": process.stderr,
                "exit_code": process.returncode
            }
            
            status = "SUCCESS" if process.returncode == 0 else "FAILURE"
            record_task_end(run_id, task_name, status, result)
            return result
        
        # Default: Echo params
        result = {
            "message": f"Executed Python task '{task_name}' dynamically",
            "params": params
        }
        record_task_end(run_id, task_name, "SUCCESS", result)
        return result
        
    except Exception as e:
        error_result = {
            "error": str(e),
            "error_type": type(e).__name__,
            "task_name": task_name
        }
        record_task_end(run_id, task_name, "FAILURE", error_result)
        raise

