"""Pydantic models for solar position calculations."""

from datetime import datetime
from pydantic import BaseModel, Field


class SolarPositionRequest(BaseModel):
    """Request model for solar position calculation."""

    latitude: float = Field(..., ge=-90, le=90, description="Latitude in degrees (-90 to 90)")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in degrees (-180 to 180)")
    timestamp: datetime | None = Field(
        default=None,
        description="Timestamp for calculation (defaults to current UTC time)",
    )


class SolarPositionResponse(BaseModel):
    """Response model with calculated solar position."""

    azimuth: float = Field(..., description="Sun azimuth in degrees (0-360, North = 0)")
    altitude: float = Field(..., description="Sun altitude in degrees (-90 to 90, horizon = 0)")
    timestamp: datetime = Field(..., description="Timestamp used for calculation (UTC)")
