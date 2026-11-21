import json
from pathlib import Path

import httpx
import pytest

from abreveilverdetto import mountains
from abreveilverdetto.commands.montagna import caption, elevation
from abreveilverdetto.mountains import (
    Details,
    Mountain,
    Photo,
    api_params,
    parse_details,
    plain,
    shorten,
    without_parentheses,
)
from abreveilverdetto.services import RateLimitedError, Services
from tests.fakes import assert_valid_telegram_html

# Risposta reale di it.wikipedia.org per il Cervino (testo CC BY-SA 4.0, metadati da Commons)
SAMPLE = json.loads((Path(__file__).parent / "data" / "wikipedia_mountain_cervino.json").read_text())
CERVINO = Mountain("Q1374", "Cervino", 4478, ("Italia", "Svizzera"), ("Alpi Pennine",), "Cervino cloud.jpg")


def test_parse_details_reale():
    details = parse_details(SAMPLE)
    assert details.description.startswith("Il Cervino è una montagna delle Alpi alta 4478 m s.l.m.")
    assert "(" not in details.description
    assert len(details.description) <= mountains.MAX_DESCRIPTION
    photo = details.photo
    assert photo.url.startswith("https://thumb.wikimedia.org/") and "/1280px-Cervino_cloud.jpg" in photo.url
    assert (photo.artist, photo.license) == ("Gianluca Miscione", "CC BY-SA 4.0")
    assert photo.page_url.startswith("https://commons.wikimedia.org/wiki/File:")
    assert photo.artist and "<" not in photo.artist
    assert photo.license


@pytest.mark.parametrize("data", [None, {}, {"query": {}}, {"query": {"pages": "x"}}, {"query": {"pages": [1]}}])
def test_parse_details_malformato(data):
    assert parse_details(data) == Details(None, None)


def test_parse_details_voce_mancante_e_foto_senza_metadati():
    data = {
        "query": {
            "pages": [
                {"ns": 0, "title": "Boh", "missing": True},
                {
                    "ns": 6,
                    "title": "File:X.jpg",
                    "missing": True,
                    "known": True,
                    "imageinfo": [{"url": "https://u/x.jpg"}],
                },
            ]
        }
    }
    assert parse_details(data) == Details(None, Photo("https://u/x.jpg", "https://u/x.jpg", None, None))


def test_without_parentheses():
    assert without_parentheses("Il Cervino (Cervin, pron. [x (y)]) è  alto (4478 m).") == "Il Cervino è alto."


def test_plain_e_shorten():
    assert plain('<a href="//x">Mario&nbsp;Rossi</a>\n<br> (talk)') == "Mario Rossi (talk)"
    assert shorten("Corta.", 100) == "Corta."
    assert shorten("Prima frase lunga. Seconda frase lunghissima che non ci sta.", 40) == "Prima frase lunga."
    assert shorten("una sola frase senza punti e lunghissima", 20) == "una sola frase…"


def test_nome_senza_disambigua_e_url():
    m = Mountain("Q30429", "Corno Nero (Alpi Pennine)", 4321, ("Italia",), (), "x.jpg")
    assert m.name == "Corno Nero"
    assert m.page_url == "https://it.wikipedia.org/wiki/Corno_Nero_(Alpi_Pennine)"


def test_elevation():
    assert elevation(4478) == "4.478 m"
    assert elevation(724) == "724 m"


def test_caption_reale():
    text = caption(CERVINO, parse_details(SAMPLE))
    assert_valid_telegram_html(text)
    assert text.startswith("⛰ <b>CERVINO</b>\n<pre>Altitudine: 4.478 m\nNazione:    Italia\n            Svizzera\n")
    assert "Via Wikimedia Commons".lower() in text.lower() and "CC BY-SA 4.0" in text
    assert len(text) <= 1024


def test_caption_senza_dettagli():
    text = caption(Mountain("Q1", "X", 10, (), (), "x.jpg"), None)
    assert_valid_telegram_html(text)
    assert "Nazione" not in text and "Catena" not in text and "Foto:" not in text


def make_services(handler):
    return Services(httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_servizio_una_richiesta_header_e_cache():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=SAMPLE)

    s = make_services(handler)
    first = await s.mountain_details(CERVINO)
    assert first == await s.mountain_details(CERVINO)
    assert len(calls) == 1  # in cache per un giorno
    request = calls[0]
    assert request.url.host == "it.wikipedia.org"
    assert request.url.params["titles"] == "Cervino|File:Cervino cloud.jpg"
    assert dict(request.url.params) == api_params(CERVINO)
    assert request.headers["Accept"] == "application/json"


async def test_servizio_429():
    def handler(request):
        return httpx.Response(429, headers={"Retry-After": "30"})

    with pytest.raises(RateLimitedError):
        await make_services(handler).mountain_details(CERVINO)
