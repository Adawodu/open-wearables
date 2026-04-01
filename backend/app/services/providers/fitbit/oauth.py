import httpx

from app.config import settings
from app.schemas import (
    AuthenticationMethod,
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class FitbitOAuth(BaseOAuthTemplate):
    """Fitbit OAuth 2.0 with PKCE implementation."""

    @property
    def endpoints(self) -> ProviderEndpoints:
        return ProviderEndpoints(
            authorize_url="https://www.fitbit.com/oauth2/authorize",
            token_url="https://api.fitbit.com/oauth2/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        return ProviderCredentials(
            client_id=settings.fitbit_client_id or "",
            client_secret=(settings.fitbit_client_secret.get_secret_value() if settings.fitbit_client_secret else ""),
            redirect_uri=settings.fitbit_redirect_uri,
            default_scope=settings.fitbit_default_scope,
        )

    use_pkce = True
    auth_method = AuthenticationMethod.BASIC_AUTH  # Fitbit uses Basic Auth for token exchange

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Fetch Fitbit user profile."""
        try:
            response = httpx.get(
                "https://api.fitbit.com/1/user/-/profile.json",
                headers={"Authorization": f"Bearer {token_response.access_token}"},
                timeout=30.0,
            )
            response.raise_for_status()
            user_data = response.json().get("user", {})
            return {
                "user_id": user_data.get("encodedId"),
                "username": user_data.get("displayName") or user_data.get("fullName"),
            }
        except Exception:
            return {"user_id": None, "username": None}
