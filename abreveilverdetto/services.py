"""Accesso alle fonti dati esterne, con timeout e cache in memoria.

Ogni chiamata ha un timeout: un'API lenta non può più bloccare il bot.
I dataset grandi (comuni 1,9 MB, COVID 1,4 MB, Pokédex 0,6 MB) vengono scaricati
una volta e tenuti in cache, ridotti ai soli campi usati.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

import httpx

from . import __version__, wiktionary

logger = logging.getLogger(__name__)

T = TypeVar("T")

COMUNI_URL = "https://raw.githubusercontent.com/matteocontrini/comuni-json/master/comuni.json"
COVID_URL = (
    "https://raw.githubusercontent.com/pcm-dpc/COVID-19/master/dati-json/dpc-covid19-ita-andamento-nazionale.json"
)
POKEDEX_URL = "https://raw.githubusercontent.com/HybridShivam/Pokemon/master/src/dataSet/pokemon.json"
POKEMON_ARTWORK_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{}.png"
)
COCKTAIL_URL = "https://www.thecocktaildb.com/api/json/v1/1/random.php"
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
WEATHER_ICON_URL = "https://openweathermap.org/img/wn/{}@4x.png"
WIKTIONARY_API_URL = "https://it.wiktionary.org/w/api.php"

# Wikimedia chiede uno User-Agent descrittivo con un contatto (qui l'URL del progetto):
# https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_API_Usage_Guidelines
# Con gli header predefiniti di httpx (Accept: */*, Accept-Encoding: gzip, deflate) il filtro
# anti-bot di Wikimedia risponde 403 "Please respect our robot policy" anche con uno User-Agent
# conforme; con questi header la stessa richiesta passa (verificato il 9/11/2026).
WIKIMEDIA_HEADERS = {"Accept": "application/json", "Accept-Encoding": "gzip"}

USER_AGENT = (
    f"abreveilverdetto-bot/{__version__} (https://github.com/mfurlanetto/abreveilverdetto) httpx/{httpx.__version__}"
)

HOUR = 3600.0
DAY = 24 * HOUR


class ServiceError(RuntimeError):
    """Una fonte esterna non ha risposto o ha risposto in modo inatteso."""


class RateLimitedError(ServiceError):
    """La fonte esterna chiede di rallentare (HTTP 429)."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class TTLCache:
    """Cache asincrona con scadenza; un solo download alla volta per chiave."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._values: dict[str, tuple[float, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def get(self, key: str, ttl: float, loader: Callable[[], Awaitable[T]]) -> T:
        entry = self._values.get(key)
        if entry and self._clock() - entry[0] < ttl:
            return entry[1]
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            entry = self._values.get(key)
            if entry and self._clock() - entry[0] < ttl:
                return entry[1]
            try:
                value = await loader()
            except Exception:
                if entry is not None:  # meglio un dato vecchio che nessun dato
                    logger.warning("Aggiornamento di %s fallito, uso la copia in cache", key, exc_info=True)
                    return entry[1]
                raise
            self._values[key] = (self._clock(), value)
            return value


@dataclass(frozen=True)
class Comune:
    nome: str
    cap: str
    provincia: str
    sigla: str
    regione: str
    popolazione: int


@dataclass(frozen=True)
class CovidReport:
    date: datetime
    nuovi_positivi: int
    ospedalizzati: int
    var_ospedalizzati: int
    terapia_intensiva: int
    var_terapia_intensiva: int
    isolamento: int
    var_isolamento: int
    deceduti: int
    var_deceduti: int
    tamponi: int
    var_tamponi: int

    @property
    def positivity(self) -> float | None:
        return 100 * self.nuovi_positivi / self.var_tamponi if self.var_tamponi > 0 else None


@dataclass(frozen=True)
class Weather:
    description: str
    temperature: float
    icon_url: str


@dataclass(frozen=True)
class Pokemon:
    number: int
    name: str
    types: list[str]

    @property
    def image_url(self) -> str:
        return POKEMON_ARTWORK_URL.format(self.number)


class Services:
    def __init__(self, client: httpx.AsyncClient, weather_api_key: str | None = None) -> None:
        self._client = client
        self._cache = TTLCache()
        self._weather_key = weather_api_key

    @classmethod
    def create(cls, timeout: float, weather_api_key: str | None) -> Services:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        return cls(client, weather_api_key)

    async def close(self) -> None:
        await self._client.aclose()

    @property
    def weather_enabled(self) -> bool:
        return bool(self._weather_key)

    async def _get_json(self, url: str, *, headers: dict[str, str] | None = None, **params: Any) -> Any:
        try:
            response = await self._client.get(url, params=params or None, headers=headers)
            if response.status_code == 429:
                retry = response.headers.get("Retry-After", "")
                raise RateLimitedError(
                    f"{httpx.URL(url).host} chiede di rallentare (HTTP 429)",
                    int(retry) if retry.isdigit() else None,
                )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # "from None": l'eccezione originale contiene l'URL completo, che per il
            # meteo include la API key, e finirebbe nei log con il traceback.
            status = f" HTTP {exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError) else ""
            raise ServiceError(f"Richiesta a {httpx.URL(url).host} fallita: {type(exc).__name__}{status}") from None

    # --- Comuni ---------------------------------------------------------------------

    async def comuni(self) -> list[Comune]:
        async def load() -> list[Comune]:
            raw = await self._get_json(COMUNI_URL)
            return [
                Comune(
                    nome=c["nome"],
                    cap=c["cap"][0] if c.get("cap") else "",
                    provincia=c["provincia"]["nome"],
                    sigla=c["sigla"],
                    regione=c["regione"]["nome"],
                    popolazione=int(c.get("popolazione") or 0),
                )
                for c in raw
            ]

        return await self._cache.get("comuni", DAY, load)

    async def weather(self, cap: str) -> Weather | None:
        if not self._weather_key or not cap:
            return None
        data = await self._get_json(WEATHER_URL, zip=f"{cap},IT", units="metric", lang="it", appid=self._weather_key)
        try:
            return Weather(
                description=data["weather"][0]["description"],
                temperature=float(data["main"]["temp"]),
                icon_url=WEATHER_ICON_URL.format(data["weather"][0]["icon"]),
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ServiceError("Risposta meteo inattesa") from exc

    # --- COVID ----------------------------------------------------------------------

    async def covid(self) -> CovidReport:
        async def load() -> CovidReport:
            data = await self._get_json(COVID_URL)
            if len(data) < 2:
                raise ServiceError("Dataset COVID troppo corto")
            cur, prev = data[-1], data[-2]
            return CovidReport(
                date=datetime.fromisoformat(cur["data"]),
                nuovi_positivi=cur["nuovi_positivi"],
                ospedalizzati=cur["totale_ospedalizzati"],
                var_ospedalizzati=cur["totale_ospedalizzati"] - prev["totale_ospedalizzati"],
                terapia_intensiva=cur["terapia_intensiva"],
                var_terapia_intensiva=cur["terapia_intensiva"] - prev["terapia_intensiva"],
                isolamento=cur["isolamento_domiciliare"],
                var_isolamento=cur["isolamento_domiciliare"] - prev["isolamento_domiciliare"],
                deceduti=cur["deceduti"],
                var_deceduti=cur["deceduti"] - prev["deceduti"],
                tamponi=cur["tamponi"],
                var_tamponi=cur["tamponi"] - prev["tamponi"],
            )

        return await self._cache.get("covid", 6 * HOUR, load)

    # --- Pokémon --------------------------------------------------------------------

    async def pokemon(self, number: int) -> Pokemon:
        async def load() -> dict[int, Pokemon]:
            raw = await self._get_json(POKEDEX_URL)
            pokedex = {}
            for key, p in raw["pokemon"].items():
                n = int(key)
                if 1 <= n <= 151:
                    pokedex[n] = Pokemon(n, p["N"], [t["n"] for t in p.get("T", [])][:2])
            return pokedex

        pokedex = await self._cache.get("pokedex", DAY, load)
        try:
            return pokedex[number]
        except KeyError as exc:
            raise ServiceError(f"Pokémon #{number} assente dal Pokédex") from exc

    # --- Cocktail -------------------------------------------------------------------

    async def random_cocktail(self) -> dict[str, Any]:
        data = await self._get_json(COCKTAIL_URL)
        try:
            return data["drinks"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise ServiceError("Risposta TheCocktailDB inattesa") from exc

    # --- Wikizionario ---------------------------------------------------------------

    async def random_words(self, batch: int = 20, attempts: int = 3) -> list[wiktionary.Entry]:
        """Voci casuali del Wikizionario con almeno una definizione italiana.

        Una richiesta restituisce ``batch`` pagine casuali con il loro wikitext; circa
        metà sono parole italiane (il resto: altre lingue). Si ripete al massimo
        ``attempts`` volte se nessuna pagina del lotto è utilizzabile.
        """
        for _ in range(attempts):
            data = await self._get_json(
                WIKTIONARY_API_URL,
                headers=WIKIMEDIA_HEADERS,
                action="query",
                format="json",
                formatversion="2",
                generator="random",
                grnnamespace="0",
                grnlimit=str(batch),
                prop="revisions",
                rvprop="content",
                rvslots="main",
            )
            try:
                pages = data["query"]["pages"]
            except (KeyError, TypeError) as exc:
                raise ServiceError("Risposta del Wikizionario inattesa") from exc
            entries = []
            for page in pages:
                try:
                    text = page["revisions"][0]["slots"]["main"]["content"]
                except (KeyError, IndexError, TypeError):
                    continue
                entry = wiktionary.parse(page["title"], text)
                if entry.has_definitions():
                    entries.append(entry)
            if entries:
                return entries
        raise ServiceError("Nessuna voce italiana con definizioni nei lotti casuali")
