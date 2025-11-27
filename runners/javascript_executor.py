import json
import subprocess
import tempfile
import os
from celery import Task
from engine_core.celery_app import celery_app
from engine_core.common_utils import record_task_start, record_task_end
from config import settings


@celery_app.task(bind=True, name="runners.javascript_executor.executor_task", queue="javascript")
def executor_task(self: Task, run_id: str, task_name: str, task_payload: dict):
    """
    Execute JavaScript/Node.js code. Supports three modes:
    1. Inline JavaScript code execution (if 'code' is provided)
    2. JavaScript file execution (if 'script_path' is provided)
    3. npm module execution (if 'module' is provided)
    """
    record_task_start(run_id, task_name, self.request.id, "javascript")
    
    try:
        params = task_payload.get("params", {})
        
        # Mode 1: Inline JavaScript code execution
        if "code" in params:
            code = params["code"]
            env_vars = params.get("env", {})
            
            with tempfile.TemporaryDirectory() as tmpdir:
                # Write JavaScript code to temp file
                script_file = os.path.join(tmpdir, "script.js")
                
                with open(script_file, 'w') as f:
                    f.write(code)
                
                # Execute with Node.js
                process = subprocess.run(
                    [settings.NODE_PATH, script_file],
                    capture_output=True,
                    text=True,
                    timeout=params.get("timeout", 3600),
                    env={**os.environ.copy(), **env_vars} if env_vars else None
                )
                
                result = {
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "exit_code": process.returncode
                }
                
                status = "SUCCESS" if process.returncode == 0 else "FAILURE"
                record_task_end(run_id, task_name, status, result)
                return result
        
        # Mode 2: JavaScript file execution
        if "script_path" in params:
            script_path = params["script_path"]
            script_args = params.get("args", [])
            env_vars = params.get("env", {})
            
            if not os.path.exists(script_path):
                raise FileNotFoundError(f"Script not found: {script_path}")
            
            cmd = [settings.NODE_PATH, script_path] + script_args
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=params.get("timeout", 3600),
                env={**os.environ.copy(), **env_vars} if env_vars else None
            )
            
            result = {
                "stdout": process.stdout,
                "stderr": process.stderr,
                "exit_code": process.returncode,
                "script_path": script_path
            }
            
            status = "SUCCESS" if process.returncode == 0 else "FAILURE"
            record_task_end(run_id, task_name, status, result)
            return result
        
        # Mode 3: npm module execution
        if "module" in params:
            module_name = params["module"]
            module_args = params.get("args", [])
            
            # Execute npm module using npx
            cmd = ["npx", "-y", module_name] + module_args
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=params.get("timeout", 3600)
            )
            
            result = {
                "stdout": process.stdout,
                "stderr": process.stderr,
                "exit_code": process.returncode,
                "module": module_name
            }
            
            status = "SUCCESS" if process.returncode == 0 else "FAILURE"
            record_task_end(run_id, task_name, status, result)
            return result
        
        raise ValueError("JavaScript task requires 'code', 'script_path', or 'module' parameter")
        
    except subprocess.TimeoutExpired:
        error_result = {
            "error": "JavaScript execution timed out",
            "timeout": params.get("timeout", 3600)
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
