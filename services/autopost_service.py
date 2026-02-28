from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from repositories.autopost_settings_repository import AutopostSettings, AutopostSettingsRepository
from services.ai_service import AIService, AIServiceError, PostStyle
from services.linkedin_service import LinkedInService, LinkedInServiceError
from services.linkedin_token_service import LinkedInTokenService
from services.news_service import NewsItem, NewsService


class AutopostServiceError(Exception):
    pass


class AutopostService:
    JOB_ID = "autopost_job"

    def __init__(
        self,
        repository: AutopostSettingsRepository,
        news_service: NewsService,
        ai_service: AIService,
        linkedin_service: LinkedInService,
        linkedin_token_service: LinkedInTokenService,
        logger: logging.Logger,
        news_limit: int,
    ) -> None:
        self._repository = repository
        self._news_service = news_service
        self._ai_service = ai_service
        self._linkedin_service = linkedin_service
        self._linkedin_token_service = linkedin_token_service
        self._logger = logger
        self._news_limit = news_limit

        self._scheduler = AsyncIOScheduler(timezone="UTC")
        self._lock = asyncio.Lock()
        self._bot: Optional[Bot] = None

    async def start(self, bot: Bot) -> None:
        self._bot = bot
        settings = await self._repository.get()

        if not self._scheduler.running:
            self._scheduler.start()

        if settings.enabled:
            self._schedule_job(settings)
            self._logger.info("Autopost scheduler resumed")

    async def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    async def enable(
        self, chat_id: int, owner_user_id: int, interval_minutes: int, style: PostStyle
    ) -> AutopostSettings:
        if interval_minutes < 30 or interval_minutes > 1440:
            raise AutopostServiceError("Interval must be between 30 and 1440 minutes")

        settings = await self._repository.get()
        settings.enabled = True
        settings.chat_id = chat_id
        settings.owner_user_id = owner_user_id
        settings.interval_minutes = interval_minutes
        settings.style = style.value

        await self._repository.save(settings)
        self._schedule_job(settings)
        return settings

    async def disable(self) -> AutopostSettings:
        settings = await self._repository.get()
        settings.enabled = False
        await self._repository.save(settings)

        self._remove_job_if_exists()
        return settings

    async def status(self) -> Tuple[AutopostSettings, Optional[datetime]]:
        settings = await self._repository.get()
        job = self._scheduler.get_job(self.JOB_ID)
        next_run = job.next_run_time if job else None
        return settings, next_run

    async def run_once(self) -> str:
        async with self._lock:
            settings = await self._repository.get()
            if settings.chat_id is None:
                raise AutopostServiceError("Autopost chat_id is not configured")
            if settings.owner_user_id is None:
                raise AutopostServiceError("Autopost owner user is not configured")

            try:
                style = PostStyle(settings.style)
            except ValueError as exc:
                raise AutopostServiceError(f"Invalid autopost style: {settings.style}") from exc
            news_items = await self._news_service.fetch_latest_news(limit=self._news_limit)
            selected_news = self._select_news_to_post(news_items, settings.last_posted_news_link)

            if selected_news is None:
                raise AutopostServiceError("No fresh news found for autopost")

            credentials = await self._linkedin_token_service.get_credentials_for_user(
                settings.owner_user_id
            )
            if not credentials:
                raise AutopostServiceError(
                    "LinkedIn account is not connected for autopost owner. Use /linkedin_connect."
                )

            try:
                generated_post = await self._ai_service.generate_post(news=selected_news, style=style)
                post_id = await self._linkedin_service.publish_post(
                    generated_post,
                    access_token=credentials.access_token,
                    person_id=credentials.person_id,
                )
            except (AIServiceError, LinkedInServiceError, ValueError) as exc:
                raise AutopostServiceError(str(exc)) from exc

            settings.last_posted_news_link = selected_news.link
            settings.last_run_epoch = int(datetime.now(tz=timezone.utc).timestamp())
            await self._repository.save(settings)

            await self._notify_chat(
                chat_id=settings.chat_id,
                message=(
                    "Автопост виконано успішно.\n"
                    f"LinkedIn ID: {post_id}\n"
                    f"Новина: {selected_news.title}"
                ),
            )
            return str(post_id)

    async def _scheduled_job(self) -> None:
        try:
            await self.run_once()
        except AutopostServiceError as exc:
            self._logger.exception("Autopost run failed: %s", exc)
            settings = await self._repository.get()
            if settings.chat_id is not None:
                await self._notify_chat(
                    chat_id=settings.chat_id,
                    message=f"Автопост завершився з помилкою: {exc}",
                )

    def _schedule_job(self, settings: AutopostSettings) -> None:
        self._remove_job_if_exists()

        if settings.chat_id is None:
            raise AutopostServiceError("Cannot schedule autopost without chat_id")

        trigger = IntervalTrigger(minutes=settings.interval_minutes, timezone="UTC")
        self._scheduler.add_job(
            self._scheduled_job,
            trigger=trigger,
            id=self.JOB_ID,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self._logger.info(
            "Autopost scheduled every %s minutes for chat %s",
            settings.interval_minutes,
            settings.chat_id,
        )

    def _remove_job_if_exists(self) -> None:
        job = self._scheduler.get_job(self.JOB_ID)
        if job:
            self._scheduler.remove_job(self.JOB_ID)

    @staticmethod
    def _select_news_to_post(
        news_items: list[NewsItem], last_link: Optional[str]
    ) -> Optional[NewsItem]:
        for item in news_items:
            if item.link != last_link:
                return item
        return None

    async def _notify_chat(self, chat_id: int, message: str) -> None:
        if self._bot is None:
            return
        try:
            await self._bot.send_message(chat_id=chat_id, text=message)
        except Exception:
            self._logger.exception("Failed to send autopost notification to chat %s", chat_id)
