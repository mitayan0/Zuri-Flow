from os import environ
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Database configuration
    DATABASE_URL: str = environ.get("DATABASE_URL")
    
    # Redis configuration
    REDIS_BROKER_URL: str = environ.get("REDIS_BROKER_URL")
    REDIS_BACKEND_URL: str = environ.get("REDIS_BACKEND_URL")
    
    # Application configuration
    APP_URL: str = environ.get("APP_URL", "http://localhost:8000")
    
    # Executor queues - all supported languages
    QUEUES: list[str] = [
        "orchestrator",  # Special queue for workflow orchestration
        "python",
        "bash",
        "c",
        "javascript",
        "go",
        "typescript"
    ]
    
    # Task execution settings
    TASK_TIMEOUT: int = int(environ.get("TASK_TIMEOUT", "3600"))  # 1 hour default
    TASK_SOFT_TIMEOUT: int = int(environ.get("TASK_SOFT_TIMEOUT", "3300"))  # 55 minutes default
    MAX_RETRIES: int = int(environ.get("MAX_RETRIES", "3"))
    
    # Executor-specific settings
    NODE_PATH: str = environ.get("NODE_PATH", "node")  # Path to Node.js executable
    GO_PATH: str = environ.get("GO_PATH", "go")  # Path to Go executable
    TS_NODE_PATH: str = environ.get("TS_NODE_PATH", "ts-node")  # Path to ts-node
    GCC_PATH: str = environ.get("GCC_PATH", "gcc")  # Path to GCC compiler
    
    # Feature flags
    ENABLE_TASK_METRICS: bool = environ.get("ENABLE_TASK_METRICS", "false").lower() == "true"
    ENABLE_DEBUG_LOGGING: bool = environ.get("ENABLE_DEBUG_LOGGING", "false").lower() == "true"

settings = Settings()

