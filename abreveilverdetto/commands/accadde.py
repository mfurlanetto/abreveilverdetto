"""📅 ACCADDE OGGI: eventi in evidenza del giorno da Wikipedia (contenuti CC BY-SA 4.0)."""

from __future__ import annotations

from datetime import date

from telegram import CallbackQuery, LinkPreviewOptions
from telegram.ext import ContextTypes

from ..onthisday import LICENSE_URL, Event, day_label, day_page_url
from ..services import RateLimitedError
from ..telegram_io import HTML, deps
from ..text import esc

RATE_LIMITED_TEXT = "📅 Wikipedia mi chiede di rallentare: riprova tra un minuto."


def format_events(events: list[Event], today: date) -> str:
    title = f"📅 <b>ACCADDE OGGI</b> · {esc(day_label(today.month, today.day))}"
    if events:
        body = "\n".join(f"<b>{e.year}</b> – {esc(e.text)}" if e.year is not None else esc(e.text) for e in events)
    else:
        body = "Oggi Wikipedia non ha eventi in evidenza."
    # Attribuzione richiesta dalla licenza CC BY-SA 4.0: fonte (pagina del giorno) e licenza.
    source = (
        f'Fonte: <a href="{esc(day_page_url(today.month, today.day))}">Wikipedia</a>'
        f' · <a href="{LICENSE_URL}">CC BY-SA 4.0</a>'
    )
    return f"{title}\n\n{body}\n\n{source}"


async def accadde_oggi(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    today = d.now().date()  # ora italiana (BOT_TIMEZONE)
    try:
        events = await d.services.on_this_day(today.month, today.day)
    except RateLimitedError:
        await query.edit_message_text(RATE_LIMITED_TEXT)
        return
    await query.edit_message_text(
        format_events(events, today),
        parse_mode=HTML,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
