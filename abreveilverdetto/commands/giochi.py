"""🎮 GIOCHI: sottomenu dei giochi e scadenze comuni (morra, duello) per il timer."""

from __future__ import annotations

from datetime import datetime

from telegram import Bot

from ..telegram_io import Deps
from .duello import on_duel_deadline
from .morra import expire_due_games


async def process_deadlines(bot: Bot, d: Deps, now: datetime) -> datetime | None:
    """Azione del timer: gestisce le scadenze di tutti i giochi e restituisce la successiva."""
    following = [await expire_due_games(bot, d, now), await on_duel_deadline(bot, d, now)]
    return min((t for t in following if t is not None), default=None)


async def next_deadline(d: Deps) -> datetime | None:
    following = [await d.storage.next_morra_deadline(), await d.storage.next_duel_deadline()]
    return min((t for t in following if t is not None), default=None)
