import json

import httpx
import pytest

from abreveilverdetto import services as svc
from abreveilverdetto.services import ServiceError, Services, TTLCache

COMUNI = [
    {
        "nome": "Sant'Angelo-Lodigiano",
        "cap": ["26866"],
        "provincia": {"nome": "Lodi"},
        "sigla": "LO",
        "regione": {"nome": "Lombardia"},
        "popolazione": 13000,
        "codiceCatastale": "ignorato",
    }
]
COVID = [
    {
        "data": "2025-01-07T17:00:00",
        "totale_ospedalizzati": 10,
        "terapia_intensiva": 2,
        "isolamento_domiciliare": 100,
        "deceduti": 5,
        "tamponi": 1000,
        "nuovi_positivi": 3,
    },
    {
        "data": "2025-01-08T17:00:00",
        "totale_ospedalizzati": 12,
        "terapia_intensiva": 1,
        "isolamento_domiciliare": 90,
        "deceduti": 6,
        "tamponi": 1000,
        "nuovi_positivi": 4,
    },
]
POKEDEX = {"pokemon": {"25": {"N": "pikachu", "T": [{"n": "electric", "id": 13}]}, "500": {"N": "x", "T": []}}}


def make_services(handler, key=None):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return Services(client, key)


def route(table):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        url = str(request.url).split("?")[0]
        status, body = table[url]
        return httpx.Response(status, json=body)

    return handler, calls


async def test_comuni_ridotti_e_in_cache():
    handler, calls = route({svc.COMUNI_URL: (200, COMUNI)})
    s = make_services(handler)
    first = await s.comuni()
    second = await s.comuni()
    assert first is second
    assert len(calls) == 1
    c = first[0]
    assert (c.nome, c.cap, c.provincia, c.sigla, c.regione, c.popolazione) == (
        "Sant'Angelo-Lodigiano",
        "26866",
        "Lodi",
        "LO",
        "Lombardia",
        13000,
    )


async def test_covid_variazioni_e_divisione_per_zero():
    handler, _ = route({svc.COVID_URL: (200, COVID)})
    r = await make_services(handler).covid()
    assert r.var_ospedalizzati == 2
    assert r.var_terapia_intensiva == -1
    assert r.var_tamponi == 0
    assert r.positivity is None  # prima: ZeroDivisionError


async def test_pokemon_solo_prima_generazione():
    handler, _ = route({svc.POKEDEX_URL: (200, POKEDEX)})
    s = make_services(handler)
    p = await s.pokemon(25)
    assert (p.name, p.types) == ("pikachu", ["electric"])
    assert p.image_url.endswith("/official-artwork/25.png")
    with pytest.raises(ServiceError):
        await s.pokemon(500)


async def test_meteo_disabilitato_senza_chiave():
    s = make_services(lambda r: httpx.Response(500))
    assert not s.weather_enabled
    assert await s.weather("00100") is None


async def test_meteo_ok_e_parametri():
    body = {"weather": [{"description": "cielo sereno", "icon": "01d"}], "main": {"temp": 21.37}}
    handler, calls = route({svc.WEATHER_URL: (200, body)})
    w = await make_services(handler, key="SEGRETA").weather("00100")
    assert (w.description, w.temperature) == ("cielo sereno", 21.37)
    assert w.icon_url == "https://openweathermap.org/img/wn/01d@4x.png"
    assert calls[0].url.params["zip"] == "00100,IT"


async def test_errore_non_espone_la_api_key():
    handler, _ = route({svc.WEATHER_URL: (401, {"cod": 401})})
    with pytest.raises(ServiceError) as info:
        await make_services(handler, key="SEGRETA").weather("00100")
    assert "SEGRETA" not in str(info.value)
    assert info.value.__cause__ is None
    assert info.value.__suppress_context__
    assert "HTTP 401" in str(info.value)


async def test_timeout_diventa_service_error():
    def handler(request):
        raise httpx.ReadTimeout("lento", request=request)

    with pytest.raises(ServiceError):
        await make_services(handler).random_cocktail()


