"""Google Health Connect workouts implementation."""

from datetime import datetime
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.event_record import EventRecordCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.services.providers.google_health.handlers.base import GoogleHealthSourceHandler
from app.services.providers.google_health.handlers.health_connect import HealthConnectHandler
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


class GoogleHealthWorkouts(BaseWorkoutsTemplate):
    """Google Health Connect implementation of the workouts template."""

    def __init__(
        self,
        workout_repo: EventRecordRepository,
        connection_repo: UserConnectionRepository,
    ):
        super().__init__(
            workout_repo,
            connection_repo,
            provider_name="google_health",
            api_base_url="",
            oauth=None,  # type: ignore[arg-type]
        )
        self.handlers: dict[str, GoogleHealthSourceHandler] = {
            "health_connect": HealthConnectHandler(),
        }

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[Any]:
        """Fetches workouts from Google Health Connect.

        Since Google Health Connect is primarily a local, push-based provider,
        this method might not be used for pulling data in the traditional sense.
        """
        return []

    def _normalize_workout(
        self,
        raw_workout: Any,
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Google Health payloads are normalized directly in handler classes."""
        raise NotImplementedError("Direct normalization not supported. Use process_payload.")

    def _extract_dates(self, start_timestamp: Any, end_timestamp: Any) -> tuple[datetime, datetime]:
        """Google Health Connect uses datetime objects directly."""
        if isinstance(start_timestamp, datetime) and isinstance(end_timestamp, datetime):
            return start_timestamp, end_timestamp
        raise ValueError("Google Health Connect expects datetime objects for timestamps")

    def get_workouts_from_api(self, db: DbSession, user_id: UUID, **kwargs: Any) -> Any:
        """Google Health Connect does not support cloud API - data is push-only."""
        return []

    def get_workout_detail_from_api(self, db: DbSession, user_id: UUID, workout_id: str, **kwargs: Any) -> Any:
        """Google Health Connect does not support cloud API - data is push-only."""
        raise NotImplementedError("Google Health Connect does not support API-based workout detail fetching")

    def load_data(self, db: DbSession, user_id: UUID, **kwargs: Any) -> bool:
        """Google Health Connect uses push-based data ingestion via process_payload."""
        raise NotImplementedError("Google Health Connect uses process_payload for data ingestion, not load_data")

    def process_payload(
        self,
        db: DbSession,
        user_id: UUID,
        payload: Any,
        source_type: str,
    ) -> None:
        """Processes data pushed from Google Health Connect sources.

        Args:
            db: Database session.
            user_id: User ID.
            payload: The raw data payload.
            source_type: The source of the data ('health_connect').
        """
        handler = self.handlers.get(source_type)
        if not handler:
            raise ValueError(f"Unknown Google Health Connect source: {source_type}")

        normalized_data = handler.normalize(payload)

        for record, detail in normalized_data:
            # Set user_id on the record object
            record.user_id = user_id
            self._save_workout(db, record, detail)
