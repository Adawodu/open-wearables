"""Google Health Connect provider strategy."""

from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.google_health.workouts import GoogleHealthWorkouts


class GoogleHealthStrategy(BaseProviderStrategy):
    """Google Health Connect provider implementation."""

    def __init__(self):
        super().__init__()
        self.workouts = GoogleHealthWorkouts(self.workout_repo, self.connection_repo)

    @property
    def name(self) -> str:
        return "google_health"

    @property
    def display_name(self) -> str:
        return "Google Health Connect"

    @property
    def api_base_url(self) -> str:
        return ""  # Google Health Connect doesn't have a cloud API
