"""Health Connect JSON export handler for Google Health data."""

from datetime import datetime
from decimal import Decimal
from logging import getLogger
from typing import Any
from uuid import uuid4

from app.constants.workout_types.google_health import get_unified_workout_type_by_id
from app.schemas.event_record import EventRecordCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.services.providers.google_health.handlers.base import GoogleHealthSourceHandler

logger = getLogger(__name__)


class HealthConnectHandler(GoogleHealthSourceHandler):
    """Handler for Google Health Connect JSON export data.

    Parses Health Connect ExerciseSessionRecord data and normalizes workout data
    to the unified event record schema.
    """

    def normalize(self, data: Any) -> list[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        """
        Parse Health Connect JSON export and normalize to unified schema.

        Args:
            data: Either a single exercise session dict or list of exercise sessions

        Returns:
            List of tuples containing (EventRecordCreate, EventRecordDetailCreate)
        """
        # Handle both single record and list of records
        if isinstance(data, dict):
            sessions = [data]
        elif isinstance(data, list):
            sessions = data
        else:
            raise ValueError(f"Unsupported data type for Health Connect parsing: {type(data)}")

        workouts = []

        for session in sessions:
            try:
                record, detail = self._parse_exercise_session(session)
                workouts.append((record, detail))
            except Exception as e:
                # Log error but continue processing other sessions
                session_id = session.get("id", "unknown")
                logger.error(f"Error parsing Health Connect session {session_id}: {e}", exc_info=True)
                continue

        return workouts

    def _parse_exercise_session(self, session: dict[str, Any]) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Parse a single ExerciseSessionRecord into normalized records."""

        # Extract basic session attributes
        exercise_type = session.get("exerciseType", 0)

        # Parse timestamps (ISO 8601 format)
        start_time = self._parse_datetime(session.get("startTime", ""))
        end_time = self._parse_datetime(session.get("endTime", ""))

        # Calculate duration
        duration_seconds = int((end_time - start_time).total_seconds())

        # Extract metadata
        metadata = session.get("metadata", {})
        source_name = metadata.get("dataOrigin", "Google Health Connect")
        device_name = metadata.get("device")

        # Extract associated data records
        distance_meters = self._extract_distance(session)
        calories = self._extract_calories(session)
        heart_rate_data = self._extract_heart_rate(session)
        elevation_data = self._extract_elevation(session)

        # Build metrics
        metrics = self._build_metrics(
            heart_rate_data=heart_rate_data,
            distance_meters=distance_meters,
            calories=calories,
            elevation_data=elevation_data,
        )

        # Create unified workout record
        workout_id = uuid4()
        unified_type = get_unified_workout_type_by_id(exercise_type)

        record = EventRecordCreate(
            id=workout_id,
            category="workout",
            type=unified_type.value,
            source_name=source_name,
            device_id=device_name or None,
            duration_seconds=duration_seconds,
            start_datetime=start_time,
            end_datetime=end_time,
            provider_id=session.get("id"),  # Health Connect may provide IDs
            user_id=None,  # Will be set by the caller
        )

        detail = EventRecordDetailCreate(
            record_id=workout_id,
            **metrics,
        )

        return record, detail

    def _parse_datetime(self, date_str: str) -> datetime:
        """Parse Health Connect datetime string to datetime object.

        Health Connect format: ISO 8601 (e.g., "2024-01-15T08:30:00Z")
        """
        if not date_str:
            return datetime.now()

        try:
            # Try ISO format with Z
            if date_str.endswith("Z"):
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            # Try standard ISO format
            return datetime.fromisoformat(date_str)
        except ValueError:
            # Fallback to current time if parsing fails
            return datetime.now()

    def _extract_distance(self, session: dict[str, Any]) -> Decimal | None:
        """Extract total distance from session data.

        Health Connect stores distance in DistanceRecord associated with the session.
        """
        # Check for distance in session metadata or associated records
        distance_records = session.get("distanceRecords", [])
        if not distance_records:
            return None

        # Sum up all distance records (in meters)
        total_distance = Decimal("0")
        for record in distance_records:
            distance = record.get("distance", {}).get("inMeters", 0)
            total_distance += Decimal(str(distance))

        return total_distance if total_distance > 0 else None

    def _extract_calories(self, session: dict[str, Any]) -> Decimal | None:
        """Extract total calories from session data.

        Health Connect stores calories in TotalCaloriesBurnedRecord.
        """
        calories_records = session.get("caloriesRecords", [])
        if not calories_records:
            return None

        # Sum up all calorie records (in kilocalories)
        total_calories = Decimal("0")
        for record in calories_records:
            energy = record.get("energy", {}).get("inKilocalories", 0)
            total_calories += Decimal(str(energy))

        return total_calories if total_calories > 0 else None

    def _extract_heart_rate(self, session: dict[str, Any]) -> dict[str, Decimal]:
        """Extract heart rate statistics from session data.

        Health Connect stores heart rate in HeartRateRecord.
        """
        hr_records = session.get("heartRateRecords", [])
        if not hr_records:
            return {}

        # Calculate min, max, avg from all heart rate samples
        all_bpm = []
        for record in hr_records:
            samples = record.get("samples", [])
            for sample in samples:
                bpm = sample.get("beatsPerMinute", 0)
                if bpm > 0:
                    all_bpm.append(bpm)

        if not all_bpm:
            return {}

        return {
            "min": Decimal(str(min(all_bpm))),
            "max": Decimal(str(max(all_bpm))),
            "avg": Decimal(str(sum(all_bpm) / len(all_bpm))),
        }

    def _extract_elevation(self, session: dict[str, Any]) -> dict[str, Decimal]:
        """Extract elevation gain/loss from session data.

        Health Connect stores elevation in ElevationGainedRecord.
        """
        elevation_records = session.get("elevationRecords", [])
        if not elevation_records:
            return {}

        total_gain = Decimal("0")
        for record in elevation_records:
            elevation = record.get("elevation", {}).get("inMeters", 0)
            if elevation > 0:
                total_gain += Decimal(str(elevation))

        return {"gain": total_gain} if total_gain > 0 else {}

    def _build_metrics(
        self,
        heart_rate_data: dict[str, Decimal],
        distance_meters: Decimal | None,
        calories: Decimal | None,
        elevation_data: dict[str, Decimal],
    ) -> dict[str, Any]:
        """Build metrics dictionary from session data."""
        metrics: dict[str, Any] = {}

        # Heart rate metrics
        if "avg" in heart_rate_data:
            metrics["heart_rate_avg"] = heart_rate_data["avg"]
        if "max" in heart_rate_data:
            metrics["heart_rate_max"] = heart_rate_data["max"]
        if "min" in heart_rate_data:
            metrics["heart_rate_min"] = heart_rate_data["min"]

        # Distance
        if distance_meters is not None:
            metrics["distance_total"] = distance_meters

        # Calories
        if calories is not None:
            metrics["calories_total"] = calories

        # Elevation
        if "gain" in elevation_data:
            metrics["elevation_gain"] = elevation_data["gain"]

        return metrics
