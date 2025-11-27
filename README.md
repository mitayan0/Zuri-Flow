
# Zuri Flow

**Zuri Flow** is a lightweight, multi-language workflow orchestration engine built on Celery, Redis, and PostgreSQL. It enables you to create complex task workflows with dependencies, supporting execution in **Python, JavaScript/Node.js, TypeScript, Go, Bash, and C**.

## ✨ Features

- 🔄 **Workflow Orchestration** - Define complex DAG workflows with task dependencies
- 🌍 **Multi-Language Support** - Execute tasks in 6+ programming languages
- ⚡ **Asynchronous Execution** - Powered by Celery for distributed task processing
- 🔗 **Task Dependencies** - Automatic dependency resolution and parallel execution
- 💾 **Persistent Results** - PostgreSQL backend for reliable result storage
- 📊 **Real-time Monitoring** - Track workflow and task status in real-time
- 🎯 **Standalone Tasks** - Execute individual tasks outside of workflows
- ⏰ **Scheduled Tasks** - Support for periodic/cron-like task execution
- 🚀 **Lightweight & Fast** - Minimal overhead, production-ready

## 📋 Requirements

- Python 3.10+
- Redis server
- PostgreSQL server
- Node.js (for JavaScript/TypeScript executors)
- Go compiler (for Go executor)
- GCC/Clang (for C executor - optional)

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/mitayan0/Zuri-Flow.git
cd Zuri-Flow
```

### 2. Create and activate virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example environment file and update with your settings:

```bash
copy .env.example .env  # Windows
# OR
cp .env.example .env    # Linux/macOS
```

Edit `.env` with your database and Redis connection strings.

### 5. Ensure Redis and PostgreSQL are running

Make sure both services are started and accessible at the URLs specified in your `.env` file.

## 🎯 Quick Start

### Start the FastAPI Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Start the Celery Worker

Open a new terminal and run:

```bash
celery -A engine_core.celery_app worker --loglevel=info -Q orchestrator,python,javascript,typescript,go,bash,c -P threads
```

### Create and Run a Workflow

Use the examples in the `examples/` directory or create your own:

```bash
# Example: Create a multi-language workflow
curl -X POST http://localhost:8000/api/v1/workflows/definitions \
  -H "Content-Type: application/json" \
  -d @examples/multi_language_pipeline.json

# Run the workflow (use the ID returned from above)
curl -X POST http://localhost:8000/api/v1/workflows/definitions/{definition_id}/run
```

## 🔧 Language Executors

### Python Executor

Supports three modes:

**1. Inline Code:**
```json
{
  "executor": "python",
  "params": {
    "code": "result = {'message': 'Hello from Python!', 'value': 42}"
  }
}
```

**2. Script File:**
```json
{
  "executor": "python",
  "params": {
    "script_path": "/path/to/script.py",
    "args": ["arg1", "arg2"]
  }
}
```

### JavaScript/Node.js Executor

**Inline Code:**
```json
{
  "executor": "javascript",
  "params": {
    "code": "const result = {message: 'Hello from Node.js!'}; console.log(JSON.stringify(result));"
  }
}
```

**NPM Module:**
```json
{
  "executor": "javascript",
  "params": {
    "module": "eslint",
    "args": ["--version"]
  }
}
```

### TypeScript Executor

**Inline Code:**
```json
{
  "executor": "typescript",
  "params": {
    "code": "interface Result { success: boolean; } const result: Result = { success: true }; console.log(JSON.stringify(result));"
  }
}
```

### Go Executor

**Inline Code:**
```json
{
  "executor": "go",
  "params": {
    "code": "package main\nimport \"fmt\"\nfunc main() {\n\tfmt.Println(\"Hello from Go!\")\n}"
  }
}
```

**Pre-compiled Binary:**
```json
{
  "executor": "go",
  "params": {
    "binary_path": "/path/to/binary"
  }
}
```

### Bash Executor

```json
{
  "executor": "bash",
  "params": {
    "command": "echo 'Hello from Bash!'",
    "cwd": "/path/to/working/dir",
    "env": {"MY_VAR": "value"}
  }
}
```

### C Executor

**Inline Code (will compile and run):**
```json
{
  "executor": "c",
  "params": {
    "code": "#include <stdio.h>\nint main() { printf(\"Hello from C!\\n\"); return 0; }",
    "compiler_flags": ["-O2"]
  }
}
```

## 📊 API Reference

### Workflow Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/workflows/definitions` | Create a workflow definition |
| `POST` | `/api/v1/workflows/definitions/{id}/run` | Execute a workflow |
| `GET` | `/api/v1/workflows/runs/{run_id}` | Get workflow run details |
| `GET` | `/api/v1/workflows/runs/{run_id}/status` | Get workflow run status |

