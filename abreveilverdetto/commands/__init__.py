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
from .dizionario import parola, parola_command
from .external import cocktail, comune, covid, nazione, pokemon
from .fibonacci import fibonacci_command, fibonacci_menu
from .images import MAGIC_PICK, bimbe, conte, magic, santi, torta
from .quotes import CTS_SIZE, cts, lercio, quote_action, saluti
from .trombin import trombin

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
        MenuCommand("saluti", "👋 SALUTI", saluti, row=0),
        MenuCommand("cts", "🔬 CTS", cts, row=0, callbacks=(CTS_SIZE,)),
        MenuCommand("dpcm", "📜 DPCM", quote_action("dpcm"), row=0),
        MenuCommand("conte", "🙇 CONTE", conte, row=1),
        MenuCommand("bimbe", "😻 BIMBE", bimbe, row=1),
        MenuCommand("comune", "🏙 COMUNE", comune, row=1),
        MenuCommand("covid", "🧪 COVID", covid, row=2),
        MenuCommand("giurato", "🤦 GIURATO", quote_action("giurato"), row=2),
        MenuCommand("torta", "🥧 TORTA", torta, row=2),
        MenuCommand("fibonacci", "🔢 FIBONACCI", fibonacci_menu, row=3),
        MenuCommand("c100", "💯 💯 💯", c100_menu, row=3, callbacks=(C100_ANSWER,)),
        MenuCommand("ghesboro", "🦁 GHESBORO", quote_action("ghesboro"), row=3),
        MenuCommand("pokemon", "🦕 POKEMON", pokemon, row=4),
        MenuCommand("nazione", "🌍 NAZIONE", nazione, row=4),
        MenuCommand("cocktail", "🍸 COCKTAIL", cocktail, row=5),
        MenuCommand("santi", "👼 SANTI", santi, row=5),
        MenuCommand("magic", "🃏 MAGIC", magic, row=5, callbacks=(MAGIC_PICK,)),
        MenuCommand("lercio", "📰 LERCIO.IT", lercio, row=6),
        MenuCommand("parola", "📖 PAROLA", parola, row=6),
    ),
    slash=(
        SlashCommand(("start", "menu"), start, "Apri il menu dei comandi"),
        SlashCommand(("fibonacci",), fibonacci_command, "Sequenza di Fibonacci casuale (max 10)"),
        SlashCommand(("bravitutti",), bravitutti, "Classifica di 💯💯💯 in questa chat"),
        SlashCommand(("parola",), parola_command, "Parola a caso dal Wikizionario con definizione"),
        SlashCommand(("trombin",), trombin, "Indici di borsa e materie prime"),
    ),
)
