"""Pydantic schemas for Verdict Engine API."""

from datetime import datetime
from pydantic import BaseModel, Field


class VerdictResponse(BaseModel):
    """Response schema for verdict endpoints."""

    id: int = Field(..., description="Database ID of the verdict")
    created_at: str = Field(..., description="Timestamp when verdict was created (ISO format)")
    total_samples: int = Field(..., description="Total measurements analyzed")
    valid_samples: int = Field(..., description="Samples after outlier filtering")
    avg_error_azimuth: float = Field(..., description="Mean absolute error for azimuth (degrees)")
    avg_error_altitude: float = Field(..., description="Mean absolute error for altitude (degrees)")
    confidence_score: float = Field(..., ge=0, le=100, description="Confidence score 0-100")
    winning_model: str = Field(..., description="NASA or ANOMALY")


class TriggerResponse(BaseModel):
    """Response schema for trigger endpoint."""

    success: bool
    verdict: VerdictResponse
    message: str
