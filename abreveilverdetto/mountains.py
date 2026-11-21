"""Montagne del mondo: dati da Wikidata (data/mountains.json), testo e foto da Wikipedia.

- data/mountains.json è generato da scripts/build_mountains.py (Wikidata, CC0):
  titolo della voce italiana, altitudine, nazioni, catena, file della foto.
- A runtime una sola richiesta all'API di it.wikipedia.org restituisce l'introduzione
  della voce (CC BY-SA 4.0) e, per il file della foto (Wikimedia Commons, letto
  tramite it.wikipedia), l'URL della miniatura con autore e licenza.
  Le foto di Commons hanno licenze diverse (CC BY, CC BY-SA, pubblico dominio…):
  autore e licenza vanno indicati a ogni uso
  (https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

API_URL = "https://it.wikipedia.org/w/api.php"
PAGE_URL = "https://it.wikipedia.org/wiki/{}"
TEXT_LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/deed.it"
# Larghezza standard delle miniature di Wikimedia: le altre misure possono essere rifiutate.
THUMB_WIDTH = 1280
MAX_DESCRIPTION = 400
MAX_ARTIST = 60


@dataclass(frozen=True)
class Mountain:
    id: str
    title: str
    elevation: int
    countries: tuple[str, ...]
    ranges: tuple[str, ...]
    image: str

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Mountain:
        return cls(
            id=raw["id"],
            title=raw["title"],
            elevation=int(raw["elevation"]),
            countries=tuple(raw["countries"]),
            ranges=tuple(raw["ranges"]),
            image=raw["image"],
        )

    @property
    def name(self) -> str:
        """'Corno Nero (Alpi Pennine)' -> 'Corno Nero': la disambigua serve solo a Wikipedia."""
        return re.sub(r"\s*\([^)]*\)$", "", self.title)

    @property
    def page_url(self) -> str:
        return PAGE_URL.format(quote(self.title.replace(" ", "_"), safe="()"))


@dataclass(frozen=True)
class Photo:
    url: str
    page_url: str
    artist: str | None
    license: str | None


@dataclass(frozen=True)
class Details:
    description: str | None
    photo: Photo | None


def api_params(mountain: Mountain) -> dict[str, str]:
    """Parametri di una sola richiesta: introduzione della voce + metadati della foto."""
    return {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "redirects": "1",
        "titles": f"{mountain.title}|File:{mountain.image}",
        "prop": "extracts|imageinfo",
        "exintro": "1",
        "explaintext": "1",
        "exsentences": "3",
        "iiprop": "url|extmetadata",
        "iiurlwidth": str(THUMB_WIDTH),
        "iiextmetadatafilter": "Artist|LicenseShortName",
    }


def plain(value: str) -> str:
    """HTML dei metadati di Commons -> testo semplice su una riga."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def without_parentheses(text: str) -> str:
    """Toglie gli incisi tra parentesi (pronuncia, nomi in altre lingue, classificazioni).

    Nelle voci di montagne occupano spesso metà dell'introduzione:
    "Il Cervino (Cervin in francese, pron. AFI: …) è una montagna…".
    """
    previous = None
    while previous != text:  # dall'interno verso l'esterno, per le parentesi annidate
        previous = text
        text = re.sub(r"\s*\([^()]*\)", "", text)
    return " ".join(text.split())


def shorten(text: str, limit: int) -> str:
    """Taglia all'ultima frase completa entro ``limit`` caratteri (o alla parola, con …)."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = cut.rfind(". ")
    if end > limit // 4:  # meglio una frase intera e breve che una troncata
        return cut[: end + 1]
    return cut.rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _photo(page: dict[str, Any]) -> Photo | None:
    try:
        info = page["imageinfo"][0]
        url = info.get("thumburl") or info["url"]
    except (KeyError, IndexError, TypeError):
        return None
    meta = info.get("extmetadata") or {}

    def field(name: str) -> str | None:
        value = plain(str((meta.get(name) or {}).get("value") or ""))
        return value or None

    artist = field("Artist")
    if artist and len(artist) > MAX_ARTIST:
        artist = artist[: MAX_ARTIST - 1].rstrip() + "…"
    return Photo(url=url, page_url=info.get("descriptionurl") or url, artist=artist, license=field("LicenseShortName"))


def parse_details(data: Any) -> Details:
    """Risposta dell'API -> descrizione (introduzione abbreviata) e foto con attribuzione."""
    try:
        pages = data["query"]["pages"]
    except (KeyError, TypeError):
        return Details(None, None)
    description = photo = None
    for page in pages if isinstance(pages, list) else []:
        if not isinstance(page, dict):
            continue
        # I file di Commons risultano "missing" su it.wikipedia (non hanno una pagina
        # locale) ma hanno comunque imageinfo: per loro "missing" non conta.
        if page.get("ns") == 6:
            photo = _photo(page)
        elif page.get("ns") == 0 and not page.get("missing"):
            extract = without_parentheses(str(page.get("extract") or ""))
            description = shorten(extract, MAX_DESCRIPTION) or None
    return Details(description, photo)
