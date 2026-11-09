import pytest

from abreveilverdetto.commands.dizionario import MAX_DEFINITION_CHARS, format_entry
from abreveilverdetto.wiktionary import Entry, Sense, clean, parse
from tests.fakes import assert_valid_telegram_html, load_wiktionary_samples

SAMPLES = load_wiktionary_samples()


def entry(title):
    return parse(title, SAMPLES[title])


def test_voci_reali_categorie_e_definizioni():
    e = entry("cazzo")
    assert [s.pos for s in e.senses] == ["interiezione", "sostantivo", "voce verbale"]
    assert e.senses[1].definitions[0] == "(volgare) pene"
    assert e.senses[1].definitions[1] == "(per estensione) (volgare) usato al posto di cosa o che"

    a = entry("accasciare")
    assert a.senses == (
        Sense(
            "verbo",
            (
                "infiacchire, indebolire fino alla mancanza di forze",
                "(riflessivo) infiacchirsi, indebolirsi",
                "(marina) aggravarsi di nave sopra un banco o una secca",
            ),
        ),
    )


def test_esempi_e_righe_di_flessione_ignorati():
    casa = entry("casa")
    defs = casa.senses[0].definitions
    assert defs[0].startswith("(architettura) edificio costruito per essere utilizzato come abitazione")
    assert not any("acquistato una bella casa" in d for d in defs)  # esempio
    assert not any("f sing" in d for d in defs)  # riga di flessione
    assert all("File:" not in d and "thumb" not in d for d in defs)  # immagini annidate rimosse

    andare = entry("andare")
    assert [s.pos for s in andare.senses] == ["sostantivo", "verbo"]
    assert "muoversi da un luogo verso un altro luogo" in andare.senses[1].definitions
    assert not any("ogni mattina" in d for d in andare.senses[1].definitions)


def test_forme_flesse_e_locuzioni():
    assert entry("denunceremmo").senses[0] == Sense(
        "voce verbale", ("prima persona plurale del condizionale presente di denunciare",)
    )
    assert entry("ingegneria fisica").senses[0].pos == "locuzione nominale"


@pytest.mark.parametrize("title", ["fondisse", "Betriebsablauf", "tribunal", "EMI", "ferentur"])
def test_pagine_senza_sezione_italiana(title):
    assert not entry(title).has_definitions()


def test_nessuna_definizione_contiene_markup():
    for title, text in SAMPLES.items():
        for sense in parse(title, text).senses:
            for d in sense.definitions:
                assert not any(tok in d for tok in ("[[", "]]", "{{", "}}", "''", "<ref", "<!--")), (title, d)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("[[a|b]] e [[c]]", "b e c"),
        ("[[adire#Latino|adīre]]", "adīre"),
        ("[[fondre#Francese]]", "fondre"),
        ("{{Term|[[musica]]}} testo", "(musica) testo"),
        ("{{Fig}} {{Sconosciuto|x|y}} senso", "(figurato) senso"),
        ("parola{{Pn}}", "parolaprova"),
        ("testo<ref>nota [[x]]</ref> fine<!-- commento -->", "testo fine"),
        ("[[File:a.jpg|thumb|una [[casa]] in [[pietra]]]] resto", "resto"),
        ("'''grassetto''' e ''corsivo'' &amp; c", "grassetto e corsivo & c"),
        ("[https://example.org sito] ok", "sito ok"),
        ("parola , altra ( nota )", "parola, altra (nota)"),
    ],
)
def test_clean(raw, expected):
    assert clean(raw, "prova") == expected


def test_url_con_spazi_e_accenti():
    assert Entry("ingegneria fisica").url == "https://it.wiktionary.org/wiki/ingegneria_fisica"
    assert Entry("perché").url == "https://it.wiktionary.org/wiki/perch%C3%A9"


def test_format_massimo_tre_definizioni_con_attribuzione():
    text = format_entry(entry("cazzo"))
    assert_valid_telegram_html(text)
    assert text.startswith("📖 <b>CAZZO</b>")
    assert "3. " in text and "4. " not in text
    assert "<i>interiezione</i>" in text and "<i>sostantivo</i>" in text
    assert "voce verbale" not in text  # già raggiunte 3 definizioni
    assert 'href="https://it.wiktionary.org/wiki/cazzo"' in text
    assert "CC BY-SA 4.0" in text


def test_format_tronca_definizioni_lunghe_ed_esegue_escape():
    long = "parola " * 100
    text = format_entry(Entry("a<b", (Sense("sostantivo", (long, "x & y")),)))
    assert_valid_telegram_html(text)
    line = text.splitlines()[2]
    assert line.endswith("…") and len(line) <= MAX_DEFINITION_CHARS + 4
    assert "A&lt;B" in text and "x &amp; y" in text


def test_ogni_voce_reale_formattata_in_html_valido():
    for title, text in SAMPLES.items():
        e = parse(title, text)
        if e.has_definitions():
            out = format_entry(e)
            assert_valid_telegram_html(out)
            assert len(out) <= 4096
