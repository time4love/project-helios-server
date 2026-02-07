"""Solar position calculation endpoints."""

from datetime import datetime, timezone
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

router = APIRouter()

# Rate limit: minimum seconds between measurements per device
RATE_LIMIT_SECONDS = 10


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
    supabase: Client = Depends(get_supabase)
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
    now = datetime.now(timezone.utc)

    # Rate limiting: Check for recent measurements from this device
    rate_limit_response = (
        supabase.table("measurements")
        .select("created_at")
        .eq("device_id", request.device_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if rate_limit_response.data:
        last_time_str = rate_limit_response.data[0]["created_at"]
        # Parse ISO format timestamp from Supabase
        last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
        time_diff = (now - last_time).total_seconds()

        if time_diff < RATE_LIMIT_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Please wait {int(RATE_LIMIT_SECONDS - time_diff)} seconds.",
            )

    # Calculate the actual sun position using Pysolar
    sun_position = calculate_sun_position(
        lat=request.latitude,
        lon=request.longitude,
        dt=request.timestamp,
    )

    # Calculate deltas (device reading - calculated position)
    delta_azimuth = request.device_azimuth - sun_position["azimuth"]
    delta_altitude = request.device_altitude - sun_position["altitude"]

    # Prepare measurement record
    measurement_data = {
        "device_id": request.device_id,
        "latitude": request.latitude,
        "longitude": request.longitude,
        "device_azimuth": request.device_azimuth,
        "device_altitude": request.device_altitude,
        "nasa_azimuth": sun_position["azimuth"],
        "nasa_altitude": sun_position["altitude"],
        "delta_azimuth": delta_azimuth,
        "delta_altitude": delta_altitude,
    }

    # Save to Supabase via REST API
    insert_response = (
        supabase.table("measurements")
        .insert(measurement_data)
        .execute()
    )

    if not insert_response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save measurement",
        )

    # Return the saved record
    saved = insert_response.data[0]
    return MeasurementResponse(
        id=saved["id"],
        created_at=saved["created_at"],
        device_id=saved.get("device_id"),
        latitude=saved["latitude"],
        longitude=saved["longitude"],
        device_azimuth=saved["device_azimuth"],
        device_altitude=saved["device_altitude"],
        nasa_azimuth=saved["nasa_azimuth"],
        nasa_altitude=saved["nasa_altitude"],
        delta_azimuth=saved["delta_azimuth"],
        delta_altitude=saved["delta_altitude"],
    )


@router.get("/measurements", response_model=List[MeasurementResponse])
def get_measurements(
    limit: int = Query(default=100, ge=1, le=1000, description="Max number of measurements to return"),
    supabase: Client = Depends(get_supabase)
) -> List[MeasurementResponse]:
    """
    Retrieve recent measurements for visualization.

    - **limit**: Maximum number of measurements to return (default: 100, max: 1000)

    Returns measurements ordered by created_at descending (most recent first).
    """
    response = (
        supabase.table("measurements")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return [
        MeasurementResponse(
            id=row["id"],
            created_at=row["created_at"],
            device_id=row.get("device_id"),
            latitude=row["latitude"],
            longitude=row["longitude"],
            device_azimuth=row["device_azimuth"],
            device_altitude=row["device_altitude"],
            nasa_azimuth=row["nasa_azimuth"],
            nasa_altitude=row["nasa_altitude"],
            delta_azimuth=row["delta_azimuth"],
            delta_altitude=row["delta_altitude"],
        )
        for row in response.data
    ]
