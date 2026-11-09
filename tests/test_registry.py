import pytest

from abreveilverdetto.commands import COMMANDS
from abreveilverdetto.commands.images import MAGIC_PICK
from abreveilverdetto.commands.quotes import CTS_SIZE
from abreveilverdetto.registry import Callback, MenuCommand, Registry, RegistryError, SlashCommand


async def noop(*_):
    return None


def menu(key, row=0, callbacks=(), label=None):
    return MenuCommand(key, label if label is not None else key, noop, row=row, callbacks=callbacks)


def test_registro_reale_valido_e_completo():
    reg = COMMANDS
    assert len(reg.keys()) == 19
    assert {cb.prefix for cb in reg.callbacks()} == {"cts", "magic", "c100"}
    assert [len(r) for r in reg.layout()] == [3, 3, 3, 3, 2, 3, 2]


def test_callback_data_validati():
    cb = Callback("c100", r"\d+:[yn]", noop)
    assert cb.data(42, "y") == "c100:42:y"
    with pytest.raises(RegistryError):
        cb.data("abc", "y")  # non rispetta il pattern
    with pytest.raises(RegistryError):
        cb.data("9" * 70, "y")  # oltre 64 byte
    assert CTS_SIZE.data(5) == "cts:5"
    assert MAGIC_PICK.data("info") == "magic:info"


def test_regex_ancorata():
    import re

    cb = Callback("cts", "5|10", noop)
    assert re.match(cb.regex, "cts:10")
    assert not re.match(cb.regex, "cts:100")
    assert not re.match(cb.regex, "xcts:5")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"menu": (menu("a"), menu("a"))}, "chiave duplicata"),
        ({"menu": (menu("A"),)}, "solo lettere minuscole"),
        ({"menu": (menu("a", label=" "),)}, "etichetta vuota"),
        ({"menu": (menu("a", row=0), menu("b", row=2))}, "non consecutive"),
        ({"menu": tuple(menu(f"k{i}") for i in range(9))}, "max 8"),
        ({"menu": (menu("a", callbacks=(Callback("menu", "x", noop),)),)}, "già usato"),
        (
            {
                "menu": (
                    menu("a", callbacks=(Callback("p", "x", noop),)),
                    menu("b", callbacks=(Callback("p", "y", noop),)),
                )
            },
            "già usato da a",
        ),
        ({"menu": (menu("a", callbacks=(Callback("p", "(", noop),)),)}, "regex"),
        ({"menu": (menu("a" * 70),)}, "64 byte"),
        ({"menu": (), "slash": (SlashCommand(("Start",), noop, "x"),)}, "nome non valido"),
        ({"menu": (), "slash": (SlashCommand(("a",), noop, "x"), SlashCommand(("a",), noop, "y"))}, "duplicato"),
        ({"menu": (), "slash": (SlashCommand(("a",), noop, ""),)}, "descrizione"),
    ],
)
def test_registro_incoerente_rifiutato(kwargs, message):
    with pytest.raises(RegistryError, match=message):
        Registry(**kwargs)


def test_errori_riportati_tutti_insieme():
    with pytest.raises(RegistryError) as info:
        Registry(menu=(menu("A"), menu("A", row=3)))
    text = str(info.value)
    assert "solo lettere minuscole" in text
    assert "chiave duplicata" in text
    assert "non consecutive" in text
