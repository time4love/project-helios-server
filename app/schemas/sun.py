"""Pydantic models for solar position calculations."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SolarPositionRequest(BaseModel):
    """Request model for solar position calculation (lookup only)."""

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


class MeasurementRequest(BaseModel):
    """Request model for saving a measurement with device sensor data."""

    latitude: float = Field(..., ge=-90, le=90, description="Latitude in degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in degrees")
    device_azimuth: float = Field(..., ge=0, le=360, description="Device measured azimuth (0-360)")
    device_altitude: float = Field(..., ge=-90, le=90, description="Device measured altitude (-90 to 90)")
    timestamp: datetime | None = Field(
        default=None,
        description="Timestamp for calculation (defaults to current UTC time)",
    )


class MeasurementResponse(BaseModel):
    """Response model with full measurement data including saved ID."""

    id: int = Field(..., description="Database ID of the saved measurement")
    created_at: datetime = Field(..., description="Timestamp when measurement was saved")

    # Location
    latitude: float
    longitude: float

    # Device readings
    device_azimuth: float
    device_altitude: float

    # Calculated NASA/Pysolar values
    nasa_azimuth: float
    nasa_altitude: float

    # Deltas (device - nasa)
    delta_azimuth: float
    delta_altitude: float

    class Config:
        from_attributes = True  # Allows creating from ORM model
