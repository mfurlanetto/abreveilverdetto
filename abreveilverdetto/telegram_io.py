"""Utilità condivise dagli handler: dipendenze, invio di media con cache dei file_id, risposte ai bottoni."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from telegram import CallbackQuery, InputFile, Message, User
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from .content import Content
from .services import Services
from .settings import Settings
from .storage import Storage

logger = logging.getLogger(__name__)


HTML = ParseMode.HTML


@dataclass
class Deps:
    settings: Settings
    content: Content
    storage: Storage
    services: Services
    rng: random.Random

    def now(self) -> datetime:
        return datetime.now(self.settings.timezone)


def deps(context: ContextTypes.DEFAULT_TYPE) -> Deps:
    return context.application.bot_data["deps"]


def display_name(user: User) -> str:
    return user.full_name or (f"@{user.username}" if user.username else str(user.id))


async def send_media(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    path: Path,
    *,
    kind: str = "photo",
    caption: str | None = None,
) -> Message:
    """Invia un file locale riusando il file_id Telegram se già caricato.

    Il primo invio carica il file; i successivi passano solo l'identificativo.
    Se il file_id non è più valido si ricarica il file.
    """
    d = deps(context)
    send = context.bot.send_photo if kind == "photo" else context.bot.send_animation
    size = (await asyncio.to_thread(path.stat)).st_size
    key = f"{kind}:{path.relative_to(d.content.media_dir).as_posix()}:{size}"

    file_id = await d.storage.get_file_id(key)
    if file_id:
        try:
            return await send(chat_id, file_id, caption=caption, parse_mode=HTML)
        except BadRequest:
            logger.info("file_id scaduto per %s, ricarico il file", key)
            await d.storage.delete_file_id(key)

    upload = InputFile(await asyncio.to_thread(path.read_bytes), filename=path.name)
    message = await send(chat_id, upload, caption=caption, parse_mode=HTML)
    sent = message.photo[-1].file_id if kind == "photo" and message.photo else None
    if kind != "photo" and message.animation:
        sent = message.animation.file_id
    elif kind != "photo" and message.document:
        sent = message.document.file_id
    if sent:
        await d.storage.set_file_id(key, sent)
    return message


async def drop_menu(query: CallbackQuery) -> None:
    """Cancella il messaggio del menu prima di rispondere con un media."""
    try:
        await query.delete_message()
    except TelegramError:
        # Messaggio già cancellato o più vecchio di 48 ore: non è un problema.
        logger.debug("Impossibile cancellare il menu", exc_info=True)


async def replace_with_media(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    path: Path,
    *,
    kind: str = "photo",
    caption: str | None = None,
) -> None:
    await drop_menu(query)
    await send_media(context, query.message.chat.id, path, kind=kind, caption=caption)


async def replace_with_remote_photo(query: CallbackQuery, url: str, caption: str) -> None:
    """Foto da URL; se Telegram non riesce a scaricarla, ripiega sul solo testo."""
    try:
        await query.get_bot().send_photo(query.message.chat.id, url, caption=caption, parse_mode=HTML)
    except BadRequest:
        logger.warning("Telegram non ha accettato la foto remota %s", url)
        await query.edit_message_text(caption, parse_mode=HTML)
        return
    await drop_menu(query)


MenuAction = Callable[[CallbackQuery, ContextTypes.DEFAULT_TYPE], Awaitable[None]]
