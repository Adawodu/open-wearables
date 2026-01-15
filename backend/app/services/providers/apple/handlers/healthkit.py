"""HealthKit XML export handler for Apple Health data."""

import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.constants.workout_types.apple import get_unified_workout_type
from app.schemas.event_record import EventRecordCreate
from app.schemas.event_record_detail import EventRecordDetailCreate
from app.services.providers.apple.handlers.base import AppleSourceHandler


class HealthKitHandler(AppleSourceHandler):
    """Handler for HealthKit XML export data.

    Parses Apple Health export.xml files and normalizes workout data
    to the unified event record schema.
    """

    def normalize(self, data: Any) -> list[tuple[EventRecordCreate, EventRecordDetailCreate]]:
        """
        Parse HealthKit XML export and normalize to unified schema.

        Args:
            data: Either XML string or parsed ElementTree containing HealthKit export data

        Returns:
            List of tuples containing (EventRecordCreate, EventRecordDetailCreate)
        """
        # Parse XML if string provided
        if isinstance(data, str):
            root = ET.fromstring(data)
        elif isinstance(data, bytes):
            root = ET.fromstring(data.decode("utf-8"))
        elif isinstance(data, ET.Element):
            root = data
        else:
            raise ValueError(f"Unsupported data type for HealthKit parsing: {type(data)}")

        workouts = []

        # Find all Workout elements in the XML
        for workout_elem in root.findall(".//Workout"):
            try:
                record, detail = self._parse_workout_element(workout_elem)
                workouts.append((record, detail))
            except Exception as e:
                # Log error but continue processing other workouts
                print(f"Error parsing workout: {e}")
                continue

        return workouts

    def _parse_workout_element(self, workout_elem: ET.Element) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        """Parse a single Workout XML element into normalized records."""

        # Extract basic workout attributes
        workout_type = workout_elem.get("workoutActivityType", "HKWorkoutActivityTypeOther")
        source_name = workout_elem.get("sourceName", "Apple Health")
        device_name = workout_elem.get("device", "")

        # Parse timestamps
        start_date = self._parse_datetime(workout_elem.get("startDate", ""))
        end_date = self._parse_datetime(workout_elem.get("endDate", ""))

        # Calculate duration
        duration_value = workout_elem.get("duration")
        duration_unit = workout_elem.get("durationUnit", "min")
        duration_seconds = self._parse_duration(duration_value, duration_unit)

        # Extract distance
        distance_value = workout_elem.get("totalDistance")
        distance_unit = workout_elem.get("totalDistanceUnit")
        distance_meters = self._parse_distance(distance_value, distance_unit)

        # Extract energy/calories
        energy_value = workout_elem.get("totalEnergyBurned")
        energy_unit = workout_elem.get("totalEnergyBurnedUnit", "kcal")
        calories = self._parse_energy(energy_value, energy_unit)

        # Parse metadata for additional metrics
        metadata = self._parse_metadata(workout_elem)

        # Build metrics
        metrics = self._build_metrics(
            metadata=metadata,
            distance_meters=distance_meters,
            calories=calories,
        )

        # Create unified workout record
        workout_id = uuid4()
        unified_type = get_unified_workout_type(workout_type)

        record = EventRecordCreate(
            id=workout_id,
            category="workout",
            type=unified_type.value,
            source_name=source_name,
            device_id=device_name or None,
            duration_seconds=duration_seconds,
            start_datetime=start_date,
            end_datetime=end_date,
            provider_id=None,  # HealthKit doesn't provide unique IDs
            user_id=None,  # Will be set by the caller
        )

        detail = EventRecordDetailCreate(
            record_id=workout_id,
            **metrics,
        )

        return record, detail

    def _parse_datetime(self, date_str: str) -> datetime:
        """Parse HealthKit datetime string to datetime object.

        HealthKit format: "2024-01-15 08:30:00 -0800"
        """
        if not date_str:
            return datetime.now()

        try:
            # Try with timezone
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            try:
                # Try without timezone
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # Fallback to ISO format
                return datetime.fromisoformat(date_str.replace(" ", "T"))

    def _parse_duration(self, value: str | None, unit: str) -> int:
        """Convert duration to seconds."""
        if not value:
            return 0

        try:
            duration = float(value)
        except (ValueError, TypeError):
            return 0

        # Convert to seconds based on unit
        if unit == "min":
            return int(duration * 60)
        if unit == "hr":
            return int(duration * 3600)
        if unit == "s":
            return int(duration)
        # Assume minutes if unknown
        return int(duration * 60)

    def _parse_distance(self, value: str | None, unit: str | None) -> Decimal | None:
        """Convert distance to meters."""
        if not value:
            return None

        try:
            distance = Decimal(value)
        except (ValueError, TypeError):
            return None

        if not unit:
            return distance

        # Convert to meters based on unit
        if unit == "km":
            return distance * 1000
        if unit == "mi":
            return distance * Decimal("1609.34")
        if unit == "m":
            return distance
        if unit == "yd":
            return distance * Decimal("0.9144")
        # Assume meters if unknown
        return distance

    def _parse_energy(self, value: str | None, unit: str) -> Decimal | None:
        """Convert energy to kilocalories."""
        if not value:
            return None

        try:
            energy = Decimal(value)
        except (ValueError, TypeError):
            return None

        # Convert to kcal based on unit
        if unit == "Cal" or unit == "kcal":
            return energy
        if unit == "kJ":
            return energy / Decimal("4.184")
        # Assume kcal if unknown
        return energy

    def _parse_metadata(self, workout_elem: ET.Element) -> dict[str, Any]:
        """Extract metadata entries from workout element."""
        metadata = {}

        for meta_elem in workout_elem.findall("MetadataEntry"):
            key = meta_elem.get("key", "")
            value = meta_elem.get("value", "")

            if key and value:
                # Try to convert to appropriate type
                try:
                    # Try integer first
                    metadata[key] = int(value)
                except ValueError:
                    try:
                        # Try float
                        metadata[key] = float(value)
                    except ValueError:
                        # Keep as string
                        metadata[key] = value

        return metadata

    def _build_metrics(
        self,
        metadata: dict[str, Any],
        distance_meters: Decimal | None,
        calories: Decimal | None,
    ) -> dict[str, Any]:
        """Build metrics dictionary from metadata and workout data."""
        metrics: dict[str, Any] = {}

        # Heart rate metrics
        if "HKAverageHeartRate" in metadata:
            metrics["heart_rate_avg"] = Decimal(str(metadata["HKAverageHeartRate"]))
        if "HKMaximumHeartRate" in metadata:
            metrics["heart_rate_max"] = Decimal(str(metadata["HKMaximumHeartRate"]))
        if "HKMinimumHeartRate" in metadata:
            metrics["heart_rate_min"] = Decimal(str(metadata["HKMinimumHeartRate"]))

        # Distance
        if distance_meters is not None:
            metrics["distance_total"] = distance_meters

        # Calories
        if calories is not None:
            metrics["calories_total"] = calories

        # Elevation (if available)
        if "HKElevationAscended" in metadata:
            metrics["elevation_gain"] = Decimal(str(metadata["HKElevationAscended"]))
        if "HKElevationDescended" in metadata:
            metrics["elevation_loss"] = Decimal(str(metadata["HKElevationDescended"]))

        # Weather (if available)
        if "HKWeatherTemperature" in metadata:
            metrics["temperature"] = Decimal(str(metadata["HKWeatherTemperature"]))
        if "HKWeatherHumidity" in metadata:
            metrics["humidity"] = Decimal(str(metadata["HKWeatherHumidity"]))

        return metrics
