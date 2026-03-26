"""Garmin webhook endpoints for receiving push/ping notifications."""

from datetime import datetime, timezone
from logging import getLogger
from typing import Annotated
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.database import DbSession
from app.integrations.redis_client import get_redis_client
from app.models import EventRecord
from app.models.workout_details import WorkoutDetails
from app.models.sleep_details import SleepDetails
from app.repositories import UserConnectionRepository
from app.repositories.external_mapping_repository import ExternalMappingRepository
from app.models import ExternalDeviceMapping

router = APIRouter()
logger = getLogger(__name__)

mapping_repo = ExternalMappingRepository(ExternalDeviceMapping)


def _ensure_mapping(db: DbSession, user_id: UUID, provider: str) -> ExternalDeviceMapping:
    """Get or create an external device mapping for the user+provider."""
    return mapping_repo.ensure_mapping(db, user_id, provider, None, None)


def _ts_to_dt(ts: int | None, offset_seconds: int = 0) -> datetime | None:
    """Convert Garmin epoch timestamp to datetime."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts + offset_seconds, tz=timezone.utc)


@router.post("/ping")
async def garmin_ping_notification(
    request: Request,
    db: DbSession,
    garmin_client_id: Annotated[str | None, Header(alias="garmin-client-id")] = None,
) -> dict:
    """
    Receive Garmin PING notifications.

    Garmin sends ping notifications when new data is available.
    The notification contains a callbackURL to fetch the actual data.
    """
    if not garmin_client_id:
        logger.warning("Received webhook without garmin-client-id header")
        raise HTTPException(status_code=401, detail="Missing garmin-client-id header")

    try:
        payload = await request.json()
        logger.info(f"Received Garmin ping notification with keys: {list(payload.keys())}")

        processed_count = 0
        errors: list[str] = []
        repo = UserConnectionRepository()

        # Process each data type that has callback URLs
        for data_type in ["activities", "activityDetails", "dailies", "sleeps", "epochs"]:
            if data_type not in payload:
                continue

            for item in payload[data_type]:
                try:
                    garmin_user_id = item.get("userId")
                    callback_url = item.get("callbackURL")

                    if not callback_url:
                        continue

                    connection = repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
                    if not connection:
                        logger.warning(f"No connection for Garmin user {garmin_user_id}")
                        errors.append(f"User {garmin_user_id} not connected")
                        continue

                    # Save pull token to Redis
                    parsed_url = urlparse(callback_url)
                    query_params = parse_qs(parsed_url.query)
                    pull_token = query_params.get("token", [None])[0]

                    if pull_token:
                        redis_client = get_redis_client()
                        token_key = f"garmin_pull_token:{connection.user_id}:{data_type}"
                        redis_client.setex(token_key, 3600, pull_token)

                    # Fetch data from callback URL
                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.get(callback_url, timeout=30.0)
                            response.raise_for_status()
                            data = response.json()

                        if isinstance(data, list):
                            for record in data:
                                _store_garmin_record(db, connection.user_id, data_type, record)
                            processed_count += len(data)
                        elif isinstance(data, dict):
                            _store_garmin_record(db, connection.user_id, data_type, data)
                            processed_count += 1

                        logger.info(f"Processed {data_type} callback for user {connection.user_id}")

                    except httpx.HTTPError as e:
                        logger.error(f"Failed to fetch {data_type} from callback: {e}")
                        errors.append(f"HTTP error fetching {data_type}: {str(e)}")

                except Exception as e:
                    logger.error(f"Error processing {data_type} notification: {e}")
                    errors.append(str(e))

        return {"processed": processed_count, "errors": errors}

    except Exception as e:
        logger.error(f"Error processing Garmin ping webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@router.post("/push")
async def garmin_push_notification(
    request: Request,
    db: DbSession,
    garmin_client_id: Annotated[str | None, Header(alias="garmin-client-id")] = None,
) -> dict:
    """
    Receive Garmin PUSH notifications with inline data.

    Push notifications contain the actual data inline (dailies, sleeps, activities, etc.).
    """
    if not garmin_client_id:
        logger.warning("Received webhook without garmin-client-id header")
        raise HTTPException(status_code=401, detail="Missing garmin-client-id header")

    try:
        payload = await request.json()
        logger.info(f"Received Garmin push notification with keys: {list(payload.keys())}")

        processed_count = 0
        errors: list[str] = []
        repo = UserConnectionRepository()

        # Process each data type
        for data_type in ["activities", "dailies", "sleeps", "epochs", "bodyComps",
                          "stressDetails", "userMetrics", "moveIQActivities",
                          "pulseOx", "respiration", "activityDetails"]:
            if data_type not in payload:
                continue

            for item in payload[data_type]:
                try:
                    garmin_user_id = str(item.get("userId", ""))
                    if not garmin_user_id:
                        continue

                    connection = repo.get_by_provider_user_id(db, "garmin", garmin_user_id)
                    if not connection:
                        logger.warning(f"No connection for Garmin user {garmin_user_id}")
                        errors.append(f"User {garmin_user_id} not connected")
                        continue

                    _store_garmin_record(db, connection.user_id, data_type, item)
                    processed_count += 1

                except Exception as e:
                    logger.error(f"Error processing {data_type} push: {e}")
                    errors.append(str(e))

        return {"processed": processed_count, "errors": errors}

    except Exception as e:
        logger.error(f"Error processing Garmin push webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")


def _store_garmin_record(db: DbSession, user_id: UUID, data_type: str, data: dict) -> None:
    """Parse and store a Garmin data record into event_record + details."""
    try:
        mapping = _ensure_mapping(db, user_id, "garmin")

        if data_type == "dailies":
            _store_daily(db, user_id, mapping.id, data)
        elif data_type == "sleeps":
            _store_sleep(db, user_id, mapping.id, data)
        elif data_type in ("activities", "activityDetails"):
            _store_activity(db, user_id, mapping.id, data)
        else:
            logger.debug(f"Skipping unsupported data type: {data_type}")

    except Exception as e:
        logger.error(f"Failed to store Garmin {data_type} record: {e}")
        db.rollback()


def _store_daily(db: DbSession, user_id: UUID, mapping_id: UUID, data: dict) -> None:
    """Store a Garmin daily summary as an event_record with workout details."""
    start_ts = data.get("startTimeInSeconds")
    offset = data.get("startTimeOffsetInSeconds", 0)
    duration = data.get("durationInSeconds", 86400)

    if not start_ts:
        return

    start_dt = _ts_to_dt(start_ts, offset)
    end_dt = _ts_to_dt(start_ts + duration, offset)

    # Check for existing record (dedup)
    external_id = f"daily_{start_ts}"
    existing = db.query(EventRecord).filter(
        EventRecord.external_device_mapping_id == mapping_id,
        EventRecord.external_id == external_id,
    ).first()

    if existing:
        return  # Already stored

    record_id = uuid4()
    record = EventRecord(
        id=record_id,
        external_id=external_id,
        external_device_mapping_id=mapping_id,
        category="daily",
        type="daily_summary",
        source_name="garmin",
        duration_seconds=duration,
        start_datetime=start_dt,
        end_datetime=end_dt,
    )
    db.add(record)

    # Store metrics in workout_details
    detail = WorkoutDetails(
        record_id=record_id,
        detail_type="workout",
        steps_count=data.get("steps"),
        energy_burned=data.get("activeKilocalories"),
        distance=data.get("distanceInMeters"),
        heart_rate_avg=data.get("averageHeartRateInBeatsPerMinute"),
        heart_rate_min=data.get("minHeartRateInBeatsPerMinute"),
        heart_rate_max=data.get("maxHeartRateInBeatsPerMinute"),
        moving_time_seconds=data.get("activeTimeInSeconds"),
    )
    db.add(detail)
    db.commit()
    logger.info(f"Stored daily summary for user {user_id}: {data.get('steps')} steps")


def _store_sleep(db: DbSession, user_id: UUID, mapping_id: UUID, data: dict) -> None:
    """Store a Garmin sleep record."""
    start_ts = data.get("startTimeInSeconds")
    offset = data.get("startTimeOffsetInSeconds", 0)
    duration = data.get("durationInSeconds")

    if not start_ts:
        return

    start_dt = _ts_to_dt(start_ts, offset)
    end_dt = _ts_to_dt(start_ts + (duration or 0), offset)

    external_id = f"sleep_{start_ts}"
    existing = db.query(EventRecord).filter(
        EventRecord.external_device_mapping_id == mapping_id,
        EventRecord.external_id == external_id,
    ).first()

    if existing:
        return

    record_id = uuid4()
    record = EventRecord(
        id=record_id,
        external_id=external_id,
        external_device_mapping_id=mapping_id,
        category="sleep",
        type="sleep",
        source_name="garmin",
        duration_seconds=duration,
        start_datetime=start_dt,
        end_datetime=end_dt,
    )
    db.add(record)

    # Sleep level breakdown
    levels = data.get("sleepLevelsMap", {})
    deep_seconds = sum(e.get("endTimeInSeconds", 0) - e.get("startTimeInSeconds", 0) for e in levels.get("deep", []))
    light_seconds = sum(e.get("endTimeInSeconds", 0) - e.get("startTimeInSeconds", 0) for e in levels.get("light", []))
    rem_seconds = sum(e.get("endTimeInSeconds", 0) - e.get("startTimeInSeconds", 0) for e in levels.get("rem", []))
    awake_seconds = sum(e.get("endTimeInSeconds", 0) - e.get("startTimeInSeconds", 0) for e in levels.get("awake", []))

    detail = SleepDetails(
        record_id=record_id,
        detail_type="sleep",
        sleep_total_duration_minutes=(duration or 0) // 60,
        sleep_deep_minutes=deep_seconds // 60 if deep_seconds else None,
        sleep_light_minutes=light_seconds // 60 if light_seconds else None,
        sleep_rem_minutes=rem_seconds // 60 if rem_seconds else None,
        sleep_awake_minutes=awake_seconds // 60 if awake_seconds else None,
        sleep_efficiency_score=data.get("overallSleepScore", {}).get("value") if isinstance(data.get("overallSleepScore"), dict) else data.get("overallSleepScore"),
    )
    db.add(detail)
    db.commit()
    logger.info(f"Stored sleep for user {user_id}: {(duration or 0) // 60} min")


def _store_activity(db: DbSession, user_id: UUID, mapping_id: UUID, data: dict) -> None:
    """Store a Garmin activity."""
    start_ts = data.get("startTimeInSeconds")
    offset = data.get("startTimeOffsetInSeconds", 0)
    duration = data.get("durationInSeconds") or data.get("elapsedDurationInSeconds")
    activity_id = data.get("activityId") or data.get("summaryId")

    if not start_ts:
        return

    start_dt = _ts_to_dt(start_ts, offset)
    end_dt = _ts_to_dt(start_ts + (duration or 0), offset)

    external_id = f"activity_{activity_id}" if activity_id else f"activity_{start_ts}"
    existing = db.query(EventRecord).filter(
        EventRecord.external_device_mapping_id == mapping_id,
        EventRecord.external_id == external_id,
    ).first()

    if existing:
        return

    record_id = uuid4()
    activity_type = data.get("activityType", "unknown")
    activity_name = data.get("activityName", activity_type)

    record = EventRecord(
        id=record_id,
        external_id=external_id,
        external_device_mapping_id=mapping_id,
        category="workout",
        type=activity_type,
        source_name="garmin",
        duration_seconds=duration,
        start_datetime=start_dt,
        end_datetime=end_dt,
    )
    db.add(record)

    detail = WorkoutDetails(
        record_id=record_id,
        detail_type="workout",
        steps_count=data.get("steps"),
        energy_burned=data.get("activeKilocalories") or data.get("calories"),
        distance=data.get("distanceInMeters"),
        heart_rate_avg=data.get("averageHeartRateInBeatsPerMinute"),
        heart_rate_max=data.get("maxHeartRateInBeatsPerMinute"),
        moving_time_seconds=data.get("movingDurationInSeconds"),
        total_elevation_gain=data.get("elevationGainInMeters"),
        average_speed=data.get("averageSpeedInMetersPerSecond"),
        max_speed=data.get("maxSpeedInMetersPerSecond"),
    )
    db.add(detail)
    db.commit()
    logger.info(f"Stored activity {activity_name} ({activity_type}) for user {user_id}")


@router.get("/health")
async def garmin_webhook_health() -> dict:
    """Health check endpoint for Garmin webhook configuration."""
    return {"status": "ok", "service": "garmin-webhooks"}
