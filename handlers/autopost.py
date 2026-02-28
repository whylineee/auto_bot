from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from config import AppConfig
from services.ai_service import PostStyle
from services.autopost_service import AutopostService, AutopostServiceError
from services.linkedin_token_service import LinkedInTokenService

router = Router(name=__name__)

_STYLE_ALIASES: dict[str, PostStyle] = {
    "expert": PostStyle.EXPERT,
    "експертний": PostStyle.EXPERT,
    "provocative": PostStyle.PROVOCATIVE,
    "провокаційний": PostStyle.PROVOCATIVE,
    "analytical": PostStyle.ANALYTICAL,
    "аналітичний": PostStyle.ANALYTICAL,
    "short": PostStyle.SHORT,
    "короткий": PostStyle.SHORT,
}


@router.message(Command("autopost_on"))
async def autopost_on_handler(
    message: Message,
    command: CommandObject,
    autopost_service: AutopostService,
    linkedin_token_service: LinkedInTokenService,
    config: AppConfig,
) -> None:
    if message.chat is None or message.from_user is None:
        return

    token_source = await linkedin_token_service.token_source(message.from_user.id)
    if token_source == "none":
        await message.answer("Спочатку підключіть LinkedIn: /linkedin_connect")
        return

    interval_minutes, style = _parse_autopost_args(
        raw_args=command.args or "",
        default_interval=config.autopost_default_interval_minutes,
        default_style=config.autopost_default_style,
    )
    if interval_minutes is None or style is None:
        await message.answer(
            "Некоректні аргументи.\n"
            "Приклад: /autopost_on 180 analytical\n"
            "Стилі: expert, provocative, analytical, short"
        )
        return

    try:
        settings = await autopost_service.enable(
            chat_id=message.chat.id,
            owner_user_id=message.from_user.id,
            interval_minutes=interval_minutes,
            style=style,
        )
    except AutopostServiceError as exc:
        await message.answer(f"Не вдалося увімкнути автопост: {exc}")
        return

    _, next_run = await autopost_service.status()
    next_run_text = _format_dt(next_run)

    await message.answer(
        "Автопост увімкнено.\n"
        f"Інтервал: {settings.interval_minutes} хв\n"
        f"Стиль: {settings.style}\n"
        f"Наступний запуск: {next_run_text}"
    )


@router.message(Command("autopost_off"))
async def autopost_off_handler(
    message: Message,
    autopost_service: AutopostService,
) -> None:
    await autopost_service.disable()
    await message.answer("Автопост вимкнено.")


@router.message(Command("autopost_status"))
async def autopost_status_handler(
    message: Message,
    autopost_service: AutopostService,
) -> None:
    settings, next_run = await autopost_service.status()

    if not settings.enabled:
        await message.answer("Автопост: вимкнено")
        return

    await message.answer(
        "Автопост: увімкнено\n"
        f"Chat ID: {settings.chat_id}\n"
        f"Owner User ID: {settings.owner_user_id}\n"
        f"Інтервал: {settings.interval_minutes} хв\n"
        f"Стиль: {settings.style}\n"
        f"Наступний запуск: {_format_dt(next_run)}"
    )


@router.message(Command("autopost_now"))
async def autopost_now_handler(
    message: Message,
    autopost_service: AutopostService,
) -> None:
    try:
        post_id = await autopost_service.run_once()
    except AutopostServiceError as exc:
        await message.answer(f"Автопост не виконано: {exc}")
        return

    await message.answer(f"Автопост виконано. LinkedIn ID: {post_id}")


def _parse_autopost_args(
    raw_args: str,
    default_interval: int,
    default_style: str,
) -> Tuple[Optional[int], Optional[PostStyle]]:
    args = [part.strip().lower() for part in raw_args.split() if part.strip()]

    interval = default_interval
    style_key = default_style.strip().lower()

    if len(args) == 1:
        if args[0].isdigit():
            interval = int(args[0])
        else:
            style_key = args[0]

    if len(args) >= 2:
        if not args[0].isdigit():
            return None, None
        interval = int(args[0])
        style_key = args[1]

    style = _STYLE_ALIASES.get(style_key)
    return interval, style


def _format_dt(dt: Optional[datetime]) -> str:
    if dt is None:
        return "-"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
