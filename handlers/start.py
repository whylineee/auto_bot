from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import AppConfig
from keyboards import news_keyboard
from services.news_service import NewsService
from states import PostCreationStates

router = Router(name=__name__)


@router.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext,
    news_service: NewsService,
    config: AppConfig,
) -> None:
    await state.clear()

    try:
        news_items = await news_service.fetch_latest_news(limit=config.news_limit)
    except Exception:
        logging.exception("Failed to load news")
        await message.answer("Не вдалося завантажити новини. Спробуйте ще раз пізніше.")
        return

    if not news_items:
        await message.answer("Не знайшов релевантних новин за ключовими словами. Спробуйте /start пізніше.")
        return

    await state.update_data(
        news_items=[item.model_dump(mode="json") for item in news_items],
        selected_news=None,
        selected_style=None,
        generated_post=None,
        awaiting_manual_edit=False,
    )
    await state.set_state(PostCreationStates.selected_news)

    await message.answer(
        "Оберіть новину для генерації LinkedIn-поста:",
        reply_markup=news_keyboard(news_items),
    )
