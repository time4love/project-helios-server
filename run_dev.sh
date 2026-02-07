#!/bin/bash

# Activate virtual environment
source venv/bin/activate 2>/dev/null || {
    echo "Could not activate venv automatically."
    echo "Run: source venv/bin/activate"
    echo "Then: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    exit 1
}

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
