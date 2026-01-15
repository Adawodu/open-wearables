"""Tests for Google Health Connect workout processing."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.providers.factory import ProviderFactory

# Sample Health Connect JSON data
SAMPLE_HEALTH_CONNECT_WORKOUT = {
    "exerciseType": 79,  # Running
    "startTime": "2024-01-15T08:30:00Z",
    "endTime": "2024-01-15T09:15:00Z",
    "id": "health_connect_session_001",
    "metadata": {"dataOrigin": "com.google.android.apps.fitness", "device": "Pixel 7 Pro"},
    "distanceRecords": [{"distance": {"inMeters": 5280.5}}],
    "caloriesRecords": [{"energy": {"inKilocalories": 342}}],
    "heartRateRecords": [
        {
            "samples": [
                {"beatsPerMinute": 125},
                {"beatsPerMinute": 142},
                {"beatsPerMinute": 138},
                {"beatsPerMinute": 155},
                {"beatsPerMinute": 148},
            ]
        }
    ],
    "elevationRecords": [{"elevation": {"inMeters": 125.3}}],
}

SAMPLE_MULTIPLE_WORKOUTS = [
    SAMPLE_HEALTH_CONNECT_WORKOUT,
    {
        "exerciseType": 8,  # Cycling
        "startTime": "2024-01-16T07:00:00Z",
        "endTime": "2024-01-16T08:30:00Z",
        "id": "health_connect_session_002",
        "metadata": {"dataOrigin": "com.strava", "device": "Pixel 7 Pro"},
        "distanceRecords": [{"distance": {"inMeters": 25000}}],
        "caloriesRecords": [{"energy": {"inKilocalories": 680}}],
        "heartRateRecords": [
            {"samples": [{"beatsPerMinute": 135}, {"beatsPerMinute": 145}, {"beatsPerMinute": 140}]}
        ],
    },
]


@pytest.fixture
def google_health_strategy():
    """Create Google Health strategy instance."""
    factory = ProviderFactory()
    return factory.get_provider("google_health")


class TestGoogleHealthConnectImport:
    """Test Google Health Connect workout import functionality."""

    def test_import_single_workout(self, db_session, test_user, google_health_strategy):
        """Test importing a single Health Connect workout."""
        # Process the workout
        google_health_strategy.workouts.process_payload(
            db=db_session, user_id=test_user.id, payload=SAMPLE_HEALTH_CONNECT_WORKOUT, source_type="health_connect"
        )

        # Verify workout was saved
        from app.models import EventRecord

        workouts = db_session.query(EventRecord).filter(EventRecord.user_id == test_user.id).all()

        assert len(workouts) == 1
        workout = workouts[0]

        # Verify basic fields
        assert workout.category == "workout"
        assert workout.type == "running"
        assert workout.source_name == "com.google.android.apps.fitness"
        assert workout.device_id == "Pixel 7 Pro"
        assert workout.duration_seconds == 2700  # 45 minutes

        # Verify timestamps
        assert workout.start_datetime == datetime(2024, 1, 15, 8, 30, 0, tzinfo=timezone.utc)
        assert workout.end_datetime == datetime(2024, 1, 15, 9, 15, 0, tzinfo=timezone.utc)

        # Verify metrics
        assert workout.detail is not None
        assert workout.detail.distance_total == Decimal("5280.5")
        assert workout.detail.calories_total == Decimal("342")
        assert workout.detail.heart_rate_min == Decimal("125")
        assert workout.detail.heart_rate_max == Decimal("155")
        assert workout.detail.heart_rate_avg == Decimal("141.6")  # Average of samples
        assert workout.detail.elevation_gain == Decimal("125.3")

    def test_import_multiple_workouts(self, db_session, test_user, google_health_strategy):
        """Test importing multiple workouts."""
        # Process multiple workouts
        google_health_strategy.workouts.process_payload(
            db=db_session, user_id=test_user.id, payload=SAMPLE_MULTIPLE_WORKOUTS, source_type="health_connect"
        )

        # Verify both workouts were saved
        from app.models import EventRecord

        workouts = db_session.query(EventRecord).filter(EventRecord.user_id == test_user.id).all()

        assert len(workouts) == 2

        # Verify first workout (running)
        running_workout = next(w for w in workouts if w.type == "running")
        assert running_workout.distance_total == Decimal("5280.5")

        # Verify second workout (cycling)
        cycling_workout = next(w for w in workouts if w.type == "cycling")
        assert cycling_workout.distance_total == Decimal("25000")
        assert cycling_workout.calories_total == Decimal("680")

    def test_import_workout_without_optional_data(self, db_session, test_user, google_health_strategy):
        """Test importing workout with minimal data (no heart rate, elevation, etc.)."""
        minimal_workout = {
            "exerciseType": 79,
            "startTime": "2024-01-17T10:00:00Z",
            "endTime": "2024-01-17T10:30:00Z",
            "metadata": {"dataOrigin": "Google Health Connect"},
        }

        google_health_strategy.workouts.process_payload(
            db=db_session, user_id=test_user.id, payload=minimal_workout, source_type="health_connect"
        )

        from app.models import EventRecord

        workouts = db_session.query(EventRecord).filter(EventRecord.user_id == test_user.id).all()

        assert len(workouts) == 1
        workout = workouts[0]

        # Basic fields should still be present
        assert workout.type == "running"
        assert workout.duration_seconds == 1800  # 30 minutes

        # Optional metrics should be None
        assert workout.detail.distance_total is None
        assert workout.detail.calories_total is None
        assert workout.detail.heart_rate_avg is None

    def test_import_invalid_source_type(self, db_session, test_user, google_health_strategy):
        """Test error handling for invalid source type."""
        with pytest.raises(ValueError, match="Unknown Google Health Connect source"):
            google_health_strategy.workouts.process_payload(
                db=db_session, user_id=test_user.id, payload=SAMPLE_HEALTH_CONNECT_WORKOUT, source_type="invalid_source"
            )

    def test_import_invalid_data_structure(self, db_session, test_user, google_health_strategy):
        """Test error handling for invalid data structure."""
        invalid_data = "not a dict or list"

        with pytest.raises(ValueError, match="Unsupported data type"):
            google_health_strategy.workouts.process_payload(
                db=db_session, user_id=test_user.id, payload=invalid_data, source_type="health_connect"
            )

    def test_workout_type_mapping(self, db_session, test_user, google_health_strategy):
        """Test that Health Connect exercise types map correctly to unified types."""
        test_cases = [
            (79, "running"),  # Running
            (8, "cycling"),  # Cycling
            (73, "swimming"),  # Swimming
            (77, "walking"),  # Walking
        ]

        for exercise_type, expected_unified_type in test_cases:
            workout = {
                "exerciseType": exercise_type,
                "startTime": "2024-01-15T08:00:00Z",
                "endTime": "2024-01-15T09:00:00Z",
                "metadata": {"dataOrigin": "Test"},
            }

            google_health_strategy.workouts.process_payload(
                db=db_session, user_id=test_user.id, payload=workout, source_type="health_connect"
            )

        from app.models import EventRecord

        workouts = db_session.query(EventRecord).filter(EventRecord.user_id == test_user.id).all()

        assert len(workouts) == len(test_cases)

        for _, expected_type in test_cases:
            assert any(w.type == expected_type for w in workouts), f"Expected workout type '{expected_type}' not found"


class TestHealthConnectHandler:
    """Test HealthConnectHandler normalization logic."""

    def test_datetime_parsing(self):
        """Test various datetime format parsing."""
        from app.services.providers.google_health.handlers.health_connect import HealthConnectHandler

        handler = HealthConnectHandler()

        # Test ISO 8601 with Z
        dt1 = handler._parse_datetime("2024-01-15T08:30:00Z")
        assert dt1 == datetime(2024, 1, 15, 8, 30, 0, tzinfo=timezone.utc)

        # Test ISO 8601 with timezone
        dt2 = handler._parse_datetime("2024-01-15T08:30:00+00:00")
        assert dt2.hour == 8

        # Test empty string (should return current time)
        dt3 = handler._parse_datetime("")
        assert isinstance(dt3, datetime)

    def test_heart_rate_calculation(self):
        """Test heart rate min/max/avg calculation."""
        from app.services.providers.google_health.handlers.health_connect import HealthConnectHandler

        handler = HealthConnectHandler()

        session = {
            "heartRateRecords": [
                {"samples": [{"beatsPerMinute": 120}, {"beatsPerMinute": 150}, {"beatsPerMinute": 135}]}
            ]
        }

        hr_data = handler._extract_heart_rate(session)

        assert hr_data["min"] == Decimal("120")
        assert hr_data["max"] == Decimal("150")
        assert hr_data["avg"] == Decimal("135")  # (120 + 150 + 135) / 3

    def test_distance_aggregation(self):
        """Test distance aggregation from multiple records."""
        from app.services.providers.google_health.handlers.health_connect import HealthConnectHandler

        handler = HealthConnectHandler()

        session = {
            "distanceRecords": [
                {"distance": {"inMeters": 1000}},
                {"distance": {"inMeters": 2000}},
                {"distance": {"inMeters": 500}},
            ]
        }

        distance = handler._extract_distance(session)

        assert distance == Decimal("3500")
