"""Solar position calculation endpoints."""

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.core.database import get_supabase
from app.schemas.sun import (
    SolarPositionRequest,
    SolarPositionResponse,
    MeasurementRequest,
    MeasurementResponse,
)
from app.services.astronomy import calculate_sun_position
from app.services.measurement import (
    MeasurementService,
    RateLimitExceeded,
    MeasurementSaveFailed,
)

router = APIRouter()


def get_measurement_service(
    supabase: Client = Depends(get_supabase),
) -> MeasurementService:
    """Dependency injection for MeasurementService."""
    return MeasurementService(supabase)


@router.post("/calculate", response_model=SolarPositionResponse)
def calculate_solar_position(request: SolarPositionRequest) -> SolarPositionResponse:
    """
    Calculate the sun's position for a given location and time.

    - **latitude**: Latitude in degrees (-90 to 90)
    - **longitude**: Longitude in degrees (-180 to 180)
    - **timestamp**: Optional datetime (defaults to current UTC time)

    Returns the sun's azimuth and altitude angles.
    """
    result = calculate_sun_position(
        lat=request.latitude,
        lon=request.longitude,
        dt=request.timestamp,
    )
    return SolarPositionResponse(**result)


@router.post("/measure", response_model=MeasurementResponse)
def save_measurement(
    request: MeasurementRequest,
    service: MeasurementService = Depends(get_measurement_service),
) -> MeasurementResponse:
    """
    Save a measurement comparing device sensor data with calculated sun position.

    - **latitude/longitude**: Location where measurement was taken
    - **device_azimuth/device_altitude**: What the device sensors reported
    - **device_id**: Anonymous device identifier for rate limiting
    - **timestamp**: Optional datetime (defaults to current UTC time)

    Calculates the NASA/Pysolar sun position, computes deltas, and saves to database.
    Returns the full measurement record including the database ID.

    Rate limited to one measurement per device every 10 seconds.
    """
    try:
        return service.create_measurement(request)
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please wait {e.wait_seconds} seconds.",
        )
    except MeasurementSaveFailed:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save measurement",
        )


@router.get("/measurements", response_model=List[MeasurementResponse])
def get_measurements(
    target_date: date | None = Query(
        default=None,
        description="Filter measurements by date (YYYY-MM-DD). Defaults to today if not provided.",
    ),
    limit: int = Query(
        default=5000, ge=1, le=5000, description="Max number of measurements to return"
    ),
    service: MeasurementService = Depends(get_measurement_service),
) -> List[MeasurementResponse]:
    """
    Retrieve measurements for visualization, filtered by date.

    - **target_date**: Date to filter measurements (defaults to today's date)
    - **limit**: Maximum number of measurements to return (default: 5000, max: 5000)

    Returns measurements ordered by created_at descending (most recent first).
    """
    return service.get_measurements_by_date(target_date=target_date, limit=limit)
