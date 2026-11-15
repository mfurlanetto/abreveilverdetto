import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from abreveilverdetto import onthisday
from abreveilverdetto.commands.accadde import format_events
from abreveilverdetto.onthisday import Event, day_label, day_page_url, parse_selected
from abreveilverdetto.services import RateLimitedError, Services
from tests.fakes import assert_valid_telegram_html

# Eventi in evidenza reali del 13 novembre (it.wikipedia.org, CC BY-SA 4.0)
SAMPLE = json.loads((Path(__file__).parent / "data" / "onthisday_selected_11_13.json").read_text())


def test_parse_selected_reale():
    events = parse_selected(SAMPLE)
    assert [e.year for e in events] == [2015, 2002, 1994, 1990, 1960, 1940]
    assert events[3].text == "Viene scritta la prima pagina conosciuta del World Wide Web."


@pytest.mark.parametrize(
    "data",
    [None, {}, {"selected": None}, {"selected": ["x", {"text": ""}, {"year": 1900}]}],
)
def test_parse_selected_malformato(data):
    assert parse_selected(data) == []


def test_parse_selected_anno_mancante():
    assert parse_selected({"selected": [{"text": "Qualcosa", "year": "boh"}]}) == [Event(None, "Qualcosa")]


@pytest.mark.parametrize(
    ("month", "day", "label", "url"),
    [
        (11, 13, "13 novembre", "https://it.wikipedia.org/wiki/13_novembre"),
        (1, 1, "1º gennaio", "https://it.wikipedia.org/wiki/1%C2%BA_gennaio"),
        (2, 29, "29 febbraio", "https://it.wikipedia.org/wiki/29_febbraio"),
    ],
)
def test_giorno_e_pagina(month, day, label, url):
    assert day_label(month, day) == label
    assert day_page_url(month, day) == url


def test_format_events():
    text = format_events(parse_selected(SAMPLE), date(2026, 11, 13))
    assert_valid_telegram_html(text)
    assert text.startswith("📅 <b>ACCADDE OGGI</b> · 13 novembre\n\n<b>2015</b> – Una serie di attacchi")
    assert '<a href="https://it.wikipedia.org/wiki/13_novembre">Wikipedia</a>' in text
    assert len(text) < 4096


def test_format_events_vuoto_ed_escape():
    assert "non ha eventi in evidenza" in format_events([], date(2026, 1, 1))
    text = format_events([Event(None, "A < B & C")], date(2026, 1, 1))
    assert_valid_telegram_html(text)
    assert "A &lt; B &amp; C" in text and "1º gennaio" in text


def make_services(handler):
    return Services(httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_servizio_url_header_e_cache():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=SAMPLE)

    s = make_services(handler)
    first = await s.on_this_day(11, 13)
    second = await s.on_this_day(11, 13)
    assert first == second and len(first) == 6
    assert len(calls) == 1  # in cache: niente seconda richiesta per lo stesso giorno
    assert str(calls[0].url) == onthisday.FEED_URL.format(month=11, day=13)
    assert str(calls[0].url).endswith("/selected/11/13")
    assert calls[0].headers["Accept"] == "application/json"
    await s.on_this_day(11, 14)
    assert len(calls) == 2  # giorno diverso: nuova richiesta


async def test_servizio_429():
    def handler(request):
        return httpx.Response(429, headers={"Retry-After": "30"})

    with pytest.raises(RateLimitedError):
        await make_services(handler).on_this_day(11, 13)
