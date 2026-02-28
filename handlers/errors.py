from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import ErrorEvent

router = Router(name=__name__)


@router.error()
async def global_error_handler(event: ErrorEvent) -> bool:
    logging.exception("Unhandled update error", exc_info=event.exception)

    update = event.update
    if update.message:
        await update.message.answer("Сталася внутрішня помилка. Спробуйте ще раз пізніше.")
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.answer("Помилка", show_alert=True)
        await update.callback_query.message.answer("Сталася внутрішня помилка. Спробуйте ще раз пізніше.")

    return True
