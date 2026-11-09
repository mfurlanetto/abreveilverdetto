"""Doppioni di test: Bot API finta, servizi finti, random pilotabile."""

from __future__ import annotations

import itertools
import json
import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from telegram.request import BaseRequest, RequestData

from abreveilverdetto.services import CovidReport, Pokemon, RateLimitedError, ServiceError, Weather
from abreveilverdetto.wiktionary import parse

SAMPLES_PATH = Path(__file__).parent / "data" / "wiktionary_samples.json"


def load_wiktionary_samples() -> dict[str, str]:
    """Voci reali del Wikizionario (CC BY-SA 4.0), salvate il 9/11/2026."""
    return json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))["pages"]


BOT_ID = 999
ALLOWED_TAGS = {"b", "i", "u", "s", "a", "code", "pre", "tg-spoiler", "blockquote"}


class _TagChecker(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        assert tag in ALLOWED_TAGS, f"tag non supportato da Telegram: <{tag}>"
        self.stack.append(tag)

    def handle_endtag(self, tag):
        assert self.stack and self.stack[-1] == tag, f"tag non bilanciato: </{tag}>"
        self.stack.pop()


def assert_valid_telegram_html(text: str) -> None:
    """Verifica le regole di parse_mode=HTML della Bot API su un testo che stiamo per inviare."""
    assert not re.search(r"&(?!(amp|lt|gt|quot|#\d+);)", text), f"& non escapato in {text!r}"
    checker = _TagChecker()
    checker.feed(text)
    checker.close()
    assert not checker.stack, f"tag non chiusi: {checker.stack}"


@dataclass
class Call:
    method: str
    params: dict[str, Any]


class FakeBotAPI(BaseRequest):
    """Sostituisce le chiamate HTTP a api.telegram.org e registra cosa invia il bot."""

    def __init__(self) -> None:
        self.calls: list[Call] = []
        self.fail: dict[str, str] = {}  # metodo -> descrizione BadRequest (una volta)
        self._ids = itertools.count(1000)

    @property
    def read_timeout(self) -> float | None:
        return None

    async def initialize(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None

    def methods(self) -> list[str]:
        return [c.method for c in self.calls if c.method != "getMe"]

    def last(self, method: str) -> Call:
        return next(c for c in reversed(self.calls) if c.method == method)

    def _message(self, chat_id: Any, **extra: Any) -> dict[str, Any]:
        return {
            "message_id": next(self._ids),
            "date": 0,
            "chat": {"id": int(chat_id), "type": "supergroup"},
            "from": {"id": BOT_ID, "is_bot": True, "first_name": "Bot"},
            **extra,
        }

    async def do_request(self, url: str, method: str, request_data: RequestData | None = None, **_: Any):
        api_method = url.rsplit("/", 1)[-1]
        params = dict(request_data.parameters) if request_data else {}
        if request_data is not None and request_data.contains_files:
            for key in request_data.multipart_data:
                params[key] = "<upload>"  # i file caricati non compaiono in parameters
        if isinstance(params.get("reply_markup"), str):
            params["reply_markup"] = json.loads(params["reply_markup"])
        self.calls.append(Call(api_method, params))

        if api_method in self.fail:
            description = self.fail.pop(api_method)
            return 400, json.dumps({"ok": False, "error_code": 400, "description": description}).encode()

        if params.get("parse_mode") == "HTML":
            for key in ("text", "caption"):
                if key in params:
                    assert_valid_telegram_html(params[key])
        if "caption" in params:
            assert len(params["caption"]) <= 1024, "didascalia oltre il limite di 1024 caratteri"
        if "text" in params:
            assert len(params["text"]) <= 4096, "messaggio oltre il limite di 4096 caratteri"
        for row in (params.get("reply_markup") or {}).get("inline_keyboard", []):
            for button in row:
                assert len(button["callback_data"].encode()) <= 64

        n = next(self._ids)
        result: Any
        if api_method == "getMe":
            result = {"id": BOT_ID, "is_bot": True, "first_name": "Bot", "username": "abv_test_bot"}
        elif api_method == "sendPhoto":
            photo = [{"file_id": f"PHOTO_{n}", "file_unique_id": f"u{n}", "width": 10, "height": 10}]
            result = self._message(params["chat_id"], photo=photo)
        elif api_method == "sendAnimation":
            anim = {"file_id": f"ANIM_{n}", "file_unique_id": f"u{n}", "width": 1, "height": 1, "duration": 1}
            result = self._message(params["chat_id"], animation=anim)
        elif api_method in ("sendMessage", "editMessageText"):
            result = self._message(params.get("chat_id", 1), text=params.get("text", ""))
        else:
            result = True
        return 200, json.dumps({"ok": True, "result": result}).encode()


class ScriptedRandom(random.Random):
    """random.Random con risultati forzati per randrange/choice/randint."""

    def __init__(self, seed: int = 0) -> None:
        super().__init__(seed)
        self.randranges: list[int] = []
        self.choices: list[Any] = []
        self.randints: list[int] = []

    def randrange(self, *args, **kwargs):
        return self.randranges.pop(0) if self.randranges else super().randrange(*args, **kwargs)

    def choice(self, seq):
        return self.choices.pop(0) if self.choices else super().choice(seq)

    def randint(self, a, b):
        return self.randints.pop(0) if self.randints else super().randint(a, b)


@dataclass
class FakeServices:
    weather_result: Weather | None = None
    fail: set[str] = field(default_factory=set)
    weather_enabled: bool = True

    def _check(self, name: str) -> None:
        if name in self.fail:
            raise ServiceError(f"{name} giù")

    async def close(self) -> None:
        return None

    async def comuni(self):
        from abreveilverdetto.services import Comune

        self._check("comuni")
        return [Comune("Sant'Angelo <Lodigiano> & co", "26866", "Lodi", "LO", "Lombardia", 13000)]

    async def weather(self, cap):
        self._check("weather")
        return self.weather_result

    async def covid(self):
        self._check("covid")
        return CovidReport(datetime(2025, 1, 8, 17), 4, 12, 2, 1, -1, 90, -10, 6, 1, 1000, 0)

    async def pokemon(self, number):
        self._check("pokemon")
        return Pokemon(number, "pikachu", ["electric"])

    async def random_words(self):
        self._check("words")
        if "words_rate_limited" in self.fail:
            raise RateLimitedError("it.wiktionary.org chiede di rallentare (HTTP 429)", 30)
        samples = load_wiktionary_samples()
        return [parse(t, samples[t]) for t in ("cazzo", "casa")]

    async def market_quotes(self):
        self._check("markets")
        if "markets_rate_limited" in self.fail:
            raise RateLimitedError("query1.finance.yahoo.com chiede di rallentare (HTTP 429)", 10)
        from abreveilverdetto.markets import parse_spark

        return parse_spark(json.loads((Path(__file__).parent / "data" / "yahoo_spark_sample.json").read_text()))

    async def random_cocktail(self):
        self._check("cocktail")
        drink = {
            "strDrink": "Gin & Tonic",
            "strCategory": "Ordinary Drink",
            "strGlass": "Highball <glass>",
            "strInstructions": "Mix & serve",
            "strDrinkThumb": "https://example.org/gt.jpg",
            "strIngredient1": "Gin",
            "strMeasure1": "2 parts",
            "strIngredient2": "Tonic",
            "strMeasure2": None,
            "strIngredient3": "",
        }
        return drink
