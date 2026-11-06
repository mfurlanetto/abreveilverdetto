import random

import pytest

from abreveilverdetto.content import MAGIC_DECKS, Content


@pytest.fixture(scope="module")
def content():
    return Content.load()


def test_ogni_immagine_esiste_e_bimbe_non_cerca_piu_0jpg(content):
    rng = random.Random(0)
    for directory in content.images:
        for _ in range(200):
            assert content.pick_image(directory, rng).is_file()


def test_mazzi_magic(content):
    for _, _, directory in MAGIC_DECKS.values():
        assert content.images[directory]


def test_colore_zona_trentino_e_altre_regioni(content):
    assert content.severity_color("Trentino-Alto Adige/Südtirol", "Trento") == "yellow"
    assert content.severity_color("Trentino-Alto Adige/Südtirol", "Bolzano/Bozen") == "orange"
    assert content.severity_color("Trentino-Alto Adige/Südtirol", "Inesistente") is None
    assert content.severity_color("Veneto", "Treviso") == "yellow"
    assert content.severity_color("Atlantide", "x") is None


def test_paesi_completi(content):
    codes = {c["cca3"] for c in content.countries}
    assert len(codes) == len(content.countries) == 250
    for c in content.countries:
        assert content.media(f"flags/{c['cca3'].lower()}.png").is_file(), c["cca3"]
        assert set(c["borders"]) <= codes, c["cca3"]
    italia = content.country_by_code("ITA")
    assert italia["name_it"] == "Italia"
    assert "Europe/Rome" in italia["timezones"]


def test_media_speciali_esistono(content):
    for name in [
        "others/cesara.jpg",
        "others/15e18.png",
        "centocentocento/118.gif",
        "centocentocento/130_MartinGarrix.gif",
        "centocentocento/Iva_Zanicchi_CAGA_in_diretta.gif",
        "centocentocento/Mr_Bean_Middle_Finger.gif",
    ]:
        assert content.media(name).is_file()
