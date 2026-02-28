from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name=__name__)


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        "Команди:\n"
        "/start - завантажити новини та згенерувати пост\n"
        "/help - список команд\n"
        "/linkedin_connect - почати OAuth авторизацію LinkedIn\n"
        "/linkedin_code <code|url> - зберегти OAuth токен\n"
        "/linkedin_status - перевірити джерело токена\n"
        "/linkedin_me - показати підключений LinkedIn акаунт\n"
        "/linkedin_disconnect - відключити OAuth токен\n"
        "/autopost_on [minutes] [style] - увімкнути автопост\n"
        "/autopost_off - вимкнути автопост\n"
        "/autopost_status - статус автопосту\n"
        "/autopost_now - виконати автопост зараз"
    )
