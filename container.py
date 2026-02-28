from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

import httpx
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from config import AppConfig
from repositories.autopost_settings_repository import AutopostSettingsRepository
from repositories.linkedin_token_repository import LinkedInTokenRepository
from services.ai_service import AIService
from services.autopost_service import AutopostService
from services.linkedin_auth_service import LinkedInAuthService
from services.linkedin_service import LinkedInService
from services.linkedin_token_service import LinkedInTokenService
from services.news_service import NewsService


class ServiceContainer:
    def __init__(self, config: AppConfig, logger: logging.Logger) -> None:
        self._config = config
        self._logger = logger

        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.http_timeout_seconds),
            follow_redirects=True,
        )
        self._autopost_settings_repository = AutopostSettingsRepository(
            config.autopost_settings_path
        )
        self._linkedin_token_repository = LinkedInTokenRepository(config.linkedin_token_store_path)
        self._linkedin_token_service = LinkedInTokenService(
            repository=self._linkedin_token_repository,
            fallback_access_token=config.linkedin_access_token,
            fallback_person_id=config.linkedin_person_id,
        )
        self._linkedin_auth_service = LinkedInAuthService(
            http_client=self._http_client,
            logger=logger,
            client_id=config.linkedin_client_id,
            client_secret=config.linkedin_client_secret,
            redirect_uri=config.linkedin_redirect_uri,
            scopes=config.linkedin_scopes,
            timeout_seconds=config.http_timeout_seconds,
        )

        self._news_service = NewsService(
            http_client=self._http_client,
            logger=logger,
            keywords=config.news_keywords,
            timeout_seconds=config.http_timeout_seconds,
        )
        self._ai_service = AIService(
            http_client=self._http_client,
            logger=logger,
            api_key=config.qwen_api_key,
            api_url=config.qwen_api_url,
            model=config.qwen_model,
            timeout_seconds=config.ai_request_timeout_seconds,
            max_retries=config.ai_max_retries,
            retry_backoff_seconds=config.ai_retry_backoff_seconds,
        )
        self._linkedin_service = LinkedInService(
            http_client=self._http_client,
            logger=logger,
            timeout_seconds=config.http_timeout_seconds,
        )
        self._autopost_service = AutopostService(
            repository=self._autopost_settings_repository,
            news_service=self._news_service,
            ai_service=self._ai_service,
            linkedin_service=self._linkedin_service,
            linkedin_token_service=self._linkedin_token_service,
            logger=logger,
            news_limit=config.news_limit,
        )

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def news_service(self) -> NewsService:
        return self._news_service

    @property
    def ai_service(self) -> AIService:
        return self._ai_service

    @property
    def linkedin_service(self) -> LinkedInService:
        return self._linkedin_service

    @property
    def linkedin_auth_service(self) -> LinkedInAuthService:
        return self._linkedin_auth_service

    @property
    def linkedin_token_service(self) -> LinkedInTokenService:
        return self._linkedin_token_service

    @property
    def autopost_service(self) -> AutopostService:
        return self._autopost_service

    async def close(self) -> None:
        await self._autopost_service.stop()
        await self._http_client.aclose()


class ServicesMiddleware(BaseMiddleware):
    def __init__(self, container: ServiceContainer) -> None:
        self._container = container

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["config"] = self._container.config
        data["news_service"] = self._container.news_service
        data["ai_service"] = self._container.ai_service
        data["linkedin_service"] = self._container.linkedin_service
        data["linkedin_auth_service"] = self._container.linkedin_auth_service
        data["linkedin_token_service"] = self._container.linkedin_token_service
        data["autopost_service"] = self._container.autopost_service
        return await handler(event, data)