### Standalone Task Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/tasks` | Create a standalone task |
| `POST` | `/api/v1/tasks/{task_id}/run` | Execute a task |
| `POST` | `/api/v1/tasks/{task_id}/schedule` | Schedule periodic task execution |

## 📝 Workflow Definition Format

```json
{
  "name": "My Workflow",
  "start_tasks": ["task1"],
  "tasks": {
    "task1": {
      "task_name": "task1",
      "executor": "python",
      "dependencies": [],
      "params": {
        "code": "result = {'status': 'complete'}"
      }
    },
    "task2": {
      "task_name": "task2",
      "executor": "javascript",
      "dependencies": ["task1"],
      "params": {
        "code": "console.log('Task 2 runs after task1');"
      }
    }
  }
}
```

## 🛠️ Advanced Configuration

### Custom Celery Queues

By default, Zuri Flow creates separate queues for each executor. You can customize queue configuration in `config.py`:

```python
QUEUES = [
    "orchestrator",
    "python",
    "javascript",
    "typescript",
    "go",
    "bash",
    "c"
]
```

### Task Timeouts

Configure task timeouts in `.env`:

```
TASK_TIMEOUT=3600          # 1 hour hard limit
TASK_SOFT_TIMEOUT=3300     # 55 minutes soft limit
```

### Monitoring with Flower

Start Flower for web-based Celery monitoring:

```bash
celery -A engine_core.celery_app flower
```

Access dashboard at: `http://localhost:5555`

## 🏗️ Architecture

```
┌─────────────┐
│  FastAPI    │  ← REST API Server
│  (main.py)  │
└──────┬──────┘
       │
       ├─────────────────────────┐
       │                         │
┌──────▼──────┐         ┌────────▼────────┐
│ PostgreSQL  │         │  Redis (Broker) │
│  (Workflow  │         │   & Backend     │
│   Data)     │         └─────────────────┘
└─────────────┘                  │
                                 │
                        ┌────────▼─────────┐
                        │  Celery Workers  │
                        │  ┌─────────────┐ │
                        │  │Orchestrator │ │
                        │  ├─────────────┤ │
                        │  │  Python     │ │
                        │  │  JavaScript │ │
                        │  │  TypeScript │ │
                        │  │  Go         │ │
                        │  │  Bash       │ │
                        │  │  C          │ │
                        │  └─────────────┘ │
                        └──────────────────┘
```

## 🎓 Examples

Check the `examples/` directory for workflow templates:

- `python_hello_world.json` - Simple Python task
- `javascript_data_processing.json` - JavaScript data processing
- `multi_language_pipeline.json` - Complex multi-language workflow with dependencies
- `typescript_example.json` - TypeScript execution example

## 🐛 Troubleshooting

### Common Issues

**1. Celery workers not picking up tasks**
- Ensure all queues are specified when starting workers
- Check Redis connection

**2. Task execution fails with "executor not found"**
- Verify the language runtime is installed (node, go, gcc, etc.)
- Check `config.py` for correct executor paths

**3. Database connection errors**
- Verify PostgreSQL is running
- Check `DATABASE_URL` in `.env`

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- Built with [Celery](https://docs.celeryq.dev/)
- Powered by [FastAPI](https://fastapi.tiangolo.com/)
- Inspired by Apache Airflow and Temporal
