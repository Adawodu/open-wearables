"""Garmin webhook endpoints for receiving push/ping notifications."""

from datetime import datetime, timezone
from logging import getLogger
from typing import Annotated
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import text

from app.database import DbSession
from app.integrations.redis_client import get_redis_client
from app.repositories import UserConnectionRepository

router = APIRouter()
logger = getLogger(__name__)


def _ts_to_dt(ts: int | None, offset_seconds: int = 0) -> datetime | None:
    """Convert Garmin epoch timestamp to datetime."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts + offset_seconds, tz=timezone.utc)


def _ensure_data_source(db: DbSession, user_id: UUID, provider: str, connection_id: UUID | None = None) -> UUID:
    """Get or create a data_source record for the user+provider."""
    row = db.execute(
        text("SELECT id FROM data_source WHERE user_id = :uid AND provider = :prov LIMIT 1"),
        {"uid": str(user_id), "prov": provider},
    ).fetchone()

    if row:
        return row[0]

    ds_id = uuid4()
    db.execute(
        text("""INSERT INTO data_source (id, user_id, provider, source, device_model, original_source_name)
                VALUES (:id, :uid, :prov, :prov, 'webhook', :prov)"""),
        {"id": str(ds_id), "uid": str(user_id), "prov": provider},
    )
    db.commit()
    return ds_id


@router.post("/ping")
async def garmin_ping_notification(
    request: Request,
    db: DbSession,
    garmin_client_id: Annotated[str | None, Header(alias="garmin-client-id")] = None,
) -> dict:
    """Receive Garmin PING notifications with callback URLs to fetch data."""
    if not garmin_client_id:
        raise HTTPException(status_code=401, detail="Missing garmin-client-id header")

    try:
        payload = await request.json()
        logger.info(f"Garmin ping notification keys: {list(payload.keys())}")

        processed_count = 0
        errors: list[str] = []
        repo = UserConnectionRepository()

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
                        errors.append(f"User {garmin_user_id} not connected")
                        continue

                    # Save pull token to Redis
                    parsed_url = urlparse(callback_url)
                    query_params = parse_qs(parsed_url.query)
                    pull_token = query_params.get("token", [None])[0]
                    if pull_token:
                        redis_client = get_redis_client()
                        redis_client.setex(f"garmin_pull_token:{connection.user_id}:{data_type}", 3600, pull_token)

                    # Fetch and store data from callback
                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.get(callback_url, timeout=30.0)
                            response.raise_for_status()
                            data = response.json()

                        records = data if isinstance(data, list) else [data]
                        for record in records:
                            _store_garmin_record(db, connection.user_id, connection.id, data_type, record)
                        processed_count += len(records)
                        logger.info(f"Processed {len(records)} {data_type} for user {connection.user_id}")

                    except httpx.HTTPError as e:
                        logger.error(f"Failed to fetch {data_type} from callback: {e}")
                        errors.append(str(e))

                except Exception as e:
                    logger.error(f"Error processing {data_type} ping: {e}")
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
    """Receive Garmin PUSH notifications with inline data."""
    if not garmin_client_id:
        raise HTTPException(status_code=401, detail="Missing garmin-client-id header")

    try:
        payload = await request.json()
        logger.info(f"Garmin push notification keys: {list(payload.keys())}")

        processed_count = 0
        errors: list[str] = []
        repo = UserConnectionRepository()

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
                        errors.append(f"User {garmin_user_id} not connected")
                        continue

                    _store_garmin_record(db, connection.user_id, connection.id, data_type, item)
                    processed_count += 1

                except Exception as e:
                    logger.error(f"Error processing {data_type} push: {e}")
                    errors.append(str(e))

        return {"processed": processed_count, "errors": errors}

    except Exception as e:
        logger.error(f"Error processing Garmin push webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")


def _store_garmin_record(db: DbSession, user_id: UUID, connection_id: UUID, data_type: str, data: dict) -> None:
    """Parse and store a Garmin data record using raw SQL for data_source schema."""
    try:
        ds_id = _ensure_data_source(db, user_id, "garmin", connection_id)

        if data_type == "dailies":
            _store_daily(db, ds_id, data)
        elif data_type == "sleeps":
            _store_sleep(db, ds_id, data)
        elif data_type in ("activities", "activityDetails"):
            _store_activity(db, ds_id, data)
        else:
            logger.debug(f"Skipping unsupported Garmin data type: {data_type}")
    except Exception as e:
        logger.error(f"Failed to store Garmin {data_type}: {e}")
        db.rollback()


def _store_daily(db: DbSession, ds_id: UUID, data: dict) -> None:
    """Store a Garmin daily summary."""
    start_ts = data.get("startTimeInSeconds")
    offset = data.get("startTimeOffsetInSeconds", 0)
    duration = data.get("durationInSeconds", 86400)
    if not start_ts:
        return

    start_dt = _ts_to_dt(start_ts, offset)
    end_dt = _ts_to_dt(start_ts + duration, offset)
    external_id = f"daily_{start_ts}"

    # Check for existing record — UPDATE if found (dailies accumulate throughout the day)
    existing = db.execute(
        text("SELECT id FROM event_record WHERE data_source_id = :ds AND external_id = :eid LIMIT 1"),
        {"ds": str(ds_id), "eid": external_id},
    ).fetchone()

    if existing:
        # Update existing daily with latest data
        record_id = existing[0]
        db.execute(
            text("""UPDATE workout_details SET steps_count = :steps, energy_burned = :cal,
                    distance = :dist, heart_rate_avg = :avg_hr, heart_rate_min = :min_hr,
                    heart_rate_max = :max_hr, moving_time_seconds = :active
                    WHERE record_id = :rid"""),
            {
                "rid": str(record_id),
                "steps": data.get("steps"),
                "cal": data.get("activeKilocalories"),
                "dist": data.get("distanceInMeters"),
                "avg_hr": data.get("averageHeartRateInBeatsPerMinute"),
                "min_hr": data.get("minHeartRateInBeatsPerMinute"),
                "max_hr": data.get("maxHeartRateInBeatsPerMinute"),
                "active": data.get("activeTimeInSeconds"),
            },
        )
        db.commit()
        logger.info(f"Updated daily: {data.get('steps')} steps, {data.get('activeKilocalories')} cal")
        return

    record_id = uuid4()
    db.execute(
        text("""INSERT INTO event_record (id, external_id, data_source_id, category, type, source_name, duration_seconds, start_datetime, end_datetime)
                VALUES (:id, :eid, :ds, 'daily', 'daily_summary', 'garmin', :dur, :start, :end)"""),
        {"id": str(record_id), "eid": external_id, "ds": str(ds_id), "dur": duration,
         "start": start_dt, "end": end_dt},
    )

    # Event record detail (base)
    db.execute(
        text("INSERT INTO event_record_detail (record_id, detail_type) VALUES (:rid, 'workout')"),
        {"rid": str(record_id)},
    )

    # Workout details
    db.execute(
        text("""INSERT INTO workout_details (record_id, steps_count, energy_burned, distance, heart_rate_avg, heart_rate_min, heart_rate_max, moving_time_seconds)
                VALUES (:rid, :steps, :cal, :dist, :avg_hr, :min_hr, :max_hr, :active)"""),
        {
            "rid": str(record_id),
            "steps": data.get("steps"),
            "cal": data.get("activeKilocalories"),
            "dist": data.get("distanceInMeters"),
            "avg_hr": data.get("averageHeartRateInBeatsPerMinute"),
            "min_hr": data.get("minHeartRateInBeatsPerMinute"),
            "max_hr": data.get("maxHeartRateInBeatsPerMinute"),
            "active": data.get("activeTimeInSeconds"),
        },
    )
    db.commit()
    logger.info(f"Stored daily: {data.get('steps')} steps, {data.get('activeKilocalories')} cal")


def _store_sleep(db: DbSession, ds_id: UUID, data: dict) -> None:
    """Store a Garmin sleep record."""
    start_ts = data.get("startTimeInSeconds")
    offset = data.get("startTimeOffsetInSeconds", 0)
    duration = data.get("durationInSeconds")
    if not start_ts:
        return

    start_dt = _ts_to_dt(start_ts, offset)
    end_dt = _ts_to_dt(start_ts + (duration or 0), offset)
    external_id = f"sleep_{start_ts}"

    existing = db.execute(
        text("SELECT id FROM event_record WHERE data_source_id = :ds AND external_id = :eid LIMIT 1"),
        {"ds": str(ds_id), "eid": external_id},
    ).fetchone()
    if existing:
        return

    record_id = uuid4()
    db.execute(
        text("""INSERT INTO event_record (id, external_id, data_source_id, category, type, source_name, duration_seconds, start_datetime, end_datetime)
                VALUES (:id, :eid, :ds, 'sleep', 'sleep', 'garmin', :dur, :start, :end)"""),
        {"id": str(record_id), "eid": external_id, "ds": str(ds_id), "dur": duration,
         "start": start_dt, "end": end_dt},
    )

    # Sleep level breakdown
    levels = data.get("sleepLevelsMap", {})
    deep_s = sum(e.get("endTimeInSeconds", 0) - e.get("startTimeInSeconds", 0) for e in levels.get("deep", []))
    light_s = sum(e.get("endTimeInSeconds", 0) - e.get("startTimeInSeconds", 0) for e in levels.get("light", []))
    rem_s = sum(e.get("endTimeInSeconds", 0) - e.get("startTimeInSeconds", 0) for e in levels.get("rem", []))
    awake_s = sum(e.get("endTimeInSeconds", 0) - e.get("startTimeInSeconds", 0) for e in levels.get("awake", []))

    sleep_score = data.get("overallSleepScore")
    if isinstance(sleep_score, dict):
        sleep_score = sleep_score.get("value")

    db.execute(
        text("INSERT INTO event_record_detail (record_id, detail_type) VALUES (:rid, 'sleep')"),
        {"rid": str(record_id)},
    )
    db.execute(
        text("""INSERT INTO sleep_details (record_id, sleep_total_duration_minutes, sleep_deep_minutes, sleep_light_minutes, sleep_rem_minutes, sleep_awake_minutes, sleep_efficiency_score)
                VALUES (:rid, :total, :deep, :light, :rem, :awake, :score)"""),
        {
            "rid": str(record_id),
            "total": (duration or 0) // 60,
            "deep": deep_s // 60 if deep_s else None,
            "light": light_s // 60 if light_s else None,
            "rem": rem_s // 60 if rem_s else None,
            "awake": awake_s // 60 if awake_s else None,
            "score": sleep_score,
        },
    )
    db.commit()
    logger.info(f"Stored sleep: {(duration or 0) // 60} min")


def _store_activity(db: DbSession, ds_id: UUID, data: dict) -> None:
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

    existing = db.execute(
        text("SELECT id FROM event_record WHERE data_source_id = :ds AND external_id = :eid LIMIT 1"),
        {"ds": str(ds_id), "eid": external_id},
    ).fetchone()
    if existing:
        return

    record_id = uuid4()
    activity_type = data.get("activityType", "unknown")

    db.execute(
        text("""INSERT INTO event_record (id, external_id, data_source_id, category, type, source_name, duration_seconds, start_datetime, end_datetime)
                VALUES (:id, :eid, :ds, 'workout', :type, 'garmin', :dur, :start, :end)"""),
        {"id": str(record_id), "eid": external_id, "ds": str(ds_id), "type": activity_type,
         "dur": duration, "start": start_dt, "end": end_dt},
    )

    db.execute(
        text("INSERT INTO event_record_detail (record_id, detail_type) VALUES (:rid, 'workout')"),
        {"rid": str(record_id)},
    )
    db.execute(
        text("""INSERT INTO workout_details (record_id, steps_count, energy_burned, distance, heart_rate_avg, heart_rate_max, moving_time_seconds, total_elevation_gain, average_speed, max_speed)
                VALUES (:rid, :steps, :cal, :dist, :avg_hr, :max_hr, :moving, :elev, :avg_spd, :max_spd)"""),
        {
            "rid": str(record_id),
            "steps": data.get("steps"),
            "cal": data.get("activeKilocalories") or data.get("calories"),
            "dist": data.get("distanceInMeters"),
            "avg_hr": data.get("averageHeartRateInBeatsPerMinute"),
            "max_hr": data.get("maxHeartRateInBeatsPerMinute"),
            "moving": data.get("movingDurationInSeconds"),
            "elev": data.get("elevationGainInMeters"),
            "avg_spd": data.get("averageSpeedInMetersPerSecond"),
            "max_spd": data.get("maxSpeedInMetersPerSecond"),
        },
    )
    db.commit()
    logger.info(f"Stored activity {activity_type}")


@router.get("/health")
async def garmin_webhook_health() -> dict:
    """Health check endpoint for Garmin webhook configuration."""
    return {"status": "ok", "service": "garmin-webhooks"}
