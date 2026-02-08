"""Astronomy calculations using Pysolar."""

import math
from datetime import datetime, timezone
from pysolar.solar import get_altitude, get_azimuth

# Earth radius in km (for Haversine calculation)
EARTH_RADIUS_KM = 6371.0

# Minimum altitude to calculate flat earth height (avoid tan(0) issues)
MIN_ALTITUDE_FOR_FLAT_EARTH = 5.0


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


def calculate_subsolar_point(dt: datetime | None = None) -> tuple[float, float]:
    """
    Calculate the sub-solar point (where the sun is directly overhead).

    Uses solar declination for latitude and solar hour angle for longitude.

    Args:
        dt: Datetime for calculation (defaults to current UTC time)

    Returns:
        Tuple of (latitude, longitude) of sub-solar point
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    # Day of year (1-366)
    day_of_year = dt.timetuple().tm_yday

    # Solar declination (latitude where sun is overhead)
    # Approximation: δ = -23.45° * cos(360/365 * (day + 10))
    declination = -23.45 * math.cos(math.radians(360 / 365 * (day_of_year + 10)))

    # Solar hour angle -> longitude
    # At solar noon, the sun is overhead at longitude = 0° at 12:00 UTC
    # Longitude = (12 - UTC_hour) * 15 degrees
    hours_from_midnight = dt.hour + dt.minute / 60 + dt.second / 3600
    subsolar_longitude = (12 - hours_from_midnight) * 15

    # Normalize longitude to -180 to 180
    if subsolar_longitude > 180:
        subsolar_longitude -= 360
    elif subsolar_longitude < -180:
        subsolar_longitude += 360

    return (declination, subsolar_longitude)


def haversine_distance_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the great-circle distance between two points on Earth.

    Uses the Haversine formula.

    Args:
        lat1, lon1: First point (degrees)
        lat2, lon2: Second point (degrees)

    Returns:
        Distance in kilometers
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    # Haversine formula
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def calculate_flat_earth_sun_height(
    user_lat: float,
    user_lon: float,
    device_altitude: float,
    dt: datetime | None = None,
) -> float | None:
    """
    Calculate the sun's height assuming a flat Earth model.

    On a flat Earth, if we know:
    - Our distance (D) to the point where the sun is "directly overhead" (sub-solar point)
    - The angle (θ) at which we observe the sun

    Then: H = D * tan(θ)

    If Earth were flat, this height should be consistent (~5000 km per flat Earth claims).
    On a globe, this value will vary wildly based on location and time.

    Args:
        user_lat: User's latitude
        user_lon: User's longitude
        device_altitude: Observed sun altitude angle in degrees
        dt: Datetime for calculation

    Returns:
        Calculated sun height in km, or None if altitude too low
    """
    # Don't calculate for low altitudes (near horizon)
    if device_altitude < MIN_ALTITUDE_FOR_FLAT_EARTH:
        return None

    # Find the sub-solar point
    subsolar_lat, subsolar_lon = calculate_subsolar_point(dt)

    # Calculate surface distance from user to sub-solar point
    distance_km = haversine_distance_km(
        user_lat, user_lon, subsolar_lat, subsolar_lon
    )

    # Calculate height using flat Earth triangulation
    # H = D * tan(altitude_angle)
    altitude_radians = math.radians(device_altitude)
    sun_height_km = distance_km * math.tan(altitude_radians)

    return sun_height_km
