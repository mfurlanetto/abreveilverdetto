"""Messaggi liberi: risposte a Fibonacci e la briscola del 15 e 18."""

from __future__ import annotations

import re

from telegram import Update
from telegram.ext import ContextTypes

from ..telegram_io import deps, send_media
from ..text import esc
from .fibonacci import fibonacci_answer, is_fibonacci_answer

BRISCOLA = "Come fa 15+18 non fa 36 dio te maledica te do 'n sciafon che te copo d** ***"
_FIFTEEN = re.compile(r"(?<!\d)15(?!\d)")
_EIGHTEEN = re.compile(r"(?<!\d)18(?!\d)")


def mentions_15_and_18(text: str) -> bool:
    return bool(_FIFTEEN.search(text) and _EIGHTEEN.search(text))


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if is_fibonacci_answer(message, context.bot.id):
        await fibonacci_answer(update, context)
        return
    if mentions_15_and_18(message.text):
        d = deps(context)
        await send_media(context, message.chat.id, d.content.media("others/15e18.png"), caption=esc(BRISCOLA))
