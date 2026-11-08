from datetime import datetime

import pytest

from abreveilverdetto.text import esc, greeting, number_emoji, signed, spaced_upper, table, translate_measure


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
