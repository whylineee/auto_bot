from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from keyboards import style_keyboard
from services.news_service import NewsItem
from states import PostCreationStates

router = Router(name=__name__)


@router.callback_query(F.data.startswith("news_select:"), PostCreationStates.selected_news)
async def news_selected_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.message is None:
        return

    data = await state.get_data()
    raw_items = data.get("news_items", [])

    try:
        selected_idx = int(callback.data.split(":", 1)[1])
    except (AttributeError, ValueError):
        await callback.message.answer("Некоректний вибір новини. Спробуйте ще раз через /start.")
        return

    if selected_idx < 0 or selected_idx >= len(raw_items):
        await callback.message.answer("Новину не знайдено. Запустіть /start ще раз.")
        return

    selected_news = NewsItem.model_validate(raw_items[selected_idx])
    await state.update_data(selected_news=selected_news.model_dump(mode="json"))
    await state.set_state(PostCreationStates.selected_style)

    await callback.message.answer(
        "Вибрана новина:\n\n"
        f"<b>{selected_news.title}</b>\n\n"
        f"{selected_news.summary}\n\n"
        f"🔗 {selected_news.link}\n\n"
        "Оберіть стиль поста:",
        reply_markup=style_keyboard(),
        disable_web_page_preview=True,
    )
