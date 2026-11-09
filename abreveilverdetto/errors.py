"""Gestione centralizzata degli errori degli handler."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


GENERIC_ERROR = "Qualcosa è andato storto 🙈 Riprova tra poco."


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Nel log solo identificativi, non l'intero Update (contiene dati personali).
    where = ""
    if isinstance(update, Update):
        where = (
            f" (update_id={update.update_id}, chat_id={update.effective_chat.id if update.effective_chat else None})"
        )
    logger.error("Errore durante la gestione di un update%s", where, exc_info=context.error)

    if not isinstance(update, Update):
        return
    try:
        if update.callback_query:
            await update.callback_query.answer(GENERIC_ERROR, show_alert=True)
        elif update.effective_message:
            await update.effective_message.reply_text(GENERIC_ERROR)
    except TelegramError:
        logger.debug("Impossibile notificare l'errore all'utente", exc_info=True)