async def test_cocktail_risposta_inattesa():
    handler, _ = route({svc.COCKTAIL_URL: (200, {"drinks": None})})
    with pytest.raises(ServiceError):
        await make_services(handler).random_cocktail()


async def test_ttl_cache_scade_e_usa_copia_vecchia_se_il_refresh_fallisce():
    now = [0.0]
    cache = TTLCache(clock=lambda: now[0])
    values = iter([1, 2])

    async def loader():
        return next(values)

    async def failing():
        raise ServiceError("giù")

    assert await cache.get("k", 10, loader) == 1
    now[0] = 5
    assert await cache.get("k", 10, loader) == 1
    now[0] = 11
    assert await cache.get("k", 10, loader) == 2
    now[0] = 30
    assert await cache.get("k", 10, failing) == 2
    with pytest.raises(ServiceError):
        await cache.get("altro", 10, failing)


def wiktionary_batch(*titles):
    from tests.fakes import load_wiktionary_samples

    samples = load_wiktionary_samples()
    pages = [{"title": t, "revisions": [{"slots": {"main": {"content": samples[t]}}}]} for t in titles]
    return {"batchcomplete": True, "query": {"pages": pages}}


async def test_random_words_solo_voci_italiane_con_definizioni():
    handler, calls = route({svc.WIKTIONARY_API_URL: (200, wiktionary_batch("tribunal", "casa", "fondisse", "ciao"))})
    entries = await make_services(handler).random_words()
    assert [e.title for e in entries] == ["casa", "ciao"]
    params = calls[0].url.params
    assert (params["generator"], params["grnnamespace"], params["prop"]) == ("random", "0", "revisions")
    # header che evitano il 403 del filtro anti-bot di Wikimedia
    assert calls[0].headers["Accept"] == "application/json"
    assert calls[0].headers["Accept-Encoding"] == "gzip"


async def test_random_words_riprova_e_poi_si_arrende():
    handler, calls = route({svc.WIKTIONARY_API_URL: (200, wiktionary_batch("tribunal", "EMI"))})
    with pytest.raises(ServiceError):
        await make_services(handler).random_words(attempts=3)
    assert len(calls) == 3


async def test_random_words_429_diventa_rate_limited():
    def handler(request):
        return httpx.Response(429, headers={"Retry-After": "11"}, text="You are making too many requests")

    with pytest.raises(svc.RateLimitedError) as info:
        await make_services(handler).random_words()
    assert info.value.retry_after == 11


async def test_user_agent_conforme_alle_regole_wikimedia():
    # Nome/versione, contatto (URL del progetto) e libreria: senza, Wikimedia applica limiti molto più bassi.
    s = Services.create(5, None)
    try:
        ua = s._client.headers["User-Agent"]
    finally:
        await s.close()
    assert ua == svc.USER_AGENT
    assert ua.startswith("abreveilverdetto-bot/2.0.0 (https://github.com/mfurlanetto/abreveilverdetto) httpx/")


def spark_sample():
    from pathlib import Path

    return json.loads((Path(__file__).parent / "data" / "yahoo_spark_sample.json").read_text())


async def test_market_quotes_una_richiesta_e_cache():
    from abreveilverdetto import markets

    handler, calls = route({markets.SPARK_URL: (200, spark_sample())})
    s = make_services(handler)
    first = await s.market_quotes()
    second = await s.market_quotes()
    assert first is second and len(calls) == 1  # in cache per 60 s
    params = calls[0].url.params
    assert params["symbols"].split(",") == [i.symbol for i in markets.INSTRUMENTS]
    assert (params["range"], params["interval"]) == ("1d", "1d")
    assert len(first) == 13


async def test_market_quotes_429_e_risposta_vuota():
    from abreveilverdetto import markets

    def limited(request):
        return httpx.Response(429, headers={"Retry-After": "7"})

    with pytest.raises(svc.RateLimitedError):
        await make_services(limited).market_quotes()
    handler, _ = route({markets.SPARK_URL: (200, {"spark": {"result": []}})})
    with pytest.raises(ServiceError):
        await make_services(handler).market_quotes()
