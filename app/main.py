"""Project Helios API - FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import solar
from app.core.config import APP_NAME, APP_VERSION, API_V1_PREFIX
from app.core.database import engine, Base

# Import models to register them with SQLAlchemy
from app.models import measurement  # noqa: F401

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Backend API for Project Helios - Solar position calculations",
)

# Create database tables if they don't exist
# Note: In production, use Alembic migrations instead
if engine is not None:
    Base.metadata.create_all(bind=engine)

# CORS middleware - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    solar.router,
    prefix=f"{API_V1_PREFIX}/solar",
    tags=["Solar"],
)


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "Helios Server Running"}


@app.get("/health")
def health_check():
    """Detailed health check including database status."""
    db_status = "connected" if engine is not None else "not configured"
    return {
        "status": "healthy",
        "database": db_status,
        "version": APP_VERSION,
    }
