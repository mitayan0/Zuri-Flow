import json
import subprocess
import tempfile
import os
from celery import Task
from engine_core.celery_app import celery_app
from engine_core.common_utils import record_task_start, record_task_end
from config import settings


@celery_app.task(bind=True, name="runners.go_executor.executor_task", queue="go")
def executor_task(self: Task, run_id: str, task_name: str, task_payload: dict):
    """
    Execute Go code. Supports three modes:
    1. Inline Go code execution (compile and run with 'go run')
    2. Pre-compiled Go binary execution
    3. Go module execution
    """
    record_task_start(run_id, task_name, self.request.id, "go")
    
    try:
        params = task_payload.get("params", {})
        
        # Mode 1: Inline Go code execution
        if "code" in params:
            code = params["code"]
            env_vars = params.get("env", {})
            
            with tempfile.TemporaryDirectory() as tmpdir:
                # Write Go code to temp file
                source_file = os.path.join(tmpdir, "main.go")
                
                with open(source_file, 'w') as f:
                    f.write(code)
                
                # Run with 'go run'
                process = subprocess.run(
                    [settings.GO_PATH, "run", source_file],
                    capture_output=True,
                    text=True,
                    timeout=params.get("timeout", 3600),
                    cwd=tmpdir,
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
        
        # Mode 2: Pre-compiled binary execution
        if "binary_path" in params:
            binary_path = params["binary_path"]
            binary_args = params.get("args", [])
            
            if not os.path.exists(binary_path):
                raise FileNotFoundError(f"Binary not found: {binary_path}")
            
            cmd = [binary_path] + binary_args
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
                "binary_path": binary_path
            }
            
            status = "SUCCESS" if process.returncode == 0 else "FAILURE"
            record_task_end(run_id, task_name, status, result)
            return result
        
        # Mode 3: Go source file execution
        if "source_path" in params:
            source_path = params["source_path"]
            
            if not os.path.exists(source_path):
                raise FileNotFoundError(f"Source file not found: {source_path}")
            
            # Run with 'go run'
            process = subprocess.run(
                [settings.GO_PATH, "run", source_path],
                capture_output=True,
                text=True,
                timeout=params.get("timeout", 3600),
                cwd=os.path.dirname(source_path)
            )
            
            result = {
                "stdout": process.stdout,
                "stderr": process.stderr,
                "exit_code": process.returncode,
                "source_path": source_path
            }
            
            status = "SUCCESS" if process.returncode == 0 else "FAILURE"
            record_task_end(run_id, task_name, status, result)
            return result
        
        raise ValueError("Go task requires 'code', 'binary_path', or 'source_path' parameter")
        
    except subprocess.TimeoutExpired:
        error_result = {
            "error": "Go execution timed out",
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
