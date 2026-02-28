from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from repositories.linkedin_token_repository import LinkedInTokenRepository, StoredLinkedInAccount
from services.linkedin_auth_service import LinkedInOAuthToken


@dataclass(frozen=True)
class LinkedInCredentials:
    access_token: str
    person_id: str
    source: str
    expires_at_epoch: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None


class LinkedInTokenService:
    def __init__(
        self,
        repository: LinkedInTokenRepository,
        fallback_access_token: str,
        fallback_person_id: str,
    ) -> None:
        self._repository = repository
        self._fallback_access_token = self._sanitize_env_value(fallback_access_token)
        self._fallback_person_id = self._sanitize_env_value(fallback_person_id)

    async def get_credentials_for_user(self, telegram_user_id: int) -> Optional[LinkedInCredentials]:
        stored = await self._repository.get_user(telegram_user_id)
        if stored and self._is_token_valid(stored):
            return LinkedInCredentials(
                access_token=stored.access_token,
                person_id=stored.person_id,
                source="oauth",
                expires_at_epoch=stored.expires_at_epoch,
                name=stored.name,
                email=stored.email,
            )

        if self._fallback_access_token and self._fallback_person_id:
            return LinkedInCredentials(
                access_token=self._fallback_access_token,
                person_id=self._fallback_person_id,
                source="env",
            )

        return None

    async def store_oauth_account(
        self,
        telegram_user_id: int,
        oauth_token: LinkedInOAuthToken,
        person_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> None:
        account = StoredLinkedInAccount(
            access_token=oauth_token.access_token,
            refresh_token=oauth_token.refresh_token,
            expires_at_epoch=oauth_token.expires_at_epoch,
            person_id=person_id,
            name=name,
            email=email,
        )
        await self._repository.save_user(telegram_user_id, account)

    async def token_source(self, telegram_user_id: int) -> str:
        credentials = await self.get_credentials_for_user(telegram_user_id)
        return credentials.source if credentials else "none"

    async def get_expires_at(self, telegram_user_id: int) -> Optional[int]:
        stored = await self._repository.get_user(telegram_user_id)
        if stored and self._is_token_valid(stored):
            return stored.expires_at_epoch
        return None

    async def clear_oauth_account(self, telegram_user_id: int) -> None:
        await self._repository.delete_user(telegram_user_id)

    def _is_token_valid(self, account: StoredLinkedInAccount) -> bool:
        now_epoch = int(datetime.now(tz=timezone.utc).timestamp())
        return account.expires_at_epoch > now_epoch + 60

    @staticmethod
    def _sanitize_env_value(raw_value: str) -> str:
        value = raw_value.strip()
        lowered = value.lower()
        if not value:
            return ""
        if lowered.startswith("your_"):
            return ""
        if "your-domain.com" in lowered:
            return ""
        return value
