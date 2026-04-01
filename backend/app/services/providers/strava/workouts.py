from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database import DbSession
from app.schemas import EventRecordCreate, EventRecordDetailCreate, EventRecordMetrics
from app.services.event_record_service import event_record_service
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


# Strava sport type → unified workout type mapping
STRAVA_WORKOUT_TYPES = {
    "Run": "running",
    "TrailRun": "running",
    "Ride": "cycling",
    "VirtualRide": "cycling",
    "Swim": "swimming",
    "Walk": "walking",
    "Hike": "hiking",
    "Yoga": "yoga",
    "WeightTraining": "strength",
    "Workout": "other",
    "CrossFit": "strength",
    "Elliptical": "cardio",
    "Rowing": "rowing",
    "StandUpPaddling": "other",
    "Surfing": "other",
    "Snowboard": "snowboarding",
    "AlpineSki": "skiing",
    "NordicSki": "skiing",
    "IceSkate": "skating",
    "RockClimbing": "climbing",
}


def get_unified_workout_type(strava_type: str) -> str:
    return STRAVA_WORKOUT_TYPES.get(strava_type, "other")


class StravaWorkouts(BaseWorkoutsTemplate):
    """Strava implementation of workouts template."""

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Get activities from Strava API."""
        params = {
            "after": int(start_date.timestamp()),
            "before": int(end_date.timestamp()),
            "per_page": 100,
        }

        return self._make_api_request(
            db,
            user_id,
            "/api/v3/athlete/activities",
            params=params,
        )

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Get activities from Strava API with options."""
        after = kwargs.get("after")
        before = kwargs.get("before")

        params: dict[str, Any] = {"per_page": 100}
        if after:
            params["after"] = int(datetime.fromisoformat(str(after)).timestamp()) if isinstance(after, str) else int(after)
        if before:
            params["before"] = int(datetime.fromisoformat(str(before)).timestamp()) if isinstance(before, str) else int(before)

        return self._make_api_request(db, user_id, "/api/v3/athlete/activities", params=params)

    def normalize_workout(
        self,
        raw: dict[str, Any],
        user_id: UUID,
        data_source_id: UUID | None = None,
    ) -> EventRecordCreate:
        """Convert Strava activity to unified EventRecord."""
        sport_type = raw.get("sport_type") or raw.get("type", "Workout")
        unified_type = get_unified_workout_type(sport_type)

        start_time = raw.get("start_date")
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

        duration_seconds = raw.get("elapsed_time") or raw.get("moving_time", 0)
        distance_meters = raw.get("distance", 0)
        calories = raw.get("calories", 0)
        avg_hr = raw.get("average_heartrate")
        max_hr = raw.get("max_heartrate")
        avg_speed = raw.get("average_speed")  # m/s

        metrics = EventRecordMetrics(
            duration_seconds=duration_seconds,
            distance_meters=Decimal(str(distance_meters)) if distance_meters else None,
            calories=Decimal(str(calories)) if calories else None,
            avg_heart_rate=Decimal(str(avg_hr)) if avg_hr else None,
            max_heart_rate=Decimal(str(max_hr)) if max_hr else None,
            avg_speed_kmh=Decimal(str(avg_speed * 3.6)) if avg_speed else None,
            elevation_gain_meters=Decimal(str(raw.get("total_elevation_gain", 0))) if raw.get("total_elevation_gain") else None,
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
            provider_id=str(raw.get("id", "")),
            event_type=unified_type,
            sport_type=sport_type,
            started_at=start_time,
            duration_seconds=duration_seconds,
            detail=detail,
        )
