from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards import post_actions_keyboard
from services.ai_service import AIService, AIServiceError, PostStyle
from services.linkedin_service import LinkedInService, LinkedInServiceError
from services.linkedin_token_service import LinkedInTokenService
from services.news_service import NewsItem
from states import PostCreationStates

router = Router(name=__name__)


@router.callback_query(F.data == "cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    if callback.message is not None:
        await callback.message.answer("Операцію скасовано. Щоб почати знову, надішліть /start")


@router.callback_query(F.data.startswith("style:"), PostCreationStates.selected_style)
async def style_selected_handler(
    callback: CallbackQuery,
    state: FSMContext,
    ai_service: AIService,
) -> None:
    await callback.answer("Генерую пост...")
    if callback.message is None:
        return

    data = await state.get_data()
    selected_news_raw = data.get("selected_news")
    if not selected_news_raw:
        await callback.message.answer("Дані новини втрачені. Запустіть /start ще раз.")
        await state.clear()
        return

    try:
        style_value = callback.data.split(":", 1)[1]
        style = PostStyle(style_value)
        selected_news = NewsItem.model_validate(selected_news_raw)
    except (ValueError, AttributeError):
        await callback.message.answer("Некоректний стиль. Спробуйте ще раз.")
        return

    await _generate_and_show_post(
        message=callback.message,
        state=state,
        ai_service=ai_service,
        news=selected_news,
        style=style,
    )


@router.callback_query(F.data == "post_action:regenerate", PostCreationStates.generated_post)
async def regenerate_handler(
    callback: CallbackQuery,
    state: FSMContext,
    ai_service: AIService,
) -> None:
    await callback.answer("Перегенерую...")
    if callback.message is None:
        return

    data = await state.get_data()
    selected_news_raw = data.get("selected_news")
    selected_style_raw = data.get("selected_style")

    if not selected_news_raw or not selected_style_raw:
        await callback.message.answer("Контекст втрачено. Запустіть /start ще раз.")
        await state.clear()
        return

    selected_news = NewsItem.model_validate(selected_news_raw)
    style = PostStyle(selected_style_raw)

    await _generate_and_show_post(
        message=callback.message,
        state=state,
        ai_service=ai_service,
        news=selected_news,
        style=style,
    )


@router.callback_query(F.data == "post_action:edit", PostCreationStates.generated_post)
async def edit_post_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.message is None:
        return
    await state.update_data(awaiting_manual_edit=True)
    await callback.message.answer(
        "Надішліть нову версію поста одним повідомленням. Після цього зможете опублікувати або перегенерувати."
    )


@router.message(PostCreationStates.generated_post)
async def manual_edit_message_handler(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("awaiting_manual_edit", False):
        return

    if not message.text or len(message.text.strip()) < 50:
        await message.answer("Текст занадто короткий. Надішліть змістовний варіант поста.")
        return

    edited_post = message.text.strip()
    await state.update_data(generated_post=edited_post, awaiting_manual_edit=False)

    await message.answer(
        "Оновлений пост збережено:\n\n"
        f"{edited_post}",
        reply_markup=post_actions_keyboard(),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "post_action:publish", PostCreationStates.generated_post)
async def publish_handler(
    callback: CallbackQuery,
    state: FSMContext,
    linkedin_service: LinkedInService,
    linkedin_token_service: LinkedInTokenService,
) -> None:
    await callback.answer("Публікую...")
    if callback.message is None or callback.from_user is None:
        return

    data = await state.get_data()
    post_text = data.get("generated_post")
    if not post_text:
        await callback.message.answer("Не знайдено текст для публікації. Запустіть /start ще раз.")
        await state.clear()
        return

    try:
        credentials = await linkedin_token_service.get_credentials_for_user(callback.from_user.id)
        if not credentials:
            await callback.message.answer(
                "LinkedIn акаунт не підключено. Спочатку виконайте /linkedin_connect"
            )
            return

        post_id = await linkedin_service.publish_post(
            text=post_text,
            access_token=credentials.access_token,
            person_id=credentials.person_id,
        )
    except LinkedInServiceError as exc:
        logging.exception("LinkedIn publish failed")
        await callback.message.answer(f"Помилка публікації в LinkedIn: {exc}")
        return

    await state.clear()
    await callback.message.answer(
        "Пост успішно опубліковано в LinkedIn.\n"
        f"ID: {post_id}\n\n"
        "Щоб створити новий пост, надішліть /start"
    )


async def _generate_and_show_post(
    message: Message,
    state: FSMContext,
    ai_service: AIService,
    news: NewsItem,
    style: PostStyle,
) -> None:
    try:
        generated = await ai_service.generate_post(news=news, style=style)
    except AIServiceError as exc:
        logging.exception("AI generation failed")
        await message.answer(f"Не вдалося згенерувати пост: {exc}")
        return

    await state.update_data(
        selected_news=news.model_dump(mode="json"),
        selected_style=style.value,
        generated_post=generated,
        awaiting_manual_edit=False,
    )
    await state.set_state(PostCreationStates.generated_post)

    await message.answer(
        f"{generated}",
        reply_markup=post_actions_keyboard(),
        disable_web_page_preview=True,
    )
