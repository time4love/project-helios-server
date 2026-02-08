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
    device_azimuth: float = Field(..., ge=0, le=360, description="Device measured azimuth (0-360, True North)")
    device_altitude: float = Field(..., ge=-90, le=90, description="Device measured altitude (-90 to 90)")
    device_id: str = Field(..., min_length=1, description="Anonymous device identifier for rate limiting")
    magnetic_azimuth: float | None = Field(
        default=None,
        ge=0,
        le=360,
        description="Raw magnetic compass azimuth before declination correction (0-360)",
    )
    magnetic_declination: float | None = Field(
        default=None,
        description="Magnetic declination applied (positive = east, negative = west)",
    )
    timestamp: datetime | None = Field(
        default=None,
        description="Timestamp for calculation (defaults to current UTC time)",
    )


class MeasurementResponse(BaseModel):
    """Response model with full measurement data including saved ID."""

    id: int = Field(..., description="Database ID of the saved measurement")
    created_at: str = Field(..., description="Timestamp when measurement was saved (ISO format)")
    device_id: str | None = Field(None, description="Anonymous device identifier")

    # Location
    latitude: float
    longitude: float

    # Device readings (True North corrected)
    device_azimuth: float
    device_altitude: float

    # Raw magnetic readings (before declination correction)
    magnetic_azimuth: float | None = None
    magnetic_declination: float | None = None

    # Calculated NASA/Pysolar values
    nasa_azimuth: float
    nasa_altitude: float

    # Deltas (device - nasa)
    delta_azimuth: float
    delta_altitude: float

    # Flat Earth triangulation test
    flat_earth_sun_height_km: float | None = Field(
        None,
        description="Calculated sun height (km) assuming flat Earth model. "
        "Consistent values would support flat Earth; high variance supports globe.",
    )


class StatsResponse(BaseModel):
    """Response model for measurement statistics."""

    count: int = Field(..., description="Total number of measurements")
    avg_delta_azimuth: float | None = Field(
        None, description="Average delta azimuth in degrees"
    )
    avg_delta_altitude: float | None = Field(
        None, description="Average delta altitude in degrees"
    )
    std_dev_azimuth: float | None = Field(
        None, description="Standard deviation of delta azimuth"
    )
    std_dev_altitude: float | None = Field(
        None, description="Standard deviation of delta altitude"
    )

    # Flat Earth triangulation statistics
    flat_earth_samples: int | None = Field(
        None, description="Number of samples with valid flat Earth height calculation"
    )
    avg_flat_earth_sun_height_km: float | None = Field(
        None,
        description="Average calculated sun height (km) assuming flat Earth. "
        "Real sun is ~150M km away; flat Earth model claims ~5000 km.",
    )
    std_dev_flat_earth_sun_height_km: float | None = Field(
        None,
        description="Standard deviation of flat Earth sun height. "
        "Low value = consistent (flat Earth prediction). "
        "High value = inconsistent (globe prediction).",
    )
