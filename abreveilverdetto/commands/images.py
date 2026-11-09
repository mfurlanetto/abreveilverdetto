"""Comandi che inviano immagini locali, compreso Magic."""

from __future__ import annotations

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .. import emoji
from ..content import MAGIC_DECKS
from ..registry import Callback
from ..telegram_io import HTML, deps, replace_with_media
from ..text import esc


async def torta(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    await replace_with_media(query, context, d.content.pick_image("tortamele", d.rng))


async def conte(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    caption = esc(d.content.pick_text("conte", d.rng))
    await replace_with_media(query, context, d.content.pick_image("conte", d.rng), caption=caption)


async def bimbe(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    hearts = list(emoji.love.values())
    caption = "".join(d.rng.choice(hearts) for _ in range(3))
    await replace_with_media(query, context, d.content.pick_image("bimbe", d.rng), caption=caption)


async def santi(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    santo = d.rng.choice(d.content.santi)
    caption = (
        f"<b>{esc(santo['name'].upper())}</b>\n"
        f"<i>{esc(santo['func'])}</i>\n"
        f"{esc(d.content.pick_text('santi_frasi', d.rng))}"
    )
    await replace_with_media(query, context, d.content.media(f"santi/{santo['photo']}.jpg"), caption=caption)


async def magic(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [
        InlineKeyboardButton(f"{icon}{label.upper()}", callback_data=MAGIC_PICK.data(key))
        for key, (icon, label, _) in MAGIC_DECKS.items()
    ]
    buttons.append(InlineKeyboardButton("ℹ INFO", callback_data=MAGIC_PICK.data("info")))
    keyboard = InlineKeyboardMarkup([buttons[:3], buttons[3:]])
    await query.edit_message_text("Choose Card Type", reply_markup=keyboard)


async def on_magic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    d = deps(context)
    choice = query.data.split(":", 1)[1]
    if choice == "info":
        lines = ["<b>DECKS</b>"] + [
            f"{icon} <i>{label}</i>: {len(d.content.images[directory])}"
            for icon, label, directory in MAGIC_DECKS.values()
        ]
        await query.edit_message_text("\n".join(lines), parse_mode=HTML)
        return
    _, _, directory = MAGIC_DECKS[choice]
    await replace_with_media(query, context, d.content.pick_image(directory, d.rng))


MAGIC_PICK = Callback("magic", "|".join([*MAGIC_DECKS, "info"]), on_magic)
