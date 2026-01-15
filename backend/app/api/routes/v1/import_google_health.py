"""Google Health Connect import endpoint."""

import json
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.database import DbSession
from app.services import ApiKeyDep
from app.services.providers.factory import ProviderFactory

router = APIRouter()


@router.post("/users/{user_id}/import/google-health", status_code=status.HTTP_201_CREATED)
async def import_google_health(
    user_id: UUID,
    file: UploadFile = File(..., description="Google Health Connect JSON export file"),
    db: DbSession = None,
    _api_key: ApiKeyDep = None,
):
    """Import Google Health Connect JSON export.

    This endpoint accepts Health Connect ExerciseSessionRecord data exported from
    Android devices and normalizes it to the unified workout schema.

    Args:
        user_id: User ID to associate the data with
        file: JSON file containing Health Connect exercise session data
        db: Database session
        _api_key: API key for authentication

    Returns:
        Success message with count of imported workouts

    Raises:
        400: Invalid JSON format or unsupported data structure
        401: Invalid or missing API key
        404: User not found
        500: Server error during processing

    Health Connect JSON Format:
        Single workout:
        ```json
        {
          "exerciseType": 79,
          "startTime": "2024-01-15T08:30:00Z",
          "endTime": "2024-01-15T09:15:00Z",
          "metadata": {
            "dataOrigin": "com.google.android.apps.fitness",
            "device": "Pixel 7 Pro"
          },
          "distanceRecords": [{"distance": {"inMeters": 5280.5}}],
          "caloriesRecords": [{"energy": {"inKilocalories": 342}}],
          "heartRateRecords": [{"samples": [{"beatsPerMinute": 125}]}]
        }
        ```

    Exercise Type Mapping:
        - 79: Running, 8: Cycling, 73: Swimming, 77: Walking
        See: https://developer.android.com/health-and-fitness/guides/health-connect

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/users/{user_id}/import/google-health" \\
          -H "X-API-Key: YOUR_API_KEY" \\
          -F "file=@health_connect_export.json"
        ```

    Example Response:
        ```json
        {
          "success": true,
          "message": "Successfully imported 5 workout(s) from Google Health Connect",
          "workouts_imported": 5
        }
        ```
    """
    # Read and parse JSON file
    try:
        content = await file.read()
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON format: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error reading file: {str(e)}",
        )

    # Get Google Health provider
    factory = ProviderFactory()
    strategy = factory.get_provider("google_health")

    # Process the payload
    strategy.workouts.process_payload(
        db=db, user_id=user_id, payload=data, source_type="health_connect"
    )

    # Count workouts (handle both single record and list)
    workout_count = len(data) if isinstance(data, list) else 1

    return {
        "success": True,
        "message": f"Successfully imported {workout_count} workout(s) from Google Health Connect",
        "workouts_imported": workout_count,
    }
