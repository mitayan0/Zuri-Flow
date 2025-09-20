from os import environ
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL: str = environ.get("DATABASE_URL")
    REDIS_BROKER_URL: str = environ.get("REDIS_BROKER_URL")
    REDIS_BACKEND_URL: str = environ.get("REDIS_BACKEND_URL")
    APP_URL: str = environ.get("APP_URL")
    QUEUES: list[str] = ["python", "bash", "c"]

settings = Settings()
