import json
import subprocess
import tempfile
import os
from celery import Task
from engine_core.celery_app import celery_app
from engine_core.common_utils import record_task_start, record_task_end
from config import settings


@celery_app.task(bind=True, name="runners.c_executor.executor_task", queue="c")
def executor_task(self: Task, run_id: str, task_name: str, task_payload: dict):
    """
    Execute C code. Supports two modes:
    1. Pre-compiled binary execution (if 'binary_path' is provided)
    2. Inline C code compilation and execution (if 'code' is provided)
    """
    record_task_start(run_id, task_name, self.request.id, "c")
    
    try:
        params = task_payload.get("params", {})
        
        # Mode 1: Execute pre-compiled binary
        if "binary_path" in params:
            binary_path = params["binary_path"]
            if not binary_path:
                raise ValueError("C task requires a 'binary_path' parameter")
            
            process = subprocess.run(
                binary_path,
                shell=True,
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
        
        # Mode 2: Compile and execute inline C code
        if "code" in params:
            code = params["code"]
            compiler_flags = params.get("compiler_flags", [])
            
            with tempfile.TemporaryDirectory() as tmpdir:
                # Write C code to temp file
                source_file = os.path.join(tmpdir, "program.c")
                binary_file = os.path.join(tmpdir, "program.exe" if os.name == 'nt' else "program")
                
                with open(source_file, 'w') as f:
                    f.write(code)
                
                # Compile
                compile_cmd = [settings.GCC_PATH, source_file, "-o", binary_file] + compiler_flags
                compile_process = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minutes for compilation
                )
                
                if compile_process.returncode != 0:
                    result = {
                        "compilation_error": compile_process.stderr,
                        "exit_code": compile_process.returncode
                    }
                    record_task_end(run_id, task_name, "FAILURE", result)
                    return result
                
                # Execute
                exec_process = subprocess.run(
                    binary_file,
                    capture_output=True,
                    text=True,
                    timeout=params.get("timeout", 3600)
                )
                
                result = {
                    "stdout": exec_process.stdout,
                    "stderr": exec_process.stderr,
                    "exit_code": exec_process.returncode,
                    "compilation_output": compile_process.stderr
                }
                
                status = "SUCCESS" if exec_process.returncode == 0 else "FAILURE"
                record_task_end(run_id, task_name, status, result)
                return result
        
        raise ValueError("C task requires either 'binary_path' or 'code' parameter")
        
    except Exception as e:
        error_result = {
            "error": str(e),
            "error_type": type(e).__name__,
            "task_name": task_name
        }
        record_task_end(run_id, task_name, "FAILURE", error_result)
        raise

