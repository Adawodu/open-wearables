"""Google Health Connect exercise type to OpenWearables unified workout type mapping.

Based on ExerciseSessionRecord.EXERCISE_TYPE_* from Android Health Connect API.
Reference: https://developer.android.com/reference/kotlin/androidx/health/connect/client/records/ExerciseSessionRecord
"""

from app.schemas.workout_types import WorkoutType

# Google Health Connect exercise types
# Format: (exercise_type_id, exercise_type_name, unified_type)
GOOGLE_HEALTH_WORKOUT_TYPE_MAPPINGS: list[tuple[int, str, WorkoutType]] = [
    # Running & Walking
    (79, "EXERCISE_TYPE_RUNNING", WorkoutType.RUNNING),
    (80, "EXERCISE_TYPE_RUNNING_TREADMILL", WorkoutType.TREADMILL),
    (90, "EXERCISE_TYPE_WALKING", WorkoutType.WALKING),
    (36, "EXERCISE_TYPE_HIKING", WorkoutType.HIKING),
    # Cycling
    (8, "EXERCISE_TYPE_BIKING", WorkoutType.CYCLING),
    (9, "EXERCISE_TYPE_BIKING_STATIONARY", WorkoutType.INDOOR_CYCLING),
    # Swimming
    (82, "EXERCISE_TYPE_SWIMMING_POOL", WorkoutType.POOL_SWIMMING),
    (83, "EXERCISE_TYPE_SWIMMING_OPEN_WATER", WorkoutType.OPEN_WATER_SWIMMING),
    # Gym & Fitness
    (5, "EXERCISE_TYPE_BACK_EXTENSION", WorkoutType.STRENGTH_TRAINING),
    (10, "EXERCISE_TYPE_CALISTHENICS", WorkoutType.STRENGTH_TRAINING),
    (13, "EXERCISE_TYPE_CRUNCH", WorkoutType.STRENGTH_TRAINING),
    (25, "EXERCISE_TYPE_ELLIPTICAL", WorkoutType.ELLIPTICAL),
    (26, "EXERCISE_TYPE_EXERCISE_CLASS", WorkoutType.CARDIO_TRAINING),
    (28, "EXERCISE_TYPE_FRISBEE_DISC", WorkoutType.OTHER),
    (32, "EXERCISE_TYPE_GUIDED_BREATHING", WorkoutType.STRETCHING),
    (33, "EXERCISE_TYPE_GYMNASTICS", WorkoutType.FITNESS_EQUIPMENT),
    (37, "EXERCISE_TYPE_HIGH_INTENSITY_INTERVAL_TRAINING", WorkoutType.CARDIO_TRAINING),
    (45, "EXERCISE_TYPE_JUMP_ROPE", WorkoutType.CARDIO_TRAINING),
    (55, "EXERCISE_TYPE_PILATES", WorkoutType.PILATES),
    (56, "EXERCISE_TYPE_PLANK", WorkoutType.STRENGTH_TRAINING),
    (74, "EXERCISE_TYPE_ROCK_CLIMBING", WorkoutType.ROCK_CLIMBING),
    (75, "EXERCISE_TYPE_ROLLER_SKATING", WorkoutType.INLINE_SKATING),
    (78, "EXERCISE_TYPE_ROWING_MACHINE", WorkoutType.ROWING_MACHINE),
    (84, "EXERCISE_TYPE_STAIR_CLIMBING", WorkoutType.STAIR_CLIMBING),
    (85, "EXERCISE_TYPE_STAIR_CLIMBING_MACHINE", WorkoutType.STAIR_CLIMBING),
    (86, "EXERCISE_TYPE_STRENGTH_TRAINING", WorkoutType.STRENGTH_TRAINING),
    (87, "EXERCISE_TYPE_STRETCHING", WorkoutType.STRETCHING),
    (91, "EXERCISE_TYPE_WEIGHTLIFTING", WorkoutType.STRENGTH_TRAINING),
    (92, "EXERCISE_TYPE_WHEELCHAIR", WorkoutType.OTHER),
    (93, "EXERCISE_TYPE_YOGA", WorkoutType.YOGA),
    # Winter Sports
    (17, "EXERCISE_TYPE_DOWNHILL_SKIING", WorkoutType.ALPINE_SKIING),
    (18, "EXERCISE_TYPE_CROSS_COUNTRY_SKIING", WorkoutType.CROSS_COUNTRY_SKIING),
    (38, "EXERCISE_TYPE_ICE_HOCKEY", WorkoutType.HOCKEY),
    (39, "EXERCISE_TYPE_ICE_SKATING", WorkoutType.ICE_SKATING),
    (81, "EXERCISE_TYPE_SNOWBOARDING", WorkoutType.SNOWBOARDING),
    (89, "EXERCISE_TYPE_SNOWSHOEING", WorkoutType.SNOWSHOEING),
    # Water Sports
    (46, "EXERCISE_TYPE_KAYAKING", WorkoutType.KAYAKING),
    (47, "EXERCISE_TYPE_KITESURFING", WorkoutType.KITESURFING),
    (53, "EXERCISE_TYPE_PARAGLIDING", WorkoutType.OTHER),
    (54, "EXERCISE_TYPE_PADDLING", WorkoutType.PADDLING),
    (76, "EXERCISE_TYPE_ROWING", WorkoutType.ROWING),
    (77, "EXERCISE_TYPE_SAILING", WorkoutType.SAILING),
    (80, "EXERCISE_TYPE_SCUBA_DIVING", WorkoutType.DIVING),
    (88, "EXERCISE_TYPE_SURFING", WorkoutType.SURFING),
    (91, "EXERCISE_TYPE_WATER_POLO", WorkoutType.OTHER),
    (92, "EXERCISE_TYPE_WINDSURFING", WorkoutType.WINDSURFING),
    # Team Sports
    (3, "EXERCISE_TYPE_AMERICAN_FOOTBALL", WorkoutType.AMERICAN_FOOTBALL),
    (4, "EXERCISE_TYPE_AUSTRALIAN_FOOTBALL", WorkoutType.FOOTBALL),
    (6, "EXERCISE_TYPE_BADMINTON", WorkoutType.BADMINTON),
    (7, "EXERCISE_TYPE_BASEBALL", WorkoutType.BASEBALL),
    (11, "EXERCISE_TYPE_BASKETBALL", WorkoutType.BASKETBALL),
    (14, "EXERCISE_TYPE_CRICKET", WorkoutType.OTHER),
    (27, "EXERCISE_TYPE_FENCING", WorkoutType.OTHER),
    (31, "EXERCISE_TYPE_HANDBALL", WorkoutType.HANDBALL),
    (40, "EXERCISE_TYPE_LACROSSE", WorkoutType.OTHER),
    (73, "EXERCISE_TYPE_RUGBY", WorkoutType.RUGBY),
    (79, "EXERCISE_TYPE_SOCCER", WorkoutType.SOCCER),
    (80, "EXERCISE_TYPE_SOFTBALL", WorkoutType.BASEBALL),
    (88, "EXERCISE_TYPE_VOLLEYBALL", WorkoutType.VOLLEYBALL),
    # Racket Sports
    (57, "EXERCISE_TYPE_RACQUETBALL", WorkoutType.OTHER),
    (84, "EXERCISE_TYPE_SQUASH", WorkoutType.SQUASH),
    (85, "EXERCISE_TYPE_TABLE_TENNIS", WorkoutType.TABLE_TENNIS),
    (86, "EXERCISE_TYPE_TENNIS", WorkoutType.TENNIS),
    (58, "EXERCISE_TYPE_PICKLEBALL", WorkoutType.PICKLEBALL),
    # Martial Arts & Combat Sports
    (12, "EXERCISE_TYPE_BOXING", WorkoutType.BOXING),
    (48, "EXERCISE_TYPE_MARTIAL_ARTS", WorkoutType.MARTIAL_ARTS),
    (93, "EXERCISE_TYPE_WRESTLING", WorkoutType.MARTIAL_ARTS),
    # Dance
    (15, "EXERCISE_TYPE_DANCING", WorkoutType.DANCE),
    # Other Sports
    (1, "EXERCISE_TYPE_ALPINE_SKIING", WorkoutType.ALPINE_SKIING),
    (2, "EXERCISE_TYPE_ARCHERY", WorkoutType.OTHER),
    (16, "EXERCISE_TYPE_GOLF", WorkoutType.GOLF),
    (29, "EXERCISE_TYPE_GARDENING", WorkoutType.OTHER),
    (34, "EXERCISE_TYPE_HORSEBACK_RIDING", WorkoutType.HORSEBACK_RIDING),
    (41, "EXERCISE_TYPE_MARTIAL_ARTS", WorkoutType.MARTIAL_ARTS),
    (50, "EXERCISE_TYPE_PADDLEBOARDING", WorkoutType.STAND_UP_PADDLEBOARDING),
    (59, "EXERCISE_TYPE_SKATING", WorkoutType.ICE_SKATING),
    (60, "EXERCISE_TYPE_SKATEBOARDING", WorkoutType.OTHER),
    (0, "EXERCISE_TYPE_OTHER_WORKOUT", WorkoutType.OTHER),
]

