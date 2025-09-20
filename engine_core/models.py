import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    definition = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    definition_id = Column(String(255), ForeignKey("workflow_definitions.id"))
    status = Column(String(50), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

class TaskInstance(Base):
    __tablename__ = "task_instances"
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(255), ForeignKey("workflow_runs.id"))
    task_name = Column(String(255), nullable=False)
    language = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)
    celery_task_id = Column(String(255), nullable=False)
    result = Column(JSON)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

class StandaloneTask(Base):
    __tablename__ = "standalone_tasks"
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_name = Column(String(255), nullable=False)
    executor = Column(String(50), nullable=False)
    default_params = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
