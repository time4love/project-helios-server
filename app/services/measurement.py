"""Measurement service layer for business logic separation."""

import csv
import io
import statistics
from datetime import date, datetime, timezone
from typing import List

from supabase import Client

from app.schemas.sun import MeasurementRequest, MeasurementResponse, StatsResponse
from app.services.astronomy import (
    calculate_sun_position,
    calculate_flat_earth_sun_height,
)


class RateLimitExceeded(Exception):
    """Raised when a device exceeds the rate limit."""

    def __init__(self, wait_seconds: int):
        self.wait_seconds = wait_seconds
        super().__init__(f"Rate limit exceeded. Please wait {wait_seconds} seconds.")


class MeasurementSaveFailed(Exception):
    """Raised when a measurement fails to save to the database."""

    pass


def _row_to_response(row: dict) -> MeasurementResponse:
    """Convert a database row to a MeasurementResponse."""
    return MeasurementResponse(
        id=row["id"],
        created_at=row["created_at"],
        device_id=row.get("device_id"),
        latitude=row["latitude"],
        longitude=row["longitude"],
        device_azimuth=row["device_azimuth"],
        device_altitude=row["device_altitude"],
        magnetic_azimuth=row.get("magnetic_azimuth"),
        magnetic_declination=row.get("magnetic_declination"),
        nasa_azimuth=row["nasa_azimuth"],
        nasa_altitude=row["nasa_altitude"],
        delta_azimuth=row["delta_azimuth"],
        delta_altitude=row["delta_altitude"],
        flat_earth_sun_height_km=row.get("flat_earth_sun_height_km"),
    )


