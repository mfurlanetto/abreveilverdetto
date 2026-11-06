"""Costruzione dell'Application python-telegram-bot e registrazione degli handler."""

from __future__ import annotations

import logging
import random
from datetime import timedelta

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.request import BaseRequest

from . import handlers
from .content import MAGIC_DECKS, Content
from .services import Services
from .settings import Settings
from .storage import Storage, create_storage

logger = logging.getLogger(__name__)

ALLOWED_UPDATES = [Update.MESSAGE, Update.CALLBACK_QUERY]


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler(["start", "menu"], handlers.start))
    app.add_handler(CommandHandler("fibonacci", handlers.fibonacci_command))
    app.add_handler(CommandHandler("bravitutti", handlers.bravitutti))

    app.add_handler(CallbackQueryHandler(handlers.on_menu, pattern=r"^menu:[a-z0-9]+$"))
    app.add_handler(CallbackQueryHandler(handlers.on_cts, pattern=r"^cts:(5|10)$"))
    decks = "|".join([*MAGIC_DECKS, "info"])
    app.add_handler(CallbackQueryHandler(handlers.on_magic, pattern=rf"^magic:({decks})$"))
    app.add_handler(CallbackQueryHandler(handlers.on_c100, pattern=r"^c100:\d+:[yn]$"))
    app.add_handler(CallbackQueryHandler(handlers.on_stale_button))  # deve restare l'ultimo

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text))
    app.add_error_handler(handlers.on_error)


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
    deps = handlers.Deps(settings, content, storage, services, rng or random.SystemRandom())

    async def post_init(app: Application) -> None:
        await storage.setup()
        purged = await storage.purge_games(deps.now() - timedelta(days=7))
        if purged:
            logger.info("Eliminate %d partite vecchie", purged)

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
