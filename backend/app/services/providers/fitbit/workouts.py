from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database import DbSession
from app.schemas import EventRecordCreate, EventRecordDetailCreate, EventRecordMetrics
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


# Fitbit activity type ID → unified workout type mapping
FITBIT_WORKOUT_TYPES = {
    90009: "running",     # Run
    90013: "walking",     # Walk
    90001: "cycling",     # Bike
    90024: "swimming",    # Swim
    15000: "other",       # Sport
    52001: "hiking",      # Hiking
    15680: "yoga",        # Yoga
    15540: "strength",    # Weights
    90019: "elliptical",  # Elliptical
    15460: "rowing",      # Rowing
}


def get_unified_workout_type(fitbit_type_id: int | None, name: str = "") -> str:
    if fitbit_type_id and fitbit_type_id in FITBIT_WORKOUT_TYPES:
        return FITBIT_WORKOUT_TYPES[fitbit_type_id]
    name_lower = name.lower()
    if "run" in name_lower:
        return "running"
    if "walk" in name_lower:
        return "walking"
    if "bike" in name_lower or "cycl" in name_lower:
        return "cycling"
    if "swim" in name_lower:
        return "swimming"
    if "yoga" in name_lower:
        return "yoga"
    return "other"


class FitbitWorkouts(BaseWorkoutsTemplate):
    """Fitbit implementation of workouts template."""

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Get activities from Fitbit API."""
        # Fitbit uses date strings YYYY-MM-DD
        after_date = start_date.strftime("%Y-%m-%d")
        before_date = end_date.strftime("%Y-%m-%d")

        result = self._make_api_request(
            db,
            user_id,
            f"/1/user/-/activities/list.json?afterDate={after_date}&beforeDate={before_date}&sort=desc&limit=100&offset=0",
        )

        # Fitbit wraps activities in a container
        if isinstance(result, dict):
            return result.get("activities", [])
        return result

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Get activities from Fitbit API with options."""
        after_date = kwargs.get("after_date", "2020-01-01")
        return self._make_api_request(
            db,
            user_id,
            f"/1/user/-/activities/list.json?afterDate={after_date}&sort=desc&limit=100&offset=0",
        )

    def normalize_workout(
        self,
        raw: dict[str, Any],
        user_id: UUID,
        data_source_id: UUID | None = None,
    ) -> EventRecordCreate:
        """Convert Fitbit activity to unified EventRecord."""
        activity_type_id = raw.get("activityTypeId")
        activity_name = raw.get("activityName", "Workout")
        unified_type = get_unified_workout_type(activity_type_id, activity_name)

        start_time = raw.get("startTime")
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

        duration_ms = raw.get("activeDuration") or raw.get("duration", 0)
        duration_seconds = duration_ms // 1000 if duration_ms else 0
        distance_km = raw.get("distance", 0)
        calories = raw.get("calories", 0)
        avg_hr = raw.get("averageHeartRate")
        steps = raw.get("steps")
        elevation = raw.get("elevationGain")

        metrics = EventRecordMetrics(
            duration_seconds=duration_seconds,
            distance_meters=Decimal(str(distance_km * 1000)) if distance_km else None,
            calories=Decimal(str(calories)) if calories else None,
            avg_heart_rate=Decimal(str(avg_hr)) if avg_hr else None,
            elevation_gain_meters=Decimal(str(elevation)) if elevation else None,
        )

        detail = EventRecordDetailCreate(
            id=uuid4(),
            raw_data=raw,
            metrics=metrics,
        )

        return EventRecordCreate(
            id=uuid4(),
            user_id=user_id,
            data_source_id=data_source_id,
            provider=self.provider_name,
            provider_id=str(raw.get("logId", "")),
            event_type=unified_type,
            sport_type=activity_name,
            started_at=start_time,
            duration_seconds=duration_seconds,
            detail=detail,
        )
