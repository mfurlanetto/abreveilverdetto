"""Eventi "in evidenza" del giorno da Wikipedia in italiano (feed onthisday).

Il feed restituisce gli eventi scelti dalla redazione per la pagina del giorno.
In italiano le sezioni nascite e morti sono vuote, per questo si usano solo gli
eventi in evidenza ("selected"). Contenuti CC BY-SA 4.0: va citata la fonte.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

FEED_URL = "https://it.wikipedia.org/api/rest_v1/feed/onthisday/selected/{month:02d}/{day:02d}"
DAY_PAGE_URL = "https://it.wikipedia.org/wiki/{}"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/deed.it"

MONTHS = (
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)


@dataclass(frozen=True)
class Event:
    year: int | None
    text: str


def day_label(month: int, day: int) -> str:
    """15, 11 -> '15 novembre'; 1, 1 -> '1º gennaio' come i titoli di Wikipedia."""
    prefix = "1º" if day == 1 else str(day)
    return f"{prefix} {MONTHS[month - 1]}"


def day_page_url(month: int, day: int) -> str:
    return DAY_PAGE_URL.format(quote(day_label(month, day).replace(" ", "_")))


def parse_selected(data: Any) -> list[Event]:
    """Risposta del feed -> eventi in evidenza, dal più recente (ordine del feed)."""
    try:
        items = data["selected"] or []
    except (KeyError, TypeError):
        return []
    events = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        year = item.get("year")
        events.append(Event(year if isinstance(year, int) else None, text))
    return events
