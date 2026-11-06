"""Funzioni pure di formattazione testo (tutti i messaggi usano parse mode HTML)."""

from __future__ import annotations

import html
import re
from collections.abc import Iterable
from datetime import datetime

from . import emoji


def esc(value: object) -> str:
    """Escape HTML per qualsiasi valore inserito in un messaggio."""
    return html.escape(str(value), quote=False)


def greeting(now: datetime, name: str) -> str:
    hour = now.hour
    if 6 <= hour < 13:
        word = "Buongiorno"
    elif 13 <= hour < 17:
        word = "Buon pomeriggio"
    else:
        word = "Buonasera"
    return f"{word} {name}"


def signed(value: float) -> str:
    """Numero con segno esplicito e separatore delle migliaia: +1,234 / -12 / 0."""
    return f"{value:+,.0f}" if value else "0"


def number_emoji(value: int) -> str:
    return "".join(emoji.numbers[d] for d in str(value))


def spaced_upper(name: str) -> str:
    """'Roma' -> 'R O M A' (stile titolo usato da /comune e /nazione)."""
    return " ".join(name.upper())


def table(rows: Iterable[tuple[str, str]], pad: int = 16) -> str:
    """Tabella chiave/valore monospazio; i valori multilinea vengono allineati."""
    lines = []
    for key, value in rows:
        prefix = f"{key + ':':<{pad}}"
        parts = str(value).split("\n")
        lines.append(prefix + parts[0])
        lines.extend(" " * pad + part for part in parts[1:])
    return "<pre>" + esc("\n".join(lines)) + "</pre>"


# --- Traduzione delle unità di misura dei cocktail -------------------------------------

_MEASURES = [
    (r"\bcans?\b", ("lattina", "lattine")),
    (r"\bcups?\b", ("tazzina", "tazzine")),
    (r"\bdash(?:es)?\b", ("pizzico", "pizzichi")),
    (r"\bdrops?\b", ("goccia", "gocce")),
    (r"\bparts?\b", ("parte", "parti")),
    (r"\bscoops?\b", ("porzione", "porzioni")),
    (r"\bslices?\b", ("fetta", "fette")),
    (r"\btsp\b", ("cucchiaino", "cucchiaini")),
    (r"\btbl?sp\b", ("cucchiaio", "cucchiai")),
    (r"\bground\b", ("base", "base")),
    (r"\bjuice\b", ("succo", "succo")),
]


_QUANTITY = re.compile(r"(\d+(?:[.,]\d+)?)(?:\s+(\d+)\s*/\s*(\d+)|\s*/\s*(\d+))?")


def _is_plural(quantity_text: str) -> bool:
    """Quantità maggiore di 1 (in italiano "1/2 tazzina" è singolare)? Gestisce 2, 1.5, 1/2, 1 1/2."""
    match = _QUANTITY.search(quantity_text)
    if not match:
        return False
    whole, num, den, simple_den = match.groups()
    try:
        value = float(whole.replace(",", "."))
        if num and den:
            value += float(num) / float(den)
        elif simple_den:
            value /= float(simple_den)
    except ZeroDivisionError:
        return False
    return value > 1


def translate_measure(measure: str | None) -> str | None:
    """Traduce le unità inglesi di TheCocktailDB ('2 dashes' -> '2 pizzichi')."""
    if not measure or not measure.strip():
        return None
    text = measure.strip()
    plural = _is_plural(text)
    for pattern, (singular, plural_form) in _MEASURES:
        text = re.sub(pattern, plural_form if plural else singular, text, flags=re.IGNORECASE)
    return text
