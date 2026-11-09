import itertools
import logging

import pytest
from telegram import Update

from abreveilverdetto.app import build_application
from abreveilverdetto.commands import COMMANDS
from abreveilverdetto.commands.fibonacci import FIBONACCI_PROMPT
from abreveilverdetto.content import Content
from abreveilverdetto.errors import GENERIC_ERROR
from abreveilverdetto.services import Weather
from abreveilverdetto.settings import Settings
from abreveilverdetto.storage import MemoryStorage
from tests.fakes import BOT_ID, FakeBotAPI, FakeServices, ScriptedRandom

CHAT = -100500
ALICE = {"id": 1, "is_bot": False, "first_name": "Alice", "username": "alice_x"}
BOB = {"id": 2, "is_bot": False, "first_name": "Bob <3"}
CARL = {"id": 3, "is_bot": False, "first_name": "Carl & Co"}
_ids = itertools.count(1)


@pytest.fixture(scope="module")
def content():
    return Content.load()


class Harness:
    def __init__(self, content):
        self.api = FakeBotAPI()
        self.rng = ScriptedRandom(0)
        self.services = FakeServices()
        self.storage = MemoryStorage()
        self.app = build_application(
            Settings.from_env({"TELEGRAM_TOKEN": "123:TEST"}),
            content=content,
            storage=self.storage,
            services=self.services,
            rng=self.rng,
            bot_request=self.api,
        )

    async def __aenter__(self):
        await self.app.initialize()
        return self

    async def __aexit__(self, *exc):
        await self.app.shutdown()

    async def feed(self, payload: dict) -> None:
        payload = {"update_id": next(_ids), **payload}
        await self.app.process_update(Update.de_json(payload, self.app.bot))

    def _message(self, text, user=ALICE, reply_to=None, **extra):
        msg = {
            "message_id": next(_ids),
            "date": 0,
            "chat": {"id": CHAT, "type": "supergroup"},
            "from": user,
            "text": text,
            **extra,
        }
        if text.startswith("/"):
            msg["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
        if reply_to:
            msg["reply_to_message"] = reply_to
        return msg

    async def text(self, text, **kwargs):
        await self.feed({"message": self._message(text, **kwargs)})

    async def click(self, data, user=ALICE):
        menu = {
            "message_id": 77,
            "date": 0,
            "chat": {"id": CHAT, "type": "supergroup"},
            "from": {"id": BOT_ID, "is_bot": True, "first_name": "Bot"},
            "text": "Seleziona comando:",
        }
        await self.feed(
            {
                "callback_query": {
                    "id": str(next(_ids)),
                    "from": user,
                    "chat_instance": "x",
                    "message": menu,
                    "data": data,
                }
            }
        )


@pytest.fixture
async def h(content, caplog):
    caplog.set_level(logging.INFO)
    async with Harness(content) as harness:
        yield harness
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert not errors or getattr(harness, "expect_errors", False), [r.getMessage() for r in errors]


def buttons(call):
    markup = call.params["reply_markup"]
    return [b for row in markup["inline_keyboard"] for b in row]


async def test_start_mostra_il_menu(h):
    await h.text("/start")
    call = h.api.last("sendMessage")
    data = [b["callback_data"] for b in buttons(call)]
    assert len(data) == 19
    assert set(d.removeprefix("menu:") for d in data) == set(COMMANDS.keys())


@pytest.mark.parametrize("key", sorted(COMMANDS.keys()))
async def test_ogni_voce_del_menu_risponde_senza_errori(h, key):
    await h.click(f"menu:{key}")
    methods = h.api.methods()
    assert methods[0] == "answerCallbackQuery"
    assert any(m in methods for m in ("editMessageText", "sendPhoto", "sendAnimation", "sendMessage"))


async def test_bottone_di_un_menu_vecchio(h):
    await h.click("3")  # formato della versione precedente
    assert h.api.methods() == ["answerCallbackQuery"]
    assert "scaduto" in h.api.last("answerCallbackQuery").params["text"]


async def test_cts_estrae_membri_distinti(h):
    await h.click("menu:cts")
    assert [b["callback_data"] for b in buttons(h.api.last("editMessageText"))] == ["cts:5", "cts:10"]
    await h.click("cts:10")
    lines = h.api.last("editMessageText").params["text"].splitlines()[1:]
    assert len(lines) == len(set(lines)) == 10


async def test_magic_info_e_carta(h, content):
    await h.click("menu:magic")
    await h.click("magic:info")
    assert "Creature</i>: 56" in h.api.last("editMessageText").params["text"]
    await h.click("magic:land")
    assert "deleteMessage" in h.api.methods()
    assert h.api.last("sendPhoto").params["chat_id"] == CHAT


async def test_media_usa_il_file_id_dopo_il_primo_invio(h):
    await h.text("ma 15 e 18 fa 33?")
    first = h.api.last("sendPhoto").params["photo"]
    assert not str(first).startswith("PHOTO_")  # primo invio: upload del file
    await h.text("15+18")
    second = h.api.last("sendPhoto").params["photo"]
    assert second.startswith("PHOTO_")
    await h.text("115 e 180")  # non sono 15 e 18
    assert len([c for c in h.api.calls if c.method == "sendPhoto"]) == 2


async def test_file_id_scaduto_ricarica_il_file(h):
    await h.text("15 18")
    h.api.fail["sendPhoto"] = "Bad Request: wrong file identifier"
    await h.text("15 18")
    photos = [c.params["photo"] for c in h.api.calls if c.method == "sendPhoto"]
    assert len(photos) == 3
    assert photos[1].startswith("PHOTO_")
    assert not str(photos[2]).startswith("PHOTO_")


async def test_comune_con_meteo_e_caratteri_speciali(h):
    h.services.weather_result = Weather("cielo sereno", 21.37, "https://openweathermap.org/img/wn/01d@4x.png")
    await h.click("menu:comune")
    call = h.api.last("sendPhoto")
    assert "21.4 °C - Cielo sereno" in call.params["caption"]
    assert "&lt;" in call.params["caption"]  # testo escapato, nessun errore di parsing


async def test_comune_senza_meteo_se_il_servizio_cade(h):
    h.services.fail.add("weather")
    await h.click("menu:comune")
    assert "abitanti" in h.api.last("editMessageText").params["text"]
    assert "sendPhoto" not in h.api.methods()


async def test_foto_remota_rifiutata_ripiega_sul_testo(h):
    h.api.fail["sendPhoto"] = "Bad Request: wrong type of the web page content"
    h.rng.randints = [25]
    await h.click("menu:pokemon")
    assert "PIKACHU" in h.api.last("editMessageText").params["text"]
    assert "deleteMessage" not in h.api.methods()


async def test_pokemon_cesara(h):
    h.rng.randints = [171]
    await h.click("menu:pokemon")
    assert "CESARA BUONAMICI" in h.api.last("sendPhoto").params["caption"]


async def test_errore_di_un_servizio_avvisa_l_utente(h):
    h.expect_errors = True
    h.services.fail.add("covid")
    await h.click("menu:covid")
    answers = [c for c in h.api.calls if c.method == "answerCallbackQuery"]
    assert answers[-1].params["text"] == GENERIC_ERROR


@pytest.mark.parametrize("index", range(250))
async def test_nazione_ogni_paese(h, content, index):
    h.rng.choices = [content.countries[index]]
    await h.click("menu:nazione")
    assert h.api.last("sendPhoto")


# --- Fibonacci --------------------------------------------------------------------------


async def test_fibonacci_dal_menu_con_force_reply(h):
    await h.click("menu:fibonacci")
    prompt = h.api.last("sendMessage")
    assert prompt.params["reply_markup"]["force_reply"] is True
    replied = {
        "message_id": 5,
        "date": 0,
        "chat": {"id": CHAT, "type": "supergroup"},
        "from": {"id": BOT_ID, "is_bot": True, "first_name": "Bot"},
        "text": "Alice " + FIBONACCI_PROMPT,
    }
    h.rng.randints = [6]
    await h.text("7", reply_to=replied)
    assert h.api.last("sendMessage").params["text"] == "1, 1, 2, 3, 5, 8"


async def test_fibonacci_comando(h):
    h.rng.randints = [3]
    await h.text("/fibonacci 99")
    assert h.api.last("sendMessage").params["text"] == "Il massimo consentito è 10.\n1, 1, 2"


# --- Centocentocento --------------------------------------------------------------------


def draws(*values):
    """Valori di game.draw() -> argomenti di randrange (draw = 5 + randrange(0,100,5))."""
    return [v - 5 for v in values]


async def test_centocento_partita_completa(h):
    h.rng.randranges = draws(60, 40)
    await h.click("menu:c100")
    keyboard = [b["callback_data"] for b in buttons(h.api.last("editMessageText"))]
    game_id = keyboard[0].split(":")[1]
    assert keyboard == [f"c100:{game_id}:n", f"c100:{game_id}:y"]

    await h.click(f"c100:{game_id}:y", user=BOB)  # Bob non può giocare la partita di Alice
    assert "Non è la tua partita" in h.api.last("answerCallbackQuery").params["text"]

    await h.click(f"c100:{game_id}:y")
    caption = h.api.last("sendAnimation").params["caption"]
    assert "best score for today" in caption
    assert "You have won 1 time" in caption
    assert "You are the top scorer with 1 win" in caption

    await h.click(f"c100:{game_id}:y")  # secondo click sullo stesso bottone
    assert h.api.last("answerCallbackQuery").params["text"] == "Partita già conclusa"
    assert len([c for c in h.api.calls if c.method == "sendAnimation"]) == 1


async def test_centocento_cento_al_primo_tiro(h):
    h.rng.randranges = draws(100)
    await h.click("menu:c100")
    assert "You have won 1 time" in h.api.last("sendAnimation").params["caption"]


async def test_centocento_cooldown(h):
    h.rng.randranges = draws(30)
    await h.click("menu:c100")
    await h.click("menu:c100")
    assert "wait for the next try" in h.api.last("editMessageText").params["text"]


async def test_centocento_sballato_senza_record(h):
    h.rng.randranges = draws(90, 35)
    await h.click("menu:c100")
    game_id = buttons(h.api.last("editMessageText"))[0]["callback_data"].split(":")[1]
    await h.click(f"c100:{game_id}:y")
    assert "sendAnimation" not in h.api.methods()
    assert "Nessun punteggio valido oggi" in h.api.last("editMessageText").params["text"]


async def test_centocento_130_martin_garrix(h):
    h.rng.randranges = draws(65, 65)
    await h.click("menu:c100")
    game_id = buttons(h.api.last("editMessageText"))[0]["callback_data"].split(":")[1]
    await h.click(f"c100:{game_id}:y")
    assert h.api.last("sendAnimation").params["caption"].startswith("130 km/h!")


async def test_record_di_un_altro_utente_e_classifica(h):
    h.rng.randranges = draws(80)
    await h.click("menu:c100")
    gid = buttons(h.api.last("editMessageText"))[0]["callback_data"].split(":")[1]
    await h.click(f"c100:{gid}:n")
    h.rng.randranges = draws(50)
    await h.click("menu:c100", user=BOB)
    gid = buttons(h.api.last("editMessageText"))[0]["callback_data"].split(":")[1]
    await h.click(f"c100:{gid}:n", user=BOB)
    text = h.api.last("editMessageText").params["text"]
    assert "Today Alice has already done the best score (value: 80 - runs: 1)" in text

    h.rng.randranges = draws(100)
    await h.click("menu:c100", user=CARL)  # Bob è ancora in cooldown
    await h.text("/bravitutti")
    board = h.api.last("sendMessage").params["text"]
    assert "Carl &amp; Co:" in board


async def test_layout_del_menu_invariato(h):
    await h.text("/start")
    rows = [[b["text"] for b in row] for row in h.api.last("sendMessage").params["reply_markup"]["inline_keyboard"]]
    assert rows == [
        ["👋 SALUTI", "🔬 CTS", "📜 DPCM"],
        ["🙇 CONTE", "😻 BIMBE", "🏙 COMUNE"],
        ["🧪 COVID", "🤦 GIURATO", "🥧 TORTA"],
        ["🔢 FIBONACCI", "💯 💯 💯", "🦁 GHESBORO"],
        ["🦕 POKEMON", "🌍 NAZIONE"],
        ["🍸 COCKTAIL", "👼 SANTI", "🃏 MAGIC"],
        ["📰 LERCIO.IT", "📖 PAROLA"],
    ]


async def test_alias_menu(h):
    await h.text("/menu")
    assert h.api.last("sendMessage").params["text"] == "Seleziona comando:"


async def test_avvio_pubblica_i_comandi_slash(h):
    await h.app.post_init(h.app)
    commands = h.api.last("setMyCommands").params["commands"]
    assert [c["command"] for c in commands] == ["start", "fibonacci", "bravitutti", "parola", "trombin"]


async def test_avvio_prosegue_se_set_my_commands_fallisce(h):
    h.api.fail["setMyCommands"] = "Bad Request: boom"
    await h.app.post_init(h.app)  # nessuna eccezione


async def test_parola_mostra_definizione_e_attribuzione(h):
    h.rng.choices = []  # scelta casuale vera tra le voci finte
    await h.click("menu:parola")
    call = h.api.last("editMessageText")
    text = call.params["text"]
    assert text.startswith("📖 <b>")
    assert "Wikizionario" in text and "CC BY-SA 4.0" in text
    assert call.params["link_preview_options"]["is_disabled"] is True


async def test_parola_con_limite_di_wikimedia(h):
    h.services.fail.add("words_rate_limited")
    await h.click("menu:parola")
    assert "rallentare" in h.api.last("editMessageText").params["text"]


async def test_parola_come_slash_command_risponde_con_un_nuovo_messaggio(h):
    await h.text("/parola")
    call = h.api.last("sendMessage")
    assert call.params["text"].startswith("📖 <b>")
    assert "CC BY-SA 4.0" in call.params["text"]
    assert call.params["link_preview_options"]["is_disabled"] is True
    assert "editMessageText" not in h.api.methods()


async def test_parola_slash_con_limite_di_wikimedia(h):
    h.services.fail.add("words_rate_limited")
    await h.text("/parola")
    assert "rallentare" in h.api.last("sendMessage").params["text"]


async def test_tutte_le_etichette_dei_pulsanti_in_maiuscolo(h):
    h.rng.randranges = draws(60)
    await h.text("/start")
    await h.click("menu:cts")
    await h.click("menu:magic")
    await h.click("menu:c100")
    labels = [
        b["text"]
        for c in h.api.calls
        if isinstance(c.params.get("reply_markup"), dict)
        for row in c.params["reply_markup"].get("inline_keyboard", [])
        for b in row
    ]
    assert len(labels) == 19 + 2 + 6 + 2
    assert all(label == label.upper() for label in labels), [x for x in labels if x != x.upper()]


async def test_trombin(h):
    await h.text("/trombin")
    text = h.api.last("sendMessage").params["text"]
    assert text.startswith("📈 <b>TROMBIN</b>")
    assert "FTSE MIB" in text and "Brent" in text and "Yahoo Finance" in text


async def test_trombin_con_limite_di_yahoo(h):
    h.services.fail.add("markets_rate_limited")
    await h.text("/trombin")
    assert "rallentare" in h.api.last("sendMessage").params["text"]


async def test_trombin_errore_generico(h):
    h.expect_errors = True
    h.services.fail.add("markets")
    await h.text("/trombin")
    assert h.api.last("sendMessage").params["text"] == GENERIC_ERROR
