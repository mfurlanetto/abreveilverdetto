"""Fibonacci: dal menu (con ForceReply) e come /fibonacci N."""

from __future__ import annotations

from telegram import CallbackQuery, ForceReply, Message, Update
from telegram.ext import ContextTypes

from .. import game
from ..telegram_io import HTML, deps, drop_menu
from ..text import esc

FIBONACCI_PROMPT = "Fibonacci: numero massimo di iterazioni (1-10)?"


async def fibonacci_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    await drop_menu(query)
    user = query.from_user
    # ForceReply(selective) + menzione: in un gruppo il campo risposta si apre solo a chi ha cliccato.
    await context.bot.send_message(
        query.message.chat.id,
        f"{user.mention_html()} {esc(FIBONACCI_PROMPT)}",
        parse_mode=HTML,
        reply_markup=ForceReply(selective=True, input_field_placeholder="1-10"),
    )


async def fibonacci_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    raw = " ".join(context.args) if context.args else str(game.MAX_FIBONACCI)
    await update.effective_message.reply_text(esc(game.fibonacci_reply(raw, d.rng)), parse_mode=HTML)


async def fibonacci_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    await update.effective_message.reply_text(
        esc(game.fibonacci_reply(update.effective_message.text, d.rng)), parse_mode=HTML
    )


def is_fibonacci_answer(message: Message, bot_id: int) -> bool:
    replied = message.reply_to_message
    return bool(
        replied
        and replied.from_user
        and replied.from_user.id == bot_id
        and replied.text
        and replied.text.endswith(FIBONACCI_PROMPT)
    )
