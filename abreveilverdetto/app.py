"""Costruzione dell'Application python-telegram-bot e registrazione degli handler."""

from __future__ import annotations

import logging
import random
from datetime import timedelta

from telegram import BotCommand, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.request import BaseRequest

from .commands import COMMANDS, on_menu, on_stale_button
from .commands.chat import on_text
from .content import Content
from .errors import on_error
from .registry import Registry
from .services import Services
from .settings import Settings
from .storage import Storage, create_storage
from .telegram_io import Deps

logger = logging.getLogger(__name__)

ALLOWED_UPDATES = [Update.MESSAGE, Update.CALLBACK_QUERY]


def register_handlers(app: Application, registry: Registry = COMMANDS) -> None:
    for slash in registry.slash:
        app.add_handler(CommandHandler(list(slash.names), slash.handler))

    app.add_handler(CallbackQueryHandler(on_menu, pattern=registry.menu_regex))
    for callback in registry.callbacks():
        app.add_handler(CallbackQueryHandler(callback.handler, pattern=callback.regex))
    app.add_handler(CallbackQueryHandler(on_stale_button))  # deve restare l'ultimo

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)


def bot_commands(registry: Registry = COMMANDS) -> list[BotCommand]:
    """Comandi mostrati da Telegram nell'autocompletamento (solo il primo nome di ciascuno)."""
    return [BotCommand(s.names[0], s.description) for s in registry.slash]


def build_application(
    settings: Settings,
    *,
    content: Content | None = None,
    storage: Storage | None = None,
    services: Services | None = None,
    rng: random.Random | None = None,
    bot_request: BaseRequest | None = None,
) -> Application:
    content = content or Content.load()
    storage = storage or create_storage(settings.database_url)
    services = services or Services.create(settings.http_timeout, settings.openweathermap_api_key)
    deps = Deps(settings, content, storage, services, rng or random.SystemRandom())

    async def post_init(app: Application) -> None:
        await storage.setup()
        purged = await storage.purge_games(deps.now() - timedelta(days=7))
        if purged:
            logger.info("Eliminate %d partite vecchie", purged)
        try:
            await app.bot.set_my_commands(bot_commands())
        except TelegramError:  # non indispensabile: il bot funziona anche senza
            logger.warning("Impossibile aggiornare l'elenco dei comandi su Telegram", exc_info=True)

    async def post_shutdown(app: Application) -> None:
        await services.close()
        await storage.close()

    builder = ApplicationBuilder().token(settings.telegram_token)
    if settings.telegram_api_base_url:
        base = settings.telegram_api_base_url.rstrip("/")
        builder = builder.base_url(f"{base}/bot").base_file_url(f"{base}/file/bot")
    if bot_request is not None:  # usato dai test per intercettare le chiamate alla Bot API
        builder = builder.request(bot_request)
    app = (
        builder
        # Lo stato vive nello storage, quindi gli update possono essere gestiti in parallelo
        # (una chiamata HTTP lenta non blocca più gli altri utenti).
        .concurrent_updates(8)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.bot_data["deps"] = deps
    register_handlers(app)
    return app
