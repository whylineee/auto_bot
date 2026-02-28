from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.ai_service import PostStyle
from services.news_service import NewsItem


def news_keyboard(news_items: list[NewsItem]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, item in enumerate(news_items):
        title = item.title.strip()[:60]
        button_text = f"{idx + 1}. {title}" if len(item.title) > 60 else f"{idx + 1}. {item.title.strip()}"
        builder.button(text=button_text, callback_data=f"news_select:{idx}")
    builder.adjust(1)
    return builder.as_markup()


def style_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Експертний", callback_data=f"style:{PostStyle.EXPERT.value}")
    builder.button(text="🔥 Провокаційний", callback_data=f"style:{PostStyle.PROVOCATIVE.value}")
    builder.button(text="📊 Аналітичний", callback_data=f"style:{PostStyle.ANALYTICAL.value}")
    builder.button(text="🧵 Короткий", callback_data=f"style:{PostStyle.SHORT.value}")
    builder.button(text="❌ Скасувати", callback_data="cancel")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def post_actions_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Опублікувати в LinkedIn", callback_data="post_action:publish")
    builder.button(text="✏️ Перегенерувати", callback_data="post_action:regenerate")
    builder.button(text="📝 Відредагувати вручну", callback_data="post_action:edit")
    builder.button(text="❌ Скасувати", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()
