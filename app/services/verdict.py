"""Verdict Engine service layer for Earth model analysis."""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from supabase import Client

from app.schemas.verdict import VerdictResponse


# Constants
OUTLIER_THRESHOLD = 20.0  # degrees - ignore measurements with |delta| > this
NASA_THRESHOLD = 85  # confidence score above this = NASA wins
ANALYSIS_WINDOW_HOURS = 24


def _row_to_response(row: dict) -> VerdictResponse:
    """Convert a database row to a VerdictResponse."""
    return VerdictResponse(
        id=row["id"],
        created_at=row["created_at"],
        total_samples=row["total_samples"],
        valid_samples=row["valid_samples"],
        avg_error_azimuth=row["avg_error_azimuth"],
        avg_error_altitude=row["avg_error_altitude"],
        confidence_score=row["confidence_score"],
        winning_model=row["winning_model"],
    )


class VerdictService:
    """
    Service layer for verdict operations.

    Analyzes crowdsourced measurement data to determine if device sensors
    match NASA/Pysolar calculations (Earth model validation).
    """

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def calculate_score(self, measurements: List[dict]) -> dict:
        """
        Calculate verdict score from measurements.

        Algorithm:
        1. Filter outliers (|delta| > 20°) - assumed user error
        2. Calculate mean absolute error for azimuth and altitude
        3. Score = 100 - (avg_az + avg_alt), clamped 0-100
        4. Winner: score > 85 => NASA, else ANOMALY

        Args:
            measurements: List of measurement dicts with delta_azimuth, delta_altitude

        Returns:
            Dict with verdict calculation results
        """
        total_samples = len(measurements)

        if total_samples == 0:
            return {
                "total_samples": 0,
                "valid_samples": 0,
                "avg_error_azimuth": 0.0,
                "avg_error_altitude": 0.0,
                "confidence_score": 0.0,
                "winning_model": "ANOMALY",
            }

        # Filter outliers (|delta| > 20 degrees = user error)
        valid = [
            m for m in measurements
            if abs(m["delta_azimuth"]) <= OUTLIER_THRESHOLD
            and abs(m["delta_altitude"]) <= OUTLIER_THRESHOLD
        ]
        valid_samples = len(valid)

        if valid_samples == 0:
            return {
                "total_samples": total_samples,
                "valid_samples": 0,
                "avg_error_azimuth": 0.0,
                "avg_error_altitude": 0.0,
                "confidence_score": 0.0,
                "winning_model": "ANOMALY",
            }

        # Calculate mean absolute error
        avg_error_az = sum(abs(m["delta_azimuth"]) for m in valid) / valid_samples
        avg_error_alt = sum(abs(m["delta_altitude"]) for m in valid) / valid_samples

        # Score: 100 - total error, clamped 0-100
        raw_score = 100 - (avg_error_az + avg_error_alt)
        confidence_score = max(0.0, min(100.0, raw_score))

        # Determine winner
        winning_model = "NASA" if confidence_score > NASA_THRESHOLD else "ANOMALY"

        return {
            "total_samples": total_samples,
            "valid_samples": valid_samples,
            "avg_error_azimuth": round(avg_error_az, 4),
            "avg_error_altitude": round(avg_error_alt, 4),
            "confidence_score": round(confidence_score, 2),
            "winning_model": winning_model,
        }

    def trigger_calculation(self, target_date: Optional[date] = None) -> VerdictResponse:
        """
        Trigger verdict calculation for a specific date or last 24 hours.

        Args:
            target_date: If provided, analyze measurements for this specific date.
                         If None, analyze last 24 hours from now.

        Returns:
            The newly created or updated verdict
        """
        if target_date is not None:
            # Specific date: full day range
            start_of_day = f"{target_date}T00:00:00Z"
            end_of_day = f"{target_date}T23:59:59.999999Z"

            response = (
                self.supabase.table("measurements")
                .select("delta_azimuth, delta_altitude")
                .gte("created_at", start_of_day)
                .lte("created_at", end_of_day)
                .execute()
            )
        else:
            # Default: last 24 hours
            cutoff = datetime.now(timezone.utc) - timedelta(hours=ANALYSIS_WINDOW_HOURS)
            cutoff_iso = cutoff.isoformat()

            response = (
                self.supabase.table("measurements")
                .select("delta_azimuth, delta_altitude")
                .gte("created_at", cutoff_iso)
                .execute()
            )

        measurements = response.data or []

        # Calculate score
        result = self.calculate_score(measurements)

        # Determine the date for this verdict (for idempotency check)
        verdict_date = target_date or date.today()

        # Idempotency: check if verdict already exists for this date
        existing = self._get_verdict_for_date(verdict_date)

        # Prepare verdict record
        verdict_data = {
            "total_samples": result["total_samples"],
            "valid_samples": result["valid_samples"],
            "avg_error_azimuth": result["avg_error_azimuth"],
            "avg_error_altitude": result["avg_error_altitude"],
            "confidence_score": result["confidence_score"],
            "winning_model": result["winning_model"],
        }

        if existing is not None:
            # Update existing verdict (delete + insert for simplicity with Supabase)
            self.supabase.table("verdicts").delete().eq("id", existing.id).execute()

        # Insert new verdict
        insert_response = (
            self.supabase.table("verdicts").insert(verdict_data).execute()
        )

        if not insert_response.data:
            raise RuntimeError("Failed to save verdict to database")

        return _row_to_response(insert_response.data[0])

    def _get_verdict_for_date(self, target_date: date) -> Optional[VerdictResponse]:
        """
        Get verdict for a specific calendar date.

        Args:
            target_date: The date to query

        Returns:
            Verdict for that date, or None if not found
        """
        start_of_day = f"{target_date}T00:00:00Z"
        end_of_day = f"{target_date}T23:59:59.999999Z"

        response = (
            self.supabase.table("verdicts")
            .select("*")
            .gte("created_at", start_of_day)
            .lte("created_at", end_of_day)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not response.data:
            return None

        return _row_to_response(response.data[0])

    def get_latest(self, target_date: Optional[date] = None) -> Optional[VerdictResponse]:
        """
        Get the most recent verdict, optionally filtered by date.

        Args:
            target_date: If provided, get verdict for this specific date.
                         If None, get the most recent verdict overall.

        Returns:
            The verdict, or None if not found
        """
        if target_date is not None:
            return self._get_verdict_for_date(target_date)

        # Default: get latest overall
        response = (
            self.supabase.table("verdicts")
            .select("*")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not response.data:
            return None

        return _row_to_response(response.data[0])