class MeasurementService:
    """
    Service layer for measurement operations.

    Separates business logic from route handlers and data access details.
    """

    # Rate limit: minimum seconds between measurements per device
    RATE_LIMIT_SECONDS = 10

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def check_rate_limit(self, device_id: str) -> None:
        """
        Check if the device is within rate limits.

        Args:
            device_id: Anonymous device identifier

        Raises:
            RateLimitExceeded: If the device has made a measurement too recently
        """
        now = datetime.now(timezone.utc)

        response = (
            self.supabase.table("measurements")
            .select("created_at")
            .eq("device_id", device_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if response.data:
            last_time_str = response.data[0]["created_at"]
            # Parse ISO format timestamp from Supabase
            last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
            time_diff = (now - last_time).total_seconds()

            if time_diff < self.RATE_LIMIT_SECONDS:
                wait_seconds = int(self.RATE_LIMIT_SECONDS - time_diff)
                raise RateLimitExceeded(wait_seconds)

    def create_measurement(self, request: MeasurementRequest) -> MeasurementResponse:
        """
        Create a new measurement with SQL-based rate limiting (legacy).

        Calculates sun position, computes deltas, and saves to database.

        Args:
            request: Measurement request with device sensor data

        Returns:
            The saved measurement record

        Raises:
            RateLimitExceeded: If the device is rate limited
            MeasurementSaveFailed: If the database insert fails
        """
        # Check rate limit first (legacy SQL-based check)
        self.check_rate_limit(request.device_id)
        return self.create_measurement_without_rate_check(request)

    def create_measurement_without_rate_check(
        self, request: MeasurementRequest
    ) -> MeasurementResponse:
        """
        Create a new measurement without rate limiting check.

        Used when rate limiting is handled externally (e.g., Redis).

        Args:
            request: Measurement request with device sensor data

        Returns:
            The saved measurement record

        Raises:
            MeasurementSaveFailed: If the database insert fails
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

        # Calculate flat Earth sun height (triangulation test)
        # Uses device_altitude (observed angle) and distance to sub-solar point
        flat_earth_height = calculate_flat_earth_sun_height(
            user_lat=request.latitude,
            user_lon=request.longitude,
            device_altitude=request.device_altitude,
            dt=request.timestamp,
        )

        # Prepare measurement record
        measurement_data = {
            "device_id": request.device_id,
            "latitude": request.latitude,
            "longitude": request.longitude,
            "device_azimuth": request.device_azimuth,
            "device_altitude": request.device_altitude,
            "magnetic_azimuth": request.magnetic_azimuth,
            "magnetic_declination": request.magnetic_declination,
            "nasa_azimuth": sun_position["azimuth"],
            "nasa_altitude": sun_position["altitude"],
            "delta_azimuth": delta_azimuth,
            "delta_altitude": delta_altitude,
            "flat_earth_sun_height_km": flat_earth_height,
        }

        # Save to Supabase via REST API
        insert_response = (
            self.supabase.table("measurements").insert(measurement_data).execute()
        )

        if not insert_response.data:
            raise MeasurementSaveFailed("Failed to save measurement to database")

        return _row_to_response(insert_response.data[0])

    def get_measurements_by_date(
        self,
        target_date: date | None = None,
        limit: int = 5000,
    ) -> List[MeasurementResponse]:
        """
        Retrieve measurements for a specific date.

        Args:
            target_date: Date to filter by (defaults to today if None)
            limit: Maximum number of measurements to return

        Returns:
            List of measurements ordered by created_at descending
        """
        filter_date = target_date or date.today()

        # Calculate date range for the target day (start of day to end of day)
        start_of_day = f"{filter_date}T00:00:00Z"
        end_of_day = f"{filter_date}T23:59:59.999999Z"

        response = (
            self.supabase.table("measurements")
            .select("*")
            .gte("created_at", start_of_day)
            .lte("created_at", end_of_day)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        return [_row_to_response(row) for row in response.data]

    def get_stats_by_date(self, target_date: date | None = None) -> StatsResponse:
        """
        Calculate statistics for measurements on a specific date.

        Args:
            target_date: Date to calculate stats for (defaults to today)

        Returns:
            Statistics including count, averages, standard deviations,
            and flat Earth triangulation results
        """
        filter_date = target_date or date.today()

        start_of_day = f"{filter_date}T00:00:00Z"
        end_of_day = f"{filter_date}T23:59:59.999999Z"

        response = (
            self.supabase.table("measurements")
            .select("delta_azimuth, delta_altitude, flat_earth_sun_height_km")
            .gte("created_at", start_of_day)
            .lte("created_at", end_of_day)
            .execute()
        )

        rows = response.data
        count = len(rows)

        if count == 0:
            return StatsResponse(
                count=0,
                avg_delta_azimuth=None,
                avg_delta_altitude=None,
                std_dev_azimuth=None,
                std_dev_altitude=None,
                flat_earth_samples=None,
                avg_flat_earth_sun_height_km=None,
                std_dev_flat_earth_sun_height_km=None,
            )

        delta_azimuths = [row["delta_azimuth"] for row in rows]
        delta_altitudes = [row["delta_altitude"] for row in rows]

        avg_az = statistics.mean(delta_azimuths)
        avg_alt = statistics.mean(delta_altitudes)

        # Standard deviation requires at least 2 data points
        std_az = statistics.stdev(delta_azimuths) if count >= 2 else 0.0
        std_alt = statistics.stdev(delta_altitudes) if count >= 2 else 0.0

        # Flat Earth triangulation statistics
        # Filter out None values (measurements where altitude was too low)
        flat_earth_heights = [
            row["flat_earth_sun_height_km"]
            for row in rows
            if row.get("flat_earth_sun_height_km") is not None
        ]
        flat_earth_count = len(flat_earth_heights)

        avg_flat_earth = None
        std_flat_earth = None

        if flat_earth_count > 0:
            avg_flat_earth = round(statistics.mean(flat_earth_heights), 2)
            if flat_earth_count >= 2:
                std_flat_earth = round(statistics.stdev(flat_earth_heights), 2)
            else:
                std_flat_earth = 0.0

        return StatsResponse(
            count=count,
            avg_delta_azimuth=round(avg_az, 4),
            avg_delta_altitude=round(avg_alt, 4),
            std_dev_azimuth=round(std_az, 4),
            std_dev_altitude=round(std_alt, 4),
            flat_earth_samples=flat_earth_count if flat_earth_count > 0 else None,
            avg_flat_earth_sun_height_km=avg_flat_earth,
            std_dev_flat_earth_sun_height_km=std_flat_earth,
        )

    def export_csv_by_date(self, target_date: date | None = None) -> str:
        """
        Export measurements as CSV string.

        Args:
            target_date: Date to export (defaults to today)

        Returns:
            CSV formatted string of measurements
        """
        measurements = self.get_measurements_by_date(target_date=target_date, limit=10000)

        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow([
            "id",
            "created_at",
            "device_id",
            "latitude",
            "longitude",
            "device_azimuth",
            "device_altitude",
            "magnetic_azimuth",
            "magnetic_declination",
            "nasa_azimuth",
            "nasa_altitude",
            "delta_azimuth",
            "delta_altitude",
            "flat_earth_sun_height_km",
        ])

        # Data rows
        for m in measurements:
            writer.writerow([
                m.id,
                m.created_at,
                m.device_id or "",
                m.latitude,
                m.longitude,
                m.device_azimuth,
                m.device_altitude,
                m.magnetic_azimuth if m.magnetic_azimuth is not None else "",
                m.magnetic_declination if m.magnetic_declination is not None else "",
                m.nasa_azimuth,
                m.nasa_altitude,
                m.delta_azimuth,
                m.delta_altitude,
                m.flat_earth_sun_height_km if m.flat_earth_sun_height_km is not None else "",
            ])

        return output.getvalue()
