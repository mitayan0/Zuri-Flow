
# Zuri Flow

Zuri Flow is a lightweight task queue system using Celery, Redis, and PostgreSQL. It is designed to run smoothly and allows you to create asynchronous and periodic tasks with persistent results.

## Features

- Asynchronous task execution with Celery
- Redis as a fast message broker
- PostgreSQL as a reliable result backend
- Easy task creation and execution

## Requirements

- Python 3.10+
- Redis server
- PostgreSQL server

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/zuri-flow.git
cd zuri-flow
```

2.Install dependencies:

```bash
pip install -r requirements.txt
```

3.Ensure Redis and PostgreSQL are running.

## Usage

### Start Celery Worker

```bash
celery -A celery_app.celery_app worker -l info -P threads
```

### Define and Run a Task

```python
from celery_app import celery_app

@celery_app.task
def add(x, y):
    return x + y

##Run task

result = add.delay(10,20)
print(result.get(timeout=10))
```

## TODO

- Add support for periodic tasks with RedBeat
- Add Celery Flower to monitor tasks and workers
- Add authentication for task submission API
- Implement automatic retry and error handling for failed tasks
- Write unit tests for core task execution
- Provide Docker configuration for easier deployment
- Improve logging and metrics collection
- Add examples for complex task workflows (chained and group tasks)

## 🤝Contributing

Contributions are welcome!
Please fork the repository and submit a pull request.
Contributions are welcome!
Please fork the repository and submit a pull request.
