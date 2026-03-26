"""Summary endpoints that aggregate event_record data into daily summaries.

Uses raw SQL to query production DB schema (data_source FK, not external_device_mapping).
Returns flat response format compatible with the Amina client.
"""

from datetime import datetime
from logging import getLogger
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.database import DbSession
from app.schemas.common_types import Pagination, TimeseriesMetadata
from app.services import ApiKeyDep
from pydantic import BaseModel

router = APIRouter()
logger = getLogger(__name__)


class FlatPaginatedResponse(BaseModel):
    """Paginated response with flat data items."""
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

    summaries: list[dict[str, Any]] = []

    try:
        rows = db.execute(
            text("""
                SELECT
                    DATE(er.start_datetime) as day,
                    ds.provider,
                    SUM(wd.steps_count) as steps,
                    SUM(wd.energy_burned) as calories,
                    SUM(wd.distance) as distance,
                    SUM(er.duration_seconds) as duration,
                    MIN(wd.heart_rate_avg) as resting_hr,
                    MAX(wd.heart_rate_max) as max_hr,
                    AVG(wd.heart_rate_avg) as avg_hr,
                    SUM(wd.moving_time_seconds) as active_time
                FROM event_record er
                JOIN data_source ds ON er.data_source_id = ds.id
                LEFT JOIN workout_details wd ON wd.record_id = er.id
                WHERE ds.user_id = :uid
                  AND er.category IN ('daily', 'workout')
                  AND er.start_datetime >= :start
                  AND er.start_datetime <= :end
                GROUP BY DATE(er.start_datetime), ds.provider
                ORDER BY DATE(er.start_datetime) DESC
                LIMIT :lim
            """),
            {"uid": str(user_id), "start": start_dt, "end": end_dt, "lim": limit},
        ).fetchall()

        for row in rows:
            summaries.append({
                "date": str(row[0]),
                "steps": int(row[2]) if row[2] else None,
                "active_calories": float(row[3]) if row[3] else None,
                "total_calories": None,
                "active_duration_seconds": int(row[9] or row[5] or 0) or None,
                "distance_meters": float(row[4]) if row[4] else None,
                "floors_climbed": None,
                "avg_heart_rate": int(float(row[8])) if row[8] else None,
                "max_heart_rate": int(row[7]) if row[7] else None,
                "resting_heart_rate": int(float(row[6])) if row[6] else None,
                "provider": row[1] or "unknown",
            })
    except Exception as e:
        logger.warning(f"Activity summary query failed: {e}")
        db.rollback()

    return FlatPaginatedResponse(
        data=summaries,
        pagination=Pagination(next_cursor=None, has_more=False),
        metadata=TimeseriesMetadata(sample_count=len(summaries), start_time=start_dt, end_time=end_dt),
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

    summaries: list[dict[str, Any]] = []

    try:
        rows = db.execute(
            text("""
                SELECT
                    DATE(er.start_datetime) as day,
                    ds.provider,
                    sd.sleep_total_duration_minutes,
                    sd.sleep_deep_minutes,
                    sd.sleep_light_minutes,
                    sd.sleep_rem_minutes,
                    sd.sleep_awake_minutes,
                    sd.sleep_efficiency_score,
                    er.duration_seconds
                FROM event_record er
                JOIN data_source ds ON er.data_source_id = ds.id
                LEFT JOIN sleep_details sd ON sd.record_id = er.id
                WHERE ds.user_id = :uid
                  AND er.category = 'sleep'
                  AND er.start_datetime >= :start
                  AND er.start_datetime <= :end
                ORDER BY er.start_datetime DESC
                LIMIT :lim
            """),
            {"uid": str(user_id), "start": start_dt, "end": end_dt, "lim": limit},
        ).fetchall()

        for row in rows:
            duration_s = (row[2] or 0) * 60 if row[2] else (row[8] or None)
            summaries.append({
                "date": str(row[0]),
                "total_duration_seconds": duration_s,
                "deep_sleep_seconds": row[3] * 60 if row[3] else None,
                "light_sleep_seconds": row[4] * 60 if row[4] else None,
                "rem_sleep_seconds": row[5] * 60 if row[5] else None,
                "awake_seconds": row[6] * 60 if row[6] else None,
                "sleep_score": float(row[7]) if row[7] else None,
                "provider": row[1] or "unknown",
            })
    except Exception as e:
        logger.warning(f"Sleep summary query failed: {e}")
        db.rollback()

    return FlatPaginatedResponse(
        data=summaries,
        pagination=Pagination(next_cursor=None, has_more=False),
        metadata=TimeseriesMetadata(sample_count=len(summaries), start_time=start_dt, end_time=end_dt),
    )


@router.get("/users/{user_id}/summaries/recovery")
async def get_recovery_summary(
    user_id: UUID, start_date: str, end_date: str, db: DbSession, _api_key: ApiKeyDep,
    cursor: str | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> FlatPaginatedResponse:
    return _empty_response(start_date, end_date)


@router.get("/users/{user_id}/summaries/body")
async def get_body_summary(
    user_id: UUID, start_date: str, end_date: str, db: DbSession, _api_key: ApiKeyDep,
    cursor: str | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> FlatPaginatedResponse:
    return _empty_response(start_date, end_date)


def _empty_response(start_date: str, end_date: str) -> FlatPaginatedResponse:
    return FlatPaginatedResponse(
        data=[],
        pagination=Pagination(next_cursor=None, has_more=False),
        metadata=TimeseriesMetadata(sample_count=0, start_time=_parse_date(start_date), end_time=_parse_date(end_date)),
    )


def _parse_date(date_str: str) -> datetime:
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return datetime.strptime(date_str, "%Y-%m-%d")
