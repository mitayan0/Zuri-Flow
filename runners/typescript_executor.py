import json
import subprocess
import tempfile
import os
from celery import Task
from engine_core.celery_app import celery_app
from engine_core.common_utils import record_task_start, record_task_end
from config import settings


@celery_app.task(bind=True, name="runners.typescript_executor.executor_task", queue="typescript")
def executor_task(self: Task, run_id: str, task_name: str, task_payload: dict):
    """
    Execute TypeScript code. Supports two modes:
    1. Inline TypeScript code execution (using ts-node)
    2. TypeScript file execution (using ts-node)
    """
    record_task_start(run_id, task_name, self.request.id, "typescript")
    
    try:
        params = task_payload.get("params", {})
        
        # Mode 1: Inline TypeScript code execution
        if "code" in params:
            code = params["code"]
            env_vars = params.get("env", {})
            
            with tempfile.TemporaryDirectory() as tmpdir:
                # Write TypeScript code to temp file
                script_file = os.path.join(tmpdir, "script.ts")
                
                with open(script_file, 'w') as f:
                    f.write(code)
                
                # Execute with ts-node
                process = subprocess.run(
                    [settings.TS_NODE_PATH, script_file],
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
        
        # Mode 2: TypeScript file execution
        if "script_path" in params:
            script_path = params["script_path"]
            script_args = params.get("args", [])
            env_vars = params.get("env", {})
            
            if not os.path.exists(script_path):
                raise FileNotFoundError(f"Script not found: {script_path}")
            
            cmd = [settings.TS_NODE_PATH, script_path] + script_args
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
        
        # Mode 3: Compiled JavaScript execution (if TypeScript is pre-compiled)
        if "js_path" in params:
            js_path = params["js_path"]
            js_args = params.get("args", [])
            
            if not os.path.exists(js_path):
                raise FileNotFoundError(f"Compiled JavaScript file not found: {js_path}")
            
            cmd = [settings.NODE_PATH, js_path] + js_args
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
                "js_path": js_path
            }
            
            status = "SUCCESS" if process.returncode == 0 else "FAILURE"
            record_task_end(run_id, task_name, status, result)
            return result
        
        raise ValueError("TypeScript task requires 'code', 'script_path', or 'js_path' parameter")
        
    except subprocess.TimeoutExpired:
        error_result = {
            "error": "TypeScript execution timed out",
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
