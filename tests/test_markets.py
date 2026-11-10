import json
import re
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from abreveilverdetto.commands.trombin import CLOSED_MARK, format_change, format_it, format_report
from abreveilverdetto.markets import INSTRUMENTS, parse_quote, parse_spark
from tests.fakes import assert_valid_telegram_html

# Risposta reale di /v7/finance/spark per i 13 strumenti, 9/11/2026 ~20:37 UTC
SAMPLE = json.loads((Path(__file__).parent / "data" / "yahoo_spark_sample.json").read_text())
AT_SAMPLE = datetime(2026, 11, 9, 20, 37, tzinfo=UTC)
ROME = ZoneInfo("Europe/Rome")


def test_parse_spark_reale():
    quotes = parse_spark(SAMPLE)
    assert set(quotes) == {i.symbol for i in INSTRUMENTS}
    sp = quotes["^GSPC"]
    assert sp.price == 7571.13
    assert sp.previous_close == 7376.86
    assert sp.change_pct == pytest.approx(2.634, abs=0.001)


def test_mercati_aperti_e_chiusi_all_ora_del_campione():
    quotes = parse_spark(SAMPLE)
    is_open = {s: q.is_open(AT_SAMPLE) for s, q in quotes.items()}
    assert is_open["^GSPC"] and is_open["^DJI"] and is_open["^IXIC"]  # Wall Street aperta
    assert not is_open["FTSEMIB.MI"] and not is_open["^GDAXI"] and not is_open["^STOXX50E"]
    assert not is_open["^N225"]
    assert all(is_open[s] for s in ("GC=F", "SI=F", "BZ=F", "CL=F", "NG=F", "HG=F"))  # futures


def test_parse_quote_casi_limite():
    assert parse_quote({"symbol": "X"}) is None
    assert parse_quote({"regularMarketPrice": float("nan"), "regularMarketTime": 1}) is None
    q = parse_quote(
        {"symbol": "X", "regularMarketPrice": 5.0, "regularMarketTime": 1, "regularMarketChangePercent": -1.5}
    )
    assert q.change_pct == -1.5  # senza chiusura precedente usa il valore di Yahoo
    assert q.decimals == 3
    assert not q.is_open(AT_SAMPLE)  # orari mancanti: trattato come chiuso


@pytest.mark.parametrize("data", [None, {}, {"spark": {"result": None}}, {"spark": {"result": [{"response": []}]}}])
def test_parse_spark_risposte_malformate(data):
    assert parse_spark(data) == {}


def test_format_it_e_variazione():
    assert format_it(51399.875) == "51.399,88"
    assert format_it(3.2094, 3) == "3,209"
    assert format_change(2.634) == "▲ +2,63%"
    assert format_change(-6.041) == "▼ -6,04%"
    assert format_change(0.0) == "= 0,00%"
    assert format_change(None).strip() == "n.d."


def test_report_completo():
    text = format_report(parse_spark(SAMPLE), AT_SAMPLE, ROME)
    assert_valid_telegram_html(text)
    assert text.startswith("📈 <b>TROMBIN</b> · 09/11/2026 21:37")
    pre = re.search(r"<pre>(.*)</pre>", text, re.S).group(1)
    rows = pre.split("\n")
    assert "FTSE MIB      51.399,88 ▲ +2,69% *" in rows
    assert "S&amp;P 500        7.571,13 ▲ +2,63%" in rows
    assert "Brent             92,38 ▼ -6,04%" in rows
    assert max(len(r.replace("&amp;", "&")) for r in rows) <= 38  # niente a capo sul telefono
    assert f"{CLOSED_MARK} mercato chiuso" in text
    assert "Yahoo Finance" in text


def test_report_con_strumenti_mancanti_e_tutto_aperto():
    quotes = {s: q for s, q in parse_spark(SAMPLE).items() if s == "GC=F"}
    text = format_report(quotes, AT_SAMPLE, ROME)
    assert "FTSE MIB" in text and "Oro" in text
    assert text.count("n.d.") == len(INSTRUMENTS) - 1
    assert "mercato chiuso" not in text  # l'unico presente (oro) è aperto
