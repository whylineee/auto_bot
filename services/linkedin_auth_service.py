from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field


class LinkedInAuthServiceError(Exception):
    pass


class LinkedInOAuthToken(BaseModel):
    access_token: str = Field(min_length=10)
    expires_at_epoch: int
    refresh_token: Optional[str] = None


class LinkedInUserInfo(BaseModel):
    sub: str
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None
    picture: Optional[str] = None


class LinkedInAuthService:
    AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        logger: logging.Logger,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: list[str],
        timeout_seconds: float,
    ) -> None:
        self._http_client = http_client
        self._logger = logger
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._scopes = scopes
        self._timeout_seconds = timeout_seconds

    @property
    def is_enabled(self) -> bool:
        return bool(self._client_id and self._client_secret and self._redirect_uri)

    def build_authorization_url(self, state: str) -> str:
        if not self.is_enabled:
            raise LinkedInAuthServiceError("LinkedIn OAuth is not configured")

        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "scope": " ".join(self._scopes),
                "state": state,
            }
        )
        return f"{self.AUTH_URL}?{query}"

    async def exchange_code_for_token(self, code: str) -> LinkedInOAuthToken:
        if not self.is_enabled:
            raise LinkedInAuthServiceError("LinkedIn OAuth is not configured")

        form_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self._redirect_uri,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }

        try:
            response = await self._http_client.post(
                self.TOKEN_URL,
                data=form_data,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self._logger.exception("LinkedIn OAuth token exchange failed")
            raise LinkedInAuthServiceError(f"OAuth token exchange failed: {exc}") from exc

        payload = response.json()
        access_token = str(payload.get("access_token", "")).strip()
        expires_in = int(payload.get("expires_in", 0) or 0)
        refresh_token = payload.get("refresh_token")

        if not access_token or expires_in <= 0:
            raise LinkedInAuthServiceError("LinkedIn OAuth returned invalid token payload")

        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in)
        return LinkedInOAuthToken(
            access_token=access_token,
            expires_at_epoch=int(expires_at.timestamp()),
            refresh_token=str(refresh_token).strip() if refresh_token else None,
        )

    async def get_user_info(self, access_token: str) -> LinkedInUserInfo:
        if not access_token.strip():
            raise LinkedInAuthServiceError("Access token is missing")

        headers = {"Authorization": f"Bearer {access_token.strip()}"}
        try:
            response = await self._http_client.get(
                self.USERINFO_URL,
                headers=headers,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self._logger.exception("LinkedIn userinfo request failed")
            raise LinkedInAuthServiceError(f"Failed to fetch LinkedIn user info: {exc}") from exc

        payload = response.json()
        return LinkedInUserInfo.model_validate(payload)
