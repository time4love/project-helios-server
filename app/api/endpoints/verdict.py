"""Verdict Engine API endpoints."""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.core.database import get_supabase
from app.schemas.verdict import VerdictResponse, TriggerResponse
from app.services.verdict import VerdictService

logger = logging.getLogger(__name__)

router = APIRouter()

# Secret for cron job authentication
TRIGGER_SECRET = os.getenv("VERDICT_TRIGGER_SECRET", "dev-secret")


def get_verdict_service(
    supabase: Client = Depends(get_supabase),
) -> VerdictService:
    """Dependency injection for VerdictService."""
    return VerdictService(supabase)


@router.get("/latest", response_model=VerdictResponse)
def get_latest_verdict(
    service: VerdictService = Depends(get_verdict_service),
) -> VerdictResponse:
    """
    Get the most recent verdict.

    Returns the latest Earth model analysis result with:
    - **total_samples**: Number of measurements analyzed
    - **valid_samples**: Measurements after outlier filtering
    - **avg_error_azimuth/altitude**: Mean absolute errors in degrees
    - **confidence_score**: 0-100 confidence rating
    - **winning_model**: "NASA" if score > 85, otherwise "ANOMALY"
    """
    verdict = service.get_latest()

    if verdict is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No verdicts found. Trigger a calculation first via POST /trigger.",
        )

    return verdict


@router.post("/trigger", response_model=TriggerResponse)
def trigger_verdict_calculation(
    secret: str = Query(..., description="Secret key for cron authentication"),
    service: VerdictService = Depends(get_verdict_service),
) -> TriggerResponse:
    """
    Trigger verdict calculation for the last 24 hours.

    Secured via secret query param for Vercel Cron jobs.

    Algorithm:
    1. Fetch measurements from last 24 hours
    2. Filter outliers (|delta| > 20 degrees)
    3. Calculate mean absolute error
    4. Score = 100 - (avg_az + avg_alt), clamped 0-100
    5. Winner: score > 85 => NASA, else ANOMALY
    """
    if secret != TRIGGER_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid trigger secret",
        )

    try:
        verdict = service.trigger_calculation()
        return TriggerResponse(
            success=True,
            verdict=verdict,
            message=f"Verdict calculated: {verdict.winning_model} wins with {verdict.confidence_score}% confidence",
        )
    except Exception as e:
        logger.error(f"Verdict calculation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Calculation failed: {str(e)}",
        )
