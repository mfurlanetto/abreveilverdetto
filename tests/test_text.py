from datetime import UTC, datetime, timedelta

import pytest

from abreveilverdetto.text import (
    esc,
    greeting,
    number_emoji,
    signed,
    spaced_upper,
    table,
    translate_measure,
    utc_offset,
    utc_offsets,
)


def test_esc_neutralizza_html():
    assert esc("<b>&") == "&lt;b&gt;&amp;"
    assert esc('l\'Aquila "x"') == 'l\'Aquila "x"'


@pytest.mark.parametrize(
    ("hour", "expected"),
    [(5, "Buonasera"), (6, "Buongiorno"), (12, "Buongiorno"), (13, "Buon pomeriggio"), (17, "Buonasera")],
)
def test_greeting(hour, expected):
    assert greeting(datetime(2026, 1, 1, hour), "Mario") == f"{expected} Mario"


def test_signed():
    assert signed(1234) == "+1,234"
    assert signed(-5) == "-5"
    assert signed(0) == "0"


def test_number_emoji_e_spaced_upper():
    assert number_emoji(105) == "1️⃣0️⃣5️⃣"
    assert spaced_upper("Roma") == "R O M A"


def test_table_allinea_valori_multilinea_ed_esegue_escape():
    out = table([("Moneta", "Euro (EUR)\n<Lira>")], pad=8)
    assert out == "<pre>Moneta: Euro (EUR)\n        &lt;Lira&gt;</pre>"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("   ", None),
        ("2 dashes", "2 pizzichi"),
        ("1 dash", "1 pizzico"),
        ("1/2 cup", "1/2 tazzina"),
        ("1 1/2 cups", "1 1/2 tazzine"),
        ("2 tsp", "2 cucchiaini"),
        ("1 tblsp", "1 cucchiaio"),
        ("3 tbsp", "3 cucchiai"),
        ("1 can", "1 lattina"),
        ("Juice of 1", "succo of 1"),
        ("4 cl", "4 cl"),
        ("Cantaloupe", "Cantaloupe"),  # niente sostituzioni dentro le parole
    ],
)
def test_translate_measure(raw, expected):
    assert translate_measure(raw) == expected


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (timedelta(0), "UTC+0"),
        (timedelta(hours=1), "UTC+1"),
        (timedelta(hours=5, minutes=30), "UTC+5:30"),
        (timedelta(hours=5, minutes=45), "UTC+5:45"),
        (timedelta(hours=-3, minutes=-30), "UTC-3:30"),
        (timedelta(hours=-10), "UTC-10"),
    ],
)
def test_utc_offset(offset, expected):
    assert utc_offset(offset) == expected


def test_utc_offsets_ora_legale_doppioni_e_ordine():
    inverno = datetime(2026, 1, 15, 12, tzinfo=UTC)
    estate = datetime(2026, 7, 15, 12, tzinfo=UTC)
    assert utc_offsets(["Europe/Rome"], inverno) == ["UTC+1"]
    assert utc_offsets(["Europe/Rome"], estate) == ["UTC+2"]
    zones = ["America/Los_Angeles", "America/New_York", "America/Detroit", "Pacific/Honolulu"]
    assert utc_offsets(zones, inverno) == ["UTC-10", "UTC-8", "UTC-5"]
    assert utc_offsets(["Asia/Kathmandu", "Asia/Kolkata"], inverno) == ["UTC+5:30", "UTC+5:45"]
