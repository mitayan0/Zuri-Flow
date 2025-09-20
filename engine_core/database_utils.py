from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from engine_core.models import Base
from config import settings

def get_db_engine():
    return create_engine(settings.DATABASE_URL)

def create_all_tables(engine):
    Base.metadata.create_all(engine)

def get_db_session_factory():
    return sessionmaker(autocommit=False, autoflush=False, bind=get_db_engine())
