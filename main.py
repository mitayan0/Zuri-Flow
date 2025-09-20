from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from engine_core import database_utils
from api.workflows import router as WorkflowRouter
from config import settings

app = FastAPI(
    title="Zuri Flow",
    description="Enterprise workflow engine built on FastAPI, Celery & PostgreSQL",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    database_utils.create_all_tables(database_utils.get_db_engine())
    print("Database tables created successfully.")

app.include_router(WorkflowRouter)

@app.get("/")
def root():
    return {"message": "Welcome to Zuri Flow workflow engine"}
