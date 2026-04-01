from app.services.providers.apple.strategy import AppleStrategy
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.fitbit.strategy import FitbitStrategy
from app.services.providers.garmin.strategy import GarminStrategy
from app.services.providers.google_health.strategy import GoogleHealthStrategy
from app.services.providers.polar.strategy import PolarStrategy
from app.services.providers.strava.strategy import StravaStrategy
from app.services.providers.suunto.strategy import SuuntoStrategy


class ProviderFactory:
    """Factory for creating provider instances."""

    def get_provider(self, provider_name: str) -> BaseProviderStrategy:
        match provider_name:
            case "apple":
                return AppleStrategy()
            case "fitbit":
                return FitbitStrategy()
            case "garmin":
                return GarminStrategy()
            case "google_health":
                return GoogleHealthStrategy()
            case "strava":
                return StravaStrategy()
            case "suunto":
                return SuuntoStrategy()
            case "polar":
                return PolarStrategy()
            case _:
                raise ValueError(f"Unknown provider: {provider_name}")
