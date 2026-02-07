"""Astronomy calculations using Pysolar."""

from datetime import datetime, timezone
from pysolar.solar import get_altitude, get_azimuth


def calculate_sun_position(
    lat: float,
    lon: float,
    dt: datetime | None = None,
) -> dict:
    """
    Calculate the sun's position for a given location and time.

    Args:
        lat: Latitude in degrees (-90 to 90)
        lon: Longitude in degrees (-180 to 180)
        dt: Datetime for calculation (defaults to current UTC time)

    Returns:
        Dictionary with altitude, azimuth, and timestamp
    """
    # Ensure UTC timezone for Pysolar
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        # Naive datetime - assume UTC
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC
        dt = dt.astimezone(timezone.utc)

    altitude = get_altitude(lat, lon, dt)
    azimuth = get_azimuth(lat, lon, dt)

    return {
        "altitude": altitude,
        "azimuth": azimuth,
        "timestamp": dt,
    }
