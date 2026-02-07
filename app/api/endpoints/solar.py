"""Solar position calculation endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.models.measurement import Measurement
from app.schemas.sun import (
    SolarPositionRequest,
    SolarPositionResponse,
    MeasurementRequest,
    MeasurementResponse,
)
from app.services.astronomy import calculate_sun_position

router = APIRouter()


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
    - **timestamp**: Optional datetime (defaults to current UTC time)

    Calculates the NASA/Pysolar sun position, computes deltas, and saves to database.
    Returns the full measurement record including the database ID.
    """
    # Calculate the actual sun position using Pysolar
    sun_position = calculate_sun_position(
        lat=request.latitude,
        lon=request.longitude,
        dt=request.timestamp,
    )

    # Calculate deltas (device reading - calculated position)
    delta_azimuth = request.device_azimuth - sun_position["azimuth"]
    delta_altitude = request.device_altitude - sun_position["altitude"]

    # Create measurement record
    measurement = Measurement(
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
