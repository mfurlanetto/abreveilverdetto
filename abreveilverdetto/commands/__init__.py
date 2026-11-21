"""Comandi del bot e registro unico ``COMMANDS``.

I comandi sono divisi per tipo nei moduli di questo pacchetto; qui si dichiara
il menu (ordine, righe, etichette) e i comandi slash. Menu, routing e
registrazione degli handler derivano da ``COMMANDS`` (vedi registry.py).
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..registry import MAIN, MenuCommand, Registry, SlashCommand
from .accadde import accadde_oggi
from .centocento import C100_ANSWER, bravitutti, c100_menu
from .dizionario import parola
from .duello import DUEL_ACTION, duello_menu
from .external import cocktail, comune, covid, nazione, pokemon
from .fibonacci import fibonacci_menu
from .images import MAGIC_PICK, bimbe, conte, magic, santi, torta
from .montagna import montagna
from .morra import MORRA_ACTION, morra_menu
from .quotes import CTS_SIZE, cts, lercio, quote_action, saluti
from .trombin import trombin

logger = logging.getLogger(__name__)


BACK_LABEL = "⬅ INDIETRO"
MENU_TEXT = "Seleziona comando:"


def menu_keyboard(group: str = MAIN) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(c.label, callback_data=c.callback_data) for c in row] for row in COMMANDS.layout(group)
    ]
    if group != MAIN:
        rows.append([InlineKeyboardButton(BACK_LABEL, callback_data=f"menu:{MAIN}")])
    return InlineKeyboardMarkup(rows)


def submenu(group: str, text: str):
    """Azione di un bottone che apre un sottomenu nello stesso messaggio."""

    async def action(query, context: ContextTypes.DEFAULT_TYPE) -> None:
        await query.edit_message_text(text, reply_markup=menu_keyboard(group))

    return action


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(MENU_TEXT, reply_markup=menu_keyboard())


async def on_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]
    if key == MAIN:  # bottone "indietro" di un sottomenu
        await query.edit_message_text(MENU_TEXT, reply_markup=menu_keyboard())
        return
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
        MenuCommand("giochi", "🎮 GIOCHI", submenu("giochi", "🎮 Scegli un gioco:"), row=3, opens="giochi"),
        MenuCommand("ghesboro", "🦁 GHESBORO", quote_action("ghesboro"), row=3),
        MenuCommand("pokemon", "🦕 POKEMON", pokemon, row=4),
        MenuCommand("nazione", "🌍 NAZIONE", nazione, row=4),
        MenuCommand("cocktail", "🍸 COCKTAIL", cocktail, row=5),
        MenuCommand("santi", "👼 SANTI", santi, row=5),
        MenuCommand("magic", "🃏 MAGIC", magic, row=5, callbacks=(MAGIC_PICK,)),
        MenuCommand("lercio", "📰 LERCIO.IT", lercio, row=6),
        MenuCommand("parola", "📖 PAROLA", parola, row=6),
        MenuCommand("accaddeoggi", "📅 ACCADDE OGGI", accadde_oggi, row=6),
        MenuCommand("trombin", "📈 TROMBIN", trombin, row=7),
        MenuCommand("montagna", "⛰ MONTAGNA", montagna, row=4),
        # Sottomenu 🎮 GIOCHI
        MenuCommand("morra", "✊ MORRA", morra_menu, row=0, callbacks=(MORRA_ACTION,), group="giochi"),
        MenuCommand("duello", "🔫 DUELLO", duello_menu, row=0, callbacks=(DUEL_ACTION,), group="giochi"),
        MenuCommand("c100", "💯 💯 💯", c100_menu, row=0, callbacks=(C100_ANSWER,), group="giochi"),
    ),
    # Solo i comandi senza pulsante: /start apre il menu, /bravitutti è solo slash per scelta.
    slash=(
        SlashCommand(("start", "menu"), start, "Apri il menu dei comandi"),
        SlashCommand(("bravitutti",), bravitutti, "Classifiche di 💯💯💯, morra e duello in questa chat"),
    ),
)
