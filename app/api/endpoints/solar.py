"""Solar position calculation endpoints."""

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from supabase import Client

from app.core.database import get_supabase
from app.schemas.sun import (
    SolarPositionRequest,
    SolarPositionResponse,
    MeasurementRequest,
    MeasurementResponse,
    StatsResponse,
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


@router.get("/stats", response_model=StatsResponse)
def get_stats(
    target_date: date | None = Query(
        default=None,
        description="Date to calculate statistics for (YYYY-MM-DD). Defaults to today.",
    ),
    service: MeasurementService = Depends(get_measurement_service),
) -> StatsResponse:
    """
    Get statistics for measurements on a specific date.

    - **target_date**: Date to calculate stats for (defaults to today)

    Returns:
    - **count**: Total number of measurements
    - **avg_delta_azimuth**: Average azimuth delta (device - NASA)
    - **avg_delta_altitude**: Average altitude delta (device - NASA)
    - **std_dev_azimuth**: Standard deviation of azimuth deltas
    - **std_dev_altitude**: Standard deviation of altitude deltas
    """
    return service.get_stats_by_date(target_date=target_date)


@router.get("/export")
def export_csv(
    target_date: date | None = Query(
        default=None,
        description="Date to export (YYYY-MM-DD). Defaults to today.",
    ),
    service: MeasurementService = Depends(get_measurement_service),
) -> StreamingResponse:
    """
    Export measurements as a CSV file.

    - **target_date**: Date to export (defaults to today)

    Returns a downloadable CSV file with all measurements for the specified date.
    """
    csv_content = service.export_csv_by_date(target_date=target_date)

    # Format filename with date
    export_date = target_date or date.today()
    filename = f"helios_data_{export_date}.csv"

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
