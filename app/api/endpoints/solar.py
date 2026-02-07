"""Solar position calculation endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.measurement import Measurement
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
def save_measurement(request: MeasurementRequest, db: Session = Depends(get_db)) -> MeasurementResponse:
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
    # Rate limiting: Check for recent measurements from this device
    last_measurement = (
        db.query(Measurement)
        .filter(Measurement.device_id == request.device_id)
        .order_by(Measurement.created_at.desc())
        .first()
    )

    if last_measurement:
        now = datetime.now(timezone.utc)
        # Handle timezone-naive datetime from DB
        last_time = last_measurement.created_at
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)

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

    # Create measurement record with device_id
    measurement = Measurement(
        device_id=request.device_id,
        latitude=request.latitude,
        longitude=request.longitude,
        device_azimuth=request.device_azimuth,
        device_altitude=request.device_altitude,
        nasa_azimuth=sun_position["azimuth"],
        nasa_altitude=sun_position["altitude"],
        delta_azimuth=delta_azimuth,
        delta_altitude=delta_altitude,
    )

    # Save to database
    db.add(measurement)
    db.commit()
    db.refresh(measurement)

    return MeasurementResponse.model_validate(measurement)
