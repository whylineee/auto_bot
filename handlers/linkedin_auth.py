from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from services.linkedin_auth_service import LinkedInAuthService, LinkedInAuthServiceError
from services.linkedin_token_service import LinkedInTokenService

router = Router(name=__name__)


@router.message(Command(commands=["linkedin_auth", "linkedin_connect"]))
async def linkedin_auth_handler(
    message: Message,
    state: FSMContext,
    linkedin_auth_service: LinkedInAuthService,
) -> None:
    if not linkedin_auth_service.is_enabled:
        await message.answer(
            "OAuth не налаштований. Заповніть LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET і LINKEDIN_REDIRECT_URI."
        )
        return

    nonce = secrets.token_urlsafe(20)
    await state.update_data(linkedin_oauth_state=nonce)

    try:
        url = linkedin_auth_service.build_authorization_url(state=nonce)
    except LinkedInAuthServiceError as exc:
        await message.answer(f"Не вдалося сформувати OAuth URL: {exc}")
        return

    await message.answer(
        "1) Перейдіть за посиланням і авторизуйте застосунок.\n"
        "2) Після редіректу скопіюйте параметр code з URL.\n"
        "3) Надішліть: /linkedin_code <CODE>\n\n"
        f"Посилання:\n{url}",
        disable_web_page_preview=True,
    )


@router.message(Command("linkedin_code"))
async def linkedin_code_handler(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    linkedin_auth_service: LinkedInAuthService,
    linkedin_token_service: LinkedInTokenService,
) -> None:
    if message.from_user is None:
        await message.answer("Не вдалося визначити користувача Telegram.")
        return

    if not command.args:
        await message.answer("Передайте код: /linkedin_code <CODE>")
        return

    if not linkedin_auth_service.is_enabled:
        await message.answer("OAuth не налаштований у конфігу.")
        return

    code, state_from_callback = _parse_code_and_state(command.args.strip())
    if len(code) < 8:
        await message.answer("Схоже, код некоректний. Перевірте і спробуйте ще раз.")
        return

    data = await state.get_data()
    expected_state = str(data.get("linkedin_oauth_state", "")).strip()
    if expected_state and state_from_callback and state_from_callback != expected_state:
        await message.answer("OAuth state не співпадає. Запустіть /linkedin_auth ще раз.")
        return

    try:
        token = await linkedin_auth_service.exchange_code_for_token(code=code)
        me = await linkedin_auth_service.get_user_info(token.access_token)
        await linkedin_token_service.store_oauth_account(
            telegram_user_id=message.from_user.id,
            oauth_token=token,
            person_id=me.sub,
            name=me.name,
            email=me.email,
        )
    except LinkedInAuthServiceError as exc:
        await message.answer(f"Помилка OAuth обміну: {exc}")
        return

    expires_at = datetime.fromtimestamp(token.expires_at_epoch, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
    await message.answer(
        "LinkedIn OAuth токен збережено.\n"
        f"Профіль: {me.name or me.sub}\n"
        f"Дійсний до: {expires_at}\n"
        "Тепер можна публікувати пости."
    )
    await state.update_data(linkedin_oauth_state=None)


@router.message(Command("linkedin_status"))
async def linkedin_status_handler(
    message: Message,
    linkedin_token_service: LinkedInTokenService,
) -> None:
    if message.from_user is None:
        await message.answer("Не вдалося визначити користувача Telegram.")
        return

    source = await linkedin_token_service.token_source(message.from_user.id)
    expires_at_epoch = await linkedin_token_service.get_expires_at(message.from_user.id)

    if source == "oauth" and expires_at_epoch:
        expires_at = datetime.fromtimestamp(expires_at_epoch, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        await message.answer(f"LinkedIn токен: OAuth\nДійсний до: {expires_at}")
        return

    if source == "env":
        await message.answer("LinkedIn токен: з .env (LINKEDIN_ACCESS_TOKEN)")
        return

    await message.answer("LinkedIn токен не налаштований. Використайте /linkedin_connect")


@router.message(Command("linkedin_disconnect"))
async def linkedin_disconnect_handler(
    message: Message,
    linkedin_token_service: LinkedInTokenService,
) -> None:
    if message.from_user is None:
        await message.answer("Не вдалося визначити користувача Telegram.")
        return

    await linkedin_token_service.clear_oauth_account(message.from_user.id)
    await message.answer(
        "Ваш OAuth токен видалено.\n"
        "Якщо в .env є LINKEDIN_ACCESS_TOKEN, бот продовжить використовувати його."
    )


@router.message(Command("linkedin_me"))
async def linkedin_me_handler(
    message: Message,
    linkedin_token_service: LinkedInTokenService,
    linkedin_auth_service: LinkedInAuthService,
) -> None:
    if message.from_user is None:
        await message.answer("Не вдалося визначити користувача Telegram.")
        return

    credentials = await linkedin_token_service.get_credentials_for_user(message.from_user.id)
    if not credentials:
        await message.answer("LinkedIn токен не знайдено. Підключіть акаунт: /linkedin_connect")
        return

    try:
        me = await linkedin_auth_service.get_user_info(credentials.access_token)
    except LinkedInAuthServiceError as exc:
        await message.answer(f"Не вдалося отримати профіль LinkedIn: {exc}")
        return

    await message.answer(
        "Підключений LinkedIn акаунт:\n"
        f"ID: {me.sub}\n"
        f"Ім'я: {me.name or '-'}\n"
        f"Email: {me.email or '-'}\n"
        f"Джерело токена: {credentials.source}"
    )


def _parse_code_and_state(raw_args: str) -> Tuple[str, Optional[str]]:
    candidate = raw_args.strip()
    if candidate.startswith("http://") or candidate.startswith("https://"):
        parsed = urlparse(candidate)
        query = parse_qs(parsed.query)
        code = (query.get("code", [""])[0] or "").strip()
        state = (query.get("state", [""])[0] or "").strip() or None
        return code, state
    return candidate, None
