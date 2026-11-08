"""Regole pure di /centocentocento e /fibonacci (nessuna dipendenza da Telegram)."""

from __future__ import annotations

import random
from dataclasses import dataclass

from . import emoji

TARGET = 100
MAX_FIBONACCI = 10


def draw(rng: random.Random) -> int:
    """Un tiro: multiplo di 5 tra 5 e 100 (20 valori equiprobabili)."""
    return 5 + rng.randrange(0, 100, 5)


def result_emoji(value: int) -> str:
    if value < TARGET:
        return emoji.centocentocentoresult["below"]
    if value == TARGET:
        return emoji.centocentocentoresult["win"]
    return emoji.centocentocentoresult["above"]


@dataclass(frozen=True)
class Animation:
    file: str
    caption: str | None = None  # se None si usa il riepilogo standard


# Easter egg. Nota: con tiri multipli di 5 il 118 non è raggiungibile; resta per
# fedeltà alla versione originale, nel caso un giorno cambino le regole.
SPECIAL_VALUES = {
    118: Animation("centocentocento/118.gif", "118! Chiamate un po' il 118!"),
    130: Animation("centocentocento/130_MartinGarrix.gif", "130 km/h! Martin Garrix! The Animals! Si volaaaaaaaaaa"),
}
WIN_ANIMATION = Animation("centocentocento/Iva_Zanicchi_CAGA_in_diretta.gif")
SO_CLOSE_ANIMATION = Animation("centocentocento/Mr_Bean_Middle_Finger.gif")


def pick_animation(value: int, runs: int) -> Animation | None:
    if value == TARGET:
        return WIN_ANIMATION
    if value in SPECIAL_VALUES:
        return SPECIAL_VALUES[value]
    if runs == 2 and value in (95, 105):
        return SO_CLOSE_ANIMATION
    return None


def fibonacci(count: int) -> list[int]:
    """I primi ``count`` numeri di Fibonacci a partire da 1, 1."""
    seq: list[int] = []
    a, b = 1, 1
    for _ in range(max(count, 0)):
        seq.append(a)
        a, b = b, a + b
    return seq


def fibonacci_reply(raw: str, rng: random.Random) -> str:
    """Risposta a /fibonacci: lunghezza casuale tra 1 e il massimo richiesto (≤10)."""
    notes = []
    try:
        requested = int(raw.strip())
    except ValueError:
        requested = MAX_FIBONACCI
        notes.append(f"«{raw.strip()[:30]}» non è un numero: uso {MAX_FIBONACCI}.")
    if requested < 1:
        requested = 1
        notes.append("Il minimo è 1.")
    elif requested > MAX_FIBONACCI:
        requested = MAX_FIBONACCI
        notes.append(f"Il massimo consentito è {MAX_FIBONACCI}.")
    count = rng.randint(1, requested)
    notes.append(", ".join(map(str, fibonacci(count))))
    return "\n".join(notes)
