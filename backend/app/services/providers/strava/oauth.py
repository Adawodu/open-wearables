import httpx

from app.config import settings
from app.schemas import (
    AuthenticationMethod,
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class StravaOAuth(BaseOAuthTemplate):
    """Strava OAuth 2.0 implementation."""

    @property
    def endpoints(self) -> ProviderEndpoints:
        return ProviderEndpoints(
            authorize_url="https://www.strava.com/oauth/authorize",
            token_url="https://www.strava.com/oauth/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        return ProviderCredentials(
            client_id=settings.strava_client_id or "",
            client_secret=(settings.strava_client_secret.get_secret_value() if settings.strava_client_secret else ""),
            redirect_uri=settings.strava_redirect_uri,
            default_scope=settings.strava_default_scope,
        )

    use_pkce = False
    auth_method = AuthenticationMethod.BODY

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Strava returns athlete info in the token response."""
        try:
            response = httpx.get(
                "https://www.strava.com/api/v3/athlete",
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            response.raise_for_status()
            athlete = response.json()
            return {
                "user_id": str(athlete.get("id")),
                "username": athlete.get("username") or f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip() or None,
            }
        except Exception:
            return {"user_id": None, "username": None}
