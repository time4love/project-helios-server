"""Verdict Engine API endpoints."""

import logging
import os
from datetime import date

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
    target_date: date | None = Query(
        default=None,
        description="Filter by specific date (YYYY-MM-DD). If not provided, returns the most recent verdict.",
    ),
    service: VerdictService = Depends(get_verdict_service),
) -> VerdictResponse:
    """
    Get the most recent verdict, optionally filtered by date.

    - **target_date**: Optional date to get verdict for (YYYY-MM-DD format)

    Returns the Earth model analysis result with:
    - **total_samples**: Number of measurements analyzed
    - **valid_samples**: Measurements after outlier filtering
    - **avg_error_azimuth/altitude**: Mean absolute errors in degrees
    - **confidence_score**: 0-100 confidence rating
    - **winning_model**: "NASA" if score > 85, otherwise "ANOMALY"
    """
    verdict = service.get_latest(target_date=target_date)

    if verdict is None:
        if target_date:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No verdict found for {target_date}. Trigger a calculation first.",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No verdicts found. Trigger a calculation first via POST /trigger.",
        )

    return verdict


@router.post("/trigger", response_model=TriggerResponse)
def trigger_verdict_calculation(
    secret: str = Query(..., description="Secret key for cron authentication"),
    target_date: date | None = Query(
        default=None,
        description="Calculate verdict for a specific date (YYYY-MM-DD). If not provided, uses last 24 hours.",
    ),
    service: VerdictService = Depends(get_verdict_service),
) -> TriggerResponse:
    """
    Trigger verdict calculation for a specific date or last 24 hours.

    Secured via secret query param for Vercel Cron jobs.

    - **target_date**: Optional date to calculate verdict for (YYYY-MM-DD format).
                       If provided, analyzes measurements for that full day.
                       If a verdict already exists for that date, it will be replaced.
    - **secret**: Required authentication secret for cron jobs.

    Algorithm:
    1. Fetch measurements (from target_date or last 24 hours)
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
        verdict = service.trigger_calculation(target_date=target_date)
        date_info = f" for {target_date}" if target_date else ""
        return TriggerResponse(
            success=True,
            verdict=verdict,
            message=f"Verdict calculated{date_info}: {verdict.winning_model} wins with {verdict.confidence_score}% confidence",
        )
    except Exception as e:
        logger.error(f"Verdict calculation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Calculation failed: {str(e)}",
        )
