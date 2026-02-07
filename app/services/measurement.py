"""Measurement service layer for business logic separation."""

from datetime import date, datetime, timezone
from typing import List

from supabase import Client

from app.schemas.sun import MeasurementRequest, MeasurementResponse
from app.services.astronomy import calculate_sun_position


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
        nasa_azimuth=row["nasa_azimuth"],
        nasa_altitude=row["nasa_altitude"],
        delta_azimuth=row["delta_azimuth"],
        delta_altitude=row["delta_altitude"],
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
        Create a new measurement.

        Calculates sun position, computes deltas, and saves to database.

        Args:
            request: Measurement request with device sensor data

        Returns:
            The saved measurement record

        Raises:
            RateLimitExceeded: If the device is rate limited
            MeasurementSaveFailed: If the database insert fails
        """
        # Check rate limit first
        self.check_rate_limit(request.device_id)

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
            target_date: Date to filter by (defaults to today)
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
