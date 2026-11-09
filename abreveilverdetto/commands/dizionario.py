"""Parola a caso dal Wikizionario con la sua definizione (contenuti CC BY-SA 4.0)."""

from __future__ import annotations

from telegram import CallbackQuery, LinkPreviewOptions
from telegram.ext import ContextTypes

from ..services import RateLimitedError
from ..telegram_io import HTML, deps
from ..text import esc
from ..wiktionary import LICENSE_URL, Entry

MAX_DEFINITIONS = 3
MAX_DEFINITION_CHARS = 300
RATE_LIMITED_TEXT = "📖 Il Wikizionario mi chiede di rallentare: riprova tra un minuto."


def _shorten(text: str) -> str:
    if len(text) <= MAX_DEFINITION_CHARS:
        return text
    return text[: MAX_DEFINITION_CHARS - 1].rsplit(" ", 1)[0] + "…"


def format_entry(entry: Entry) -> str:
    """Parola, categoria grammaticale, al massimo 3 definizioni e attribuzione obbligatoria."""
    lines = [f"📖 <b>{esc(entry.title.upper())}</b>"]
    shown = 0
    for sense in entry.senses:
        if shown >= MAX_DEFINITIONS:
            break
        lines.append(f"<i>{esc(sense.pos)}</i>")
        for definition in sense.definitions[: MAX_DEFINITIONS - shown]:
            shown += 1
            lines.append(f"{shown}. {esc(_shorten(definition))}")
    # Attribuzione richiesta dalla licenza CC BY-SA 4.0: fonte (link alla voce) e licenza.
    lines.append("")
    lines.append(f'Fonte: <a href="{esc(entry.url)}">Wikizionario</a> · <a href="{LICENSE_URL}">CC BY-SA 4.0</a>')
    return "\n".join(lines)


async def parola(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    try:
        entries = await d.services.random_words()
    except RateLimitedError:
        await query.edit_message_text(RATE_LIMITED_TEXT)
        return
    await query.edit_message_text(
        format_entry(d.rng.choice(entries)),
        parse_mode=HTML,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
