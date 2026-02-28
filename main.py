from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import load_config
from container import ServiceContainer, ServicesMiddleware
from handlers.autopost import router as autopost_router
from handlers.errors import router as errors_router
from handlers.help import router as help_router
from handlers.linkedin_auth import router as linkedin_auth_router
from handlers.news import router as news_router
from handlers.post_generation import router as post_generation_router
from handlers.start import router as start_router


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def run() -> None:
    config = load_config()
    setup_logging(config.log_level)

    logger = logging.getLogger("auto-bot")
    container = ServiceContainer(config=config, logger=logger)

    bot = Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    try:
        dp = Dispatcher()
        dp.update.middleware(ServicesMiddleware(container))

        dp.include_router(start_router)
        dp.include_router(help_router)
        dp.include_router(linkedin_auth_router)
        dp.include_router(autopost_router)
        dp.include_router(news_router)
        dp.include_router(post_generation_router)
        dp.include_router(errors_router)

        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Згенерувати пост із новини"),
                BotCommand(command="help", description="Список команд"),
                BotCommand(command="linkedin_connect", description="Підключити LinkedIn акаунт"),
                BotCommand(command="linkedin_status", description="Статус LinkedIn токена"),
                BotCommand(command="linkedin_me", description="Поточний LinkedIn акаунт"),
                BotCommand(command="linkedin_disconnect", description="Відключити LinkedIn OAuth"),
                BotCommand(command="autopost_on", description="Увімкнути автопост"),
                BotCommand(command="autopost_off", description="Вимкнути автопост"),
                BotCommand(command="autopost_status", description="Статус автопосту"),
                BotCommand(command="autopost_now", description="Запустити автопост зараз"),
            ]
        )

        try:
            await container.autopost_service.start(bot)
        except Exception:
            logger.exception("Autopost scheduler failed to start")

        logger.info("Bot started")
        await dp.start_polling(bot)
    finally:
        await container.close()
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(run())