# Create lookup dictionaries
GOOGLE_HEALTH_ID_TO_UNIFIED: dict[int, WorkoutType] = {
    exercise_id: unified_type for exercise_id, _, unified_type in GOOGLE_HEALTH_WORKOUT_TYPE_MAPPINGS
}

GOOGLE_HEALTH_NAME_TO_UNIFIED: dict[str, WorkoutType] = {
    name: unified_type for _, name, unified_type in GOOGLE_HEALTH_WORKOUT_TYPE_MAPPINGS
}

GOOGLE_HEALTH_ID_TO_NAME: dict[int, str] = {
    exercise_id: name for exercise_id, name, _ in GOOGLE_HEALTH_WORKOUT_TYPE_MAPPINGS
}


def get_unified_workout_type_by_id(exercise_type_id: int) -> WorkoutType:
    """
    Convert Google Health Connect exercise type ID to unified WorkoutType.

    Args:
        exercise_type_id: Health Connect exercise type ID (e.g., 79 for Running)

    Returns:
        Unified WorkoutType enum value

    Examples:
        >>> get_unified_workout_type_by_id(79)
        WorkoutType.RUNNING
        >>> get_unified_workout_type_by_id(8)
        WorkoutType.CYCLING
        >>> get_unified_workout_type_by_id(999)
        WorkoutType.OTHER
    """
    return GOOGLE_HEALTH_ID_TO_UNIFIED.get(exercise_type_id, WorkoutType.OTHER)


def get_unified_workout_type_by_name(exercise_type_name: str) -> WorkoutType:
    """
    Convert Google Health Connect exercise type name to unified WorkoutType.

    Args:
        exercise_type_name: Health Connect exercise type name (e.g., "EXERCISE_TYPE_RUNNING")

    Returns:
        Unified WorkoutType enum value

    Examples:
        >>> get_unified_workout_type_by_name("EXERCISE_TYPE_RUNNING")
        WorkoutType.RUNNING
        >>> get_unified_workout_type_by_name("EXERCISE_TYPE_BIKING")
        WorkoutType.CYCLING
        >>> get_unified_workout_type_by_name("UNKNOWN")
        WorkoutType.OTHER
    """
    return GOOGLE_HEALTH_NAME_TO_UNIFIED.get(exercise_type_name, WorkoutType.OTHER)


def get_exercise_name(exercise_type_id: int) -> str:
    """Get the Health Connect exercise name for a given ID."""
    return GOOGLE_HEALTH_ID_TO_NAME.get(exercise_type_id, "Unknown")
