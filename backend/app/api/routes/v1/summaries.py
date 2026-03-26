"""Summary endpoints that aggregate event_record data into daily summaries.

Returns flattened response format compatible with the Amina client:
- ActivitySummary: date, steps, active_calories, resting_heart_rate, distance_meters, etc.
- SleepSummary: date, total_duration_seconds, deep_sleep_seconds, sleep_score, etc.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import and_, func

from app.database import DbSession
from app.models import EventRecord, ExternalDeviceMapping
from app.models.workout_details import WorkoutDetails
from app.models.sleep_details import SleepDetails
from app.schemas.common_types import Pagination, TimeseriesMetadata
from app.services import ApiKeyDep
from pydantic import BaseModel

router = APIRouter()


class FlatPaginatedResponse(BaseModel):
    """Paginated response with flat data items (no nested source)."""
    data: list[dict[str, Any]]
    pagination: Pagination
    metadata: TimeseriesMetadata


@router.get("/users/{user_id}/summaries/activity")
async def get_activity_summary(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> FlatPaginatedResponse:
    """Returns daily aggregated activity metrics."""
    start_dt = _parse_date(start_date)
    end_dt = _parse_date(end_date)

    # Query daily + workout records for this user
    rows = (
        db.query(
            func.date(EventRecord.start_datetime).label("day"),
            ExternalDeviceMapping.provider_name,
            func.sum(WorkoutDetails.steps_count).label("steps"),
            func.sum(WorkoutDetails.energy_burned).label("calories"),
            func.sum(WorkoutDetails.distance).label("distance"),
            func.sum(EventRecord.duration_seconds).label("duration"),
            func.min(WorkoutDetails.heart_rate_avg).label("resting_hr"),
            func.max(WorkoutDetails.heart_rate_max).label("max_hr"),
            func.avg(WorkoutDetails.heart_rate_avg).label("avg_hr"),
            func.sum(WorkoutDetails.moving_time_seconds).label("active_time"),
        )
        .join(ExternalDeviceMapping, EventRecord.external_device_mapping_id == ExternalDeviceMapping.id)
        .outerjoin(WorkoutDetails, WorkoutDetails.record_id == EventRecord.id)
        .filter(
            and_(
                ExternalDeviceMapping.user_id == user_id,
                EventRecord.category.in_(["daily", "workout"]),
                EventRecord.start_datetime >= start_dt,
                EventRecord.start_datetime <= end_dt,
            ),
        )
        .group_by(func.date(EventRecord.start_datetime), ExternalDeviceMapping.provider_name)
        .order_by(func.date(EventRecord.start_datetime).desc())
        .limit(limit)
        .all()
    )

    summaries = []
    for row in rows:
        summaries.append({
            "date": str(row.day),
            "steps": int(row.steps) if row.steps else None,
            "active_calories": float(row.calories) if row.calories else None,
            "total_calories": None,
            "active_duration_seconds": int(row.active_time or row.duration or 0) or None,
            "distance_meters": float(row.distance) if row.distance else None,
            "floors_climbed": None,
            "avg_heart_rate": int(float(row.avg_hr)) if row.avg_hr else None,
            "max_heart_rate": int(row.max_hr) if row.max_hr else None,
            "resting_heart_rate": int(float(row.resting_hr)) if row.resting_hr else None,
            "provider": row.provider_name or "unknown",
        })

    return FlatPaginatedResponse(
        data=summaries,
        pagination=Pagination(next_cursor=None, has_more=False),
        metadata=TimeseriesMetadata(
            sample_count=len(summaries),
            start_time=start_dt,
            end_time=end_dt,
        ),
    )


@router.get("/users/{user_id}/summaries/sleep")
async def get_sleep_summary(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> FlatPaginatedResponse:
    """Returns daily sleep metrics."""
    start_dt = _parse_date(start_date)
    end_dt = _parse_date(end_date)

    rows = (
        db.query(
            EventRecord,
            SleepDetails,
            ExternalDeviceMapping.provider_name,
        )
        .join(ExternalDeviceMapping, EventRecord.external_device_mapping_id == ExternalDeviceMapping.id)
        .outerjoin(SleepDetails, SleepDetails.record_id == EventRecord.id)
        .filter(
            and_(
                ExternalDeviceMapping.user_id == user_id,
                EventRecord.category == "sleep",
                EventRecord.start_datetime >= start_dt,
                EventRecord.start_datetime <= end_dt,
            ),
        )
        .order_by(EventRecord.start_datetime.desc())
        .limit(limit)
        .all()
    )

    summaries = []
    for record, sleep_detail, provider_name in rows:
        duration_seconds = None
        deep = None
        light = None
        rem = None
        awake = None
        score = None

        if sleep_detail:
            duration_seconds = (sleep_detail.sleep_total_duration_minutes or 0) * 60
            deep = (sleep_detail.sleep_deep_minutes or 0) * 60 if sleep_detail.sleep_deep_minutes else None
            light = (sleep_detail.sleep_light_minutes or 0) * 60 if sleep_detail.sleep_light_minutes else None
            rem = (sleep_detail.sleep_rem_minutes or 0) * 60 if sleep_detail.sleep_rem_minutes else None
            awake = (sleep_detail.sleep_awake_minutes or 0) * 60 if sleep_detail.sleep_awake_minutes else None
            score = float(sleep_detail.sleep_efficiency_score) if sleep_detail.sleep_efficiency_score else None
        elif record.duration_seconds:
            duration_seconds = record.duration_seconds

        summaries.append({
            "date": str(record.start_datetime.date()),
            "total_duration_seconds": duration_seconds,
            "deep_sleep_seconds": deep,
            "light_sleep_seconds": light,
            "rem_sleep_seconds": rem,
            "awake_seconds": awake,
            "sleep_score": score,
            "provider": provider_name or "unknown",
        })

    return FlatPaginatedResponse(
        data=summaries,
        pagination=Pagination(next_cursor=None, has_more=False),
        metadata=TimeseriesMetadata(
            sample_count=len(summaries),
            start_time=start_dt,
            end_time=end_dt,
        ),
    )


@router.get("/users/{user_id}/summaries/recovery")
async def get_recovery_summary(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> FlatPaginatedResponse:
    """Returns daily recovery metrics."""
    return FlatPaginatedResponse(
        data=[],
        pagination=Pagination(next_cursor=None, has_more=False),
        metadata=TimeseriesMetadata(
            sample_count=0,
            start_time=_parse_date(start_date),
            end_time=_parse_date(end_date),
        ),
    )


@router.get("/users/{user_id}/summaries/body")
async def get_body_summary(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> FlatPaginatedResponse:
    """Returns daily body metrics."""
    return FlatPaginatedResponse(
        data=[],
        pagination=Pagination(next_cursor=None, has_more=False),
        metadata=TimeseriesMetadata(
            sample_count=0,
            start_time=_parse_date(start_date),
            end_time=_parse_date(end_date),
        ),
    )


def _parse_date(date_str: str) -> datetime:
    """Parse date string to datetime."""
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return datetime.strptime(date_str, "%Y-%m-%d")
