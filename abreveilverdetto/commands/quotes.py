"""Comandi di testo: frasi a caso e CTS."""

from __future__ import annotations

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..registry import Callback
from ..telegram_io import HTML, MenuAction, deps
from ..text import esc, greeting


async def saluti(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    template = d.content.pick_text("saluti", d.rng)
    text = template.format(greeting(d.now(), query.from_user.first_name))
    await query.edit_message_text(esc(text), parse_mode=HTML)


def quote_action(list_name: str, prefix: str = "") -> MenuAction:
    async def action(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
        d = deps(context)
        text = d.content.pick_text(list_name, d.rng)
        await query.edit_message_text(f"{prefix}<i>“{esc(text)}”</i>", parse_mode=HTML)

    return action


async def lercio(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    text = d.content.pick_text("lercio", d.rng)
    await query.edit_message_text(f"+++ 🔴 ULTIM'ORA: {esc(text)}", parse_mode=HTML)


async def cts(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(str(n), callback_data=CTS_SIZE.data(n)) for n in CTS_SIZES]])
    await query.edit_message_text("Quanti membri desideri?", reply_markup=keyboard)


async def on_cts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    d = deps(context)
    members = d.content.texts["cts_list"]
    size = min(int(query.data.split(":", 1)[1]), len(members))
    lines = ["<b>Comitato Tecnico-Scientifico</b>"] + [f"∘ {esc(m)}" for m in d.rng.sample(members, size)]
    await query.edit_message_text("\n".join(lines), parse_mode=HTML)


CTS_SIZES = (5, 10)
CTS_SIZE = Callback("cts", "|".join(map(str, CTS_SIZES)), on_cts)
