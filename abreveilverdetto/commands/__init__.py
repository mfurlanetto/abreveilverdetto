"""Comandi del bot e registro unico ``COMMANDS``.

I comandi sono divisi per tipo nei moduli di questo pacchetto; qui si dichiara
il menu (ordine, righe, etichette) e i comandi slash. Menu, routing e
registrazione degli handler derivano da ``COMMANDS`` (vedi registry.py).
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..registry import MenuCommand, Registry, SlashCommand
from .centocento import C100_ANSWER, bravitutti, c100_menu
from .dizionario import parola
from .external import cocktail, comune, covid, nazione, pokemon
from .fibonacci import fibonacci_command, fibonacci_menu
from .images import MAGIC_PICK, bimbe, conte, magic, santi, torta
from .quotes import CTS_SIZE, cts, lercio, quote_action, saluti

logger = logging.getLogger(__name__)


def menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(c.label, callback_data=c.callback_data) for c in row] for row in COMMANDS.layout()]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("Seleziona comando:", reply_markup=menu_keyboard())


async def on_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]
    command = COMMANDS.get(key)
    if command is None:  # bottone di un menu precedente a una modifica del registro
        await query.edit_message_text("Comando sconosciuto. Usa /start.")
        return
    logger.info("Comando %s", key)
    await command.action(query, context)


async def on_stale_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bottoni di vecchi menu (versione precedente del bot o formati sconosciuti)."""
    await update.callback_query.answer("Menu scaduto: usa /start", show_alert=False)


# L'ordine delle voci con lo stesso ``row`` è l'ordine dei bottoni nella riga.
COMMANDS = Registry(
    menu=(
        MenuCommand("saluti", "👋 saluti", saluti, row=0),
        MenuCommand("cts", "🔬 cts", cts, row=0, callbacks=(CTS_SIZE,)),
        MenuCommand("dpcm", "📜 dpcm", quote_action("dpcm"), row=0),
        MenuCommand("conte", "🙇 conte", conte, row=1),
        MenuCommand("bimbe", "😻 bimbe", bimbe, row=1),
        MenuCommand("comune", "🏙 comune", comune, row=1),
        MenuCommand("covid", "🧪 covid", covid, row=2),
        MenuCommand("giurato", "🤦 giurato", quote_action("giurato"), row=2),
        MenuCommand("torta", "🥧 torta", torta, row=2),
        MenuCommand("fibonacci", "🔢 fibonacci", fibonacci_menu, row=3),
        MenuCommand("c100", "💯 💯 💯", c100_menu, row=3, callbacks=(C100_ANSWER,)),
        MenuCommand("ghesboro", "🦁 ghesboro", quote_action("ghesboro"), row=3),
        MenuCommand("pokemon", "🦕 pokemon", pokemon, row=4),
        MenuCommand("nazione", "🌍 nazione", nazione, row=4),
        MenuCommand("cocktail", "🍸 cocktail", cocktail, row=5),
        MenuCommand("santi", "👼 santi", santi, row=5),
        MenuCommand("magic", "🃏 Magic", magic, row=5, callbacks=(MAGIC_PICK,)),
        MenuCommand("lercio", "📰 Lercio.it", lercio, row=6),
        MenuCommand("parola", "📖 parola", parola, row=6),
    ),
    slash=(
        SlashCommand(("start", "menu"), start, "Apri il menu dei comandi"),
        SlashCommand(("fibonacci",), fibonacci_command, "Sequenza di Fibonacci casuale (max 10)"),
        SlashCommand(("bravitutti",), bravitutti, "Classifica di 💯💯💯 in questa chat"),
    ),
)
