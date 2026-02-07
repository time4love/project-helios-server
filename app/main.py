"""Project Helios API - FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import solar
from app.core.config import APP_NAME, APP_VERSION, API_V1_PREFIX

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Backend API for Project Helios - Solar position calculations",
)

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
