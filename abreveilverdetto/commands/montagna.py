"""⛰ MONTAGNA: una montagna a caso nel mondo, con foto, altitudine, nazione e catena.

Dati strutturati da Wikidata (CC0), descrizione da Wikipedia (CC BY-SA 4.0) e foto
da Wikimedia Commons: testo e foto vanno attribuiti nella didascalia.
"""

from __future__ import annotations

import logging

from telegram import CallbackQuery, LinkPreviewOptions
from telegram.ext import ContextTypes

from ..mountains import TEXT_LICENSE_URL, Details, Mountain
from ..services import RateLimitedError, ServiceError
from ..telegram_io import HTML, deps, replace_with_remote_photo
from ..text import esc, table

logger = logging.getLogger(__name__)

CAPTION_LIMIT = 1024  # limite di Telegram per le didascalie delle foto


def elevation(metres: int) -> str:
    """4806 -> '4.806 m' (separatore delle migliaia italiano)."""
    return f"{metres:,} m".replace(",", ".")


def caption(mountain: Mountain, details: Details | None) -> str:
    rows = [("Altitudine", elevation(mountain.elevation))]
    if mountain.countries:
        rows.append(("Nazione", "\n".join(mountain.countries)))
    if mountain.ranges:
        rows.append(("Catena", "\n".join(mountain.ranges)))
    head = f"⛰ <b>{esc(mountain.name.upper())}</b>\n{table(rows, pad=12)}"

    credits = [
        f'Testo: <a href="{esc(mountain.page_url)}">Wikipedia</a> · <a href="{TEXT_LICENSE_URL}">CC BY-SA 4.0</a>'
    ]
    photo = details.photo if details else None
    if photo:
        author = esc(photo.artist) if photo.artist else "autore sconosciuto"
        license_ = f", {esc(photo.license)}" if photo.license else ""
        credits.append(f'Foto: <a href="{esc(photo.page_url)}">{author}</a>{license_}, via Wikimedia Commons')
    footer = "\n".join(credits)

    description = details.description if details else None
    if description:
        text = f"{head}\n{esc(description)}\n\n{footer}"
        # Testo troppo lungo per una didascalia: si sacrifica la descrizione, non i dati.
        while len(text) > CAPTION_LIMIT and " " in description:
            description = description.rstrip("…").rsplit(" ", 1)[0]
            text = f"{head}\n{esc(description)}…\n\n{footer}"
        if len(text) <= CAPTION_LIMIT:
            return text
    return f"{head}\n{footer}"


async def montagna(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    mountain = d.rng.choice(d.content.mountains)
    try:
        details = await d.services.mountain_details(mountain)
    except RateLimitedError:
        details = None  # senza Wikipedia restano i dati di Wikidata
    except ServiceError:
        logger.warning("Wikipedia non disponibile per %s", mountain.title, exc_info=True)
        details = None

    text = caption(mountain, details)
    if details and details.photo:
        await replace_with_remote_photo(query, details.photo.url, text)
    else:
        await query.edit_message_text(text, parse_mode=HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
