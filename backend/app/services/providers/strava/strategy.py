from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.strava.oauth import StravaOAuth
from app.services.providers.strava.workouts import StravaWorkouts


class StravaStrategy(BaseProviderStrategy):
    """Strava provider implementation."""

    def __init__(self):
        super().__init__()
        self.oauth = StravaOAuth(
            user_repo=self.user_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )
        self.workouts = StravaWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
            oauth=self.oauth,
        )

    @property
    def name(self) -> str:
        return "strava"

    @property
    def api_base_url(self) -> str:
        return "https://www.strava.com"
