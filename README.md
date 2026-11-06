# A breve il verdetto

Bot Telegram goliardico: concettualmente da non prendere sul serio, tecnicamente sì.

Python 3.13, [python-telegram-bot](https://docs.python-telegram-bot.org/) 22 (asyncio), Postgres via asyncpg.
Pensato per girare gratis su **Koyeb** (webhook, scale-to-zero) con database su **Neon**.

## Comandi

`/start` (o `/menu`) apre il menu a bottoni: saluti, CTS, DPCM, Conte, bimbe, comune (con meteo),
COVID, giurato, torta, Fibonacci, 💯💯💯, ghesboro, Pokémon, nazione, cocktail, santi, Magic, Lercio.

| Comando | |
|---|---|
| `/fibonacci N` | Sequenza di Fibonacci di lunghezza casuale fino a N (max 10) |
| `/bravitutti` | Classifica delle vittorie a 💯💯💯 nella chat |
| (testo con "15" e "18") | Risposta sulla briscola |

### 💯💯💯
Ogni tiro vale un multiplo di 5 tra 5 e 100. Dopo il primo tiro si può tentare un secondo giro:
vince chi fa **esattamente 100**. Un tentativo al minuto per utente; record giornaliero per chat
(valore più alto ≤ 100, a parità vince chi ha usato meno giri, a parità assoluta resta il primo).
Solo chi ha avviato la partita può premere "Yes/No".

## Architettura

```
abreveilverdetto/
  __main__.py   avvio: webhook se WEBHOOK_BASE_URL è impostato, altrimenti polling
  app.py        costruzione dell'Application e registrazione degli handler
  handlers.py   handler Telegram (menu, comandi, gioco, errori)
  game.py       regole pure di 💯💯💯 e Fibonacci
  services.py   API esterne con timeout e cache (comuni, COVID, Pokédex, meteo, cocktail)
  storage.py    Postgres (produzione) / memoria (sviluppo), stessa interfaccia e stessi test
  schema.sql    schema del DB, applicato in modo idempotente a ogni avvio
  content.py    frasi (data/*.json) e immagini (media/), validate all'avvio
  text.py       formattazione HTML ed escape
data/           frasi e dataset statici
media/          immagini
scripts/        rigenerazione del dataset dei paesi e delle bandiere
tests/          pytest: logica, storage su Postgres reale, handler contro una Bot API finta
```

Scelte principali:

- **Nessuno stato in memoria.** I bottoni portano nel `callback_data` ciò che serve; partite,
  cooldown, record e vittorie stanno nel DB. Riavvii e scale-to-zero non fanno perdere nulla.
- **Operazioni atomiche** su Postgres (`INSERT … ON CONFLICT … WHERE`, `UPDATE … RETURNING`):
  doppio click e click simultanei non producono doppie vittorie o partite chiuse due volte.
- **Timeout e cache** su tutte le chiamate esterne; se un refresh fallisce si usa l'ultima copia valida.
- **Immagini caricate una volta sola**: il `file_id` restituito da Telegram viene salvato e riusato.
- **Solo HTML con escape** in tutti i messaggi (niente più errori di MarkdownV2 su nomi con `-`, `_`, `'`).
- **Nessun segreto nel repository.** Il webhook è protetto da `secret_token` (header
  `X-Telegram-Bot-Api-Secret-Token`); i log non contengono il token né la API key del meteo.

## Configurazione

Variabili d'ambiente (vedi `.env.example`):

| Variabile | Obbligatoria | Descrizione |
|---|---|---|
| `TELEGRAM_TOKEN` | sì | Token di @BotFather |
| `DATABASE_URL` | in produzione | Connection string Postgres (Neon). Senza: storage in memoria |
| `WEBHOOK_BASE_URL` | in produzione | URL pubblico del servizio. Senza: long polling |
| `WEBHOOK_SECRET` | no | Default: derivato dal token (stabile tra i riavvii) |
| `OPENWEATHERMAP_API_KEY` | no | Senza chiave `/comune` non mostra il meteo |
| `PORT` | no | Default 8000 |
| `BOT_TIMEZONE` | no | Default `Europe/Rome` |

## Messa in produzione (gratuita)

### 0. Revoca le credenziali vecchie
Token del bot e chiave OpenWeatherMap erano committati nella history pubblica del repository.
1. @BotFather → `/mybots` → il bot → *API Token* → *Revoke current token*. Usa il nuovo token.
2. OpenWeatherMap → *API keys*: elimina la chiave vecchia e generane una nuova.

### 1. Database su Neon
1. Crea un account su <https://neon.com> e un progetto (regione europea, es. Frankfurt).
2. Copia la connection string (`postgresql://…?sslmode=require…`). Va bene sia quella diretta
   sia quella *pooled*: il bot gestisce entrambe e rimuove `channel_binding`, che asyncpg non supporta.
3. Le tabelle vengono create dal bot al primo avvio.

Piano gratuito Neon (documentazione ufficiale, ottobre 2026): 1 GB per progetto, 100 CU-ore al mese;
il database si sospende quando è inattivo e si riattiva da solo alla prima connessione.

### 2. Servizio su Koyeb
1. Crea un account su <https://www.koyeb.com> e un nuovo *Web Service* da GitHub,
   repository `mfurlanetto/abreveilverdetto`, builder **Dockerfile**, istanza **Free**.
2. Porta esposta: `8000` (HTTP).
3. Variabili d'ambiente: `TELEGRAM_TOKEN`, `DATABASE_URL`, `OPENWEATHERMAP_API_KEY`
   (marcale come *secret*).
4. Dopo il primo deploy copia l'URL pubblico del servizio, impostalo in `WEBHOOK_BASE_URL`
   e rideploya. All'avvio il bot registra il webhook da solo.

L'istanza gratuita si spegne dopo 1 ora senza traffico e si riaccende alla prima richiesta
([documentazione Koyeb](https://www.koyeb.com/docs/run-and-scale/scale-to-zero)): il primo messaggio
dopo una pausa può impiegare qualche secondo. Il bot non scarta mai gli update in coda all'avvio.

Il codice non dipende da Koyeb: funziona uguale su Render, Google Cloud Run o qualsiasi host
che esegua un container ed esponga una porta HTTP.

### 3. Gruppi
Per far funzionare la risposta a "15 e 18" nei gruppi il bot deve leggere tutti i messaggi:
@BotFather → `/setprivacy` → *Disable* (poi rimuovi e riaggiungi il bot al gruppo).

## Sviluppo locale

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # inserisci almeno TELEGRAM_TOKEN (meglio un bot di test)
set -a; . ./.env; set +a
python -m abreveilverdetto          # senza WEBHOOK_BASE_URL usa il polling
```

Test e lint:

```bash
ruff format --check . && ruff check .
pytest -q                                            # i test Postgres vengono saltati
TEST_DATABASE_URL=postgresql://… pytest -q           # anche contro un Postgres reale
```

## Fonti dati

| Comando | Fonte | Note |
|---|---|---|
| comune | [matteocontrini/comuni-json](https://github.com/matteocontrini/comuni-json) | cache 24 h |
| comune (colore zona) | `data/regions_ita.json` | dati statici storici, inverno 2020-21 |
| comune (meteo) | [OpenWeatherMap Current Weather](https://openweathermap.org/current) | facoltativo |
| covid | [pcm-dpc/COVID-19](https://github.com/pcm-dpc/COVID-19) | ultimo dato: 8 gennaio 2025; il bot mostra un avviso |
| pokemon | [HybridShivam/Pokemon](https://github.com/HybridShivam/Pokemon) (nomi/tipi), [PokeAPI/sprites](https://github.com/PokeAPI/sprites) (immagini) | cache 24 h |
| nazione | [mledoze/countries](https://github.com/mledoze/countries), IANA tz database, [samayo/country-json](https://github.com/samayo/country-json) (popolazione, **non ufficiale**, ~2018) | snapshot statico in `data/countries.json`, rigenerabile con `scripts/build_countries.py` |
| cocktail | [TheCocktailDB](https://www.thecocktaildb.com/api.php) | chiave pubblica di test `1` |
