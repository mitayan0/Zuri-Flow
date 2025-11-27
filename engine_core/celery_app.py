from celery import Celery
from config import settings

celery_app = Celery(
    "zuri_flow",
    broker=settings.REDIS_BROKER_URL,
    backend=settings.REDIS_BACKEND_URL,
    include=[
        "engine_core.orchestrator",
        "runners.python_executor",
        "runners.bash_executor",
        "runners.c_executor",
        "runners.javascript_executor",
        "runners.go_executor",
        "runners.typescript_executor",
    ]
)

# --- Celery configuration ---
celery_app.conf.update(
    # Task execution settings
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3300,  # 55 minutes soft limit
    
    # Result backend settings
    result_expires=86400,  # Results expire after 24 hours
    result_backend_transport_options={'master_name': 'mymaster'},
    
    # Retry settings
    task_default_retry_delay=60,  # Retry after 60 seconds
    task_max_retries=3,
    
    # Serialization
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Beat schedule (for periodic tasks)
    beat_schedule={},
    
    # Task routing - map tasks to specific queues
    task_routes={
        'engine_core.orchestrator.workflow_orchestrator': {'queue': 'orchestrator'},
        'runners.python_executor.executor_task': {'queue': 'python'},
        'runners.bash_executor.executor_task': {'queue': 'bash'},
        'runners.c_executor.executor_task': {'queue': 'c'},
        'runners.javascript_executor.executor_task': {'queue': 'javascript'},
        'runners.go_executor.executor_task': {'queue': 'go'},
        'runners.typescript_executor.executor_task': {'queue': 'typescript'},
    },
    
    # Queue definitions
    task_queues={
        'orchestrator': {
            'exchange': 'orchestrator',
            'routing_key': 'orchestrator',
        },
        'python': {
            'exchange': 'python',
            'routing_key': 'python',
        },
        'bash': {
            'exchange': 'bash',
            'routing_key': 'bash',
        },
        'c': {
            'exchange': 'c',
            'routing_key': 'c',
        },
        'javascript': {
            'exchange': 'javascript',
            'routing_key': 'javascript',
        },
        'go': {
            'exchange': 'go',
            'routing_key': 'go',
        },
        'typescript': {
            'exchange': 'typescript',
            'routing_key': 'typescript',
        },
    },
)

