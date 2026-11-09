"""Quotazioni di indici e materie prime da Yahoo Finance (endpoint non ufficiale "spark").

Yahoo Finance non ha un'API pubblica documentata: l'endpoint può cambiare o essere
limitato senza preavviso, e i dati sono per uso personale. Una sola richiesta
restituisce tutti gli strumenti, per non far scattare i limiti di Yahoo (che
rispondeva 429 già a 13 richieste singole in sequenza, verificato il 9/11/2026).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

SPARK_URL = "https://query1.finance.yahoo.com/v7/finance/spark"


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    group: str


INDICES = "INDICI"
COMMODITIES = "MATERIE PRIME"

INSTRUMENTS: tuple[Instrument, ...] = (
    Instrument("FTSEMIB.MI", "FTSE MIB", INDICES),
    Instrument("^GDAXI", "DAX", INDICES),
    Instrument("^STOXX50E", "Euro Stoxx 50", INDICES),
    Instrument("^GSPC", "S&P 500", INDICES),
    Instrument("^IXIC", "Nasdaq", INDICES),
    Instrument("^DJI", "Dow Jones", INDICES),
    Instrument("^N225", "Nikkei 225", INDICES),
    Instrument("GC=F", "Oro", COMMODITIES),
    Instrument("SI=F", "Argento", COMMODITIES),
    Instrument("BZ=F", "Brent", COMMODITIES),
    Instrument("CL=F", "WTI", COMMODITIES),
    Instrument("NG=F", "Gas naturale", COMMODITIES),
    Instrument("HG=F", "Rame", COMMODITIES),
)


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    previous_close: float | None
    change_pct: float | None
    time: datetime
    regular_start: datetime | None
    regular_end: datetime | None

    @property
    def decimals(self) -> int:
        """2 decimali, 3 per i prezzi sotto 10 (gas, rame), dove 2 sarebbero troppo pochi."""
        return 2 if abs(self.price) >= 10 else 3

    def is_open(self, now: datetime) -> bool:
        """Mercato nella sessione regolare in corso? Altrimenti il prezzo è l'ultima chiusura."""
        if self.regular_start is None or self.regular_end is None:
            return False
        return self.regular_start <= now < self.regular_end


def _ts(value: Any) -> datetime | None:
    return datetime.fromtimestamp(value, UTC) if isinstance(value, int | float) else None


def _number(value: Any) -> float | None:
    if isinstance(value, int | float) and math.isfinite(value):
        return float(value)
    return None


def parse_quote(meta: dict[str, Any]) -> Quote | None:
    price = _number(meta.get("regularMarketPrice"))
    time = _ts(meta.get("regularMarketTime"))
    if price is None or time is None:
        return None
    previous = _number(meta.get("chartPreviousClose")) or _number(meta.get("previousClose"))
    change = (price / previous - 1) * 100 if previous else _number(meta.get("regularMarketChangePercent"))
    regular = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    return Quote(
        symbol=str(meta.get("symbol", "")),
        price=price,
        previous_close=previous,
        change_pct=change,
        time=time,
        regular_start=_ts(regular.get("start")),
        regular_end=_ts(regular.get("end")),
    )


def parse_spark(data: Any) -> dict[str, Quote]:
    """Risposta di /v7/finance/spark -> quotazioni per simbolo (i simboli mancanti sono omessi)."""
    quotes: dict[str, Quote] = {}
    try:
        results = data["spark"]["result"] or []
    except (KeyError, TypeError):
        return quotes
    for item in results:
        try:
            meta = item["response"][0]["meta"]
        except (KeyError, IndexError, TypeError):
            continue
        quote = parse_quote(meta)
        if quote is not None:
            quotes[item.get("symbol") or quote.symbol] = quote
    return quotes
