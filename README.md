# A breve il verdetto

Bot Telegram goliardico: concettualmente da non prendere sul serio, tecnicamente sì.

Python 3.13, [python-telegram-bot](https://docs.python-telegram-bot.org/) 22 (asyncio), Postgres via asyncpg.
Pensato per girare gratis su **Render** (web service Docker, webhook) con database su **Neon**.

## Comandi

`/start` (o `/menu`) apre il menu a bottoni: saluti, CTS, DPCM, Conte, bimbe, comune (con meteo),
COVID, giurato, torta, Fibonacci, 💯💯💯, ghesboro, Pokémon, nazione, cocktail, santi, Magic, Lercio,
parola (parola a caso dal Wikizionario con la sua definizione).

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
  __main__.py   avvio: webhook se c'è un URL pubblico (WEBHOOK_BASE_URL/RENDER_EXTERNAL_URL), altrimenti polling
  app.py        costruzione dell'Application e registrazione degli handler
  commands/     comandi divisi per tipo; __init__.py contiene il registro COMMANDS e il menu
    quotes.py       frasi a caso e CTS
    images.py       immagini locali e Magic
    external.py     COVID, comune, nazione, Pokémon, cocktail
    centocento.py   💯💯💯 e /bravitutti
    fibonacci.py    Fibonacci (menu e /fibonacci)
    chat.py         messaggi liberi (15 e 18, risposte a Fibonacci)
    dizionario.py   parola a caso dal Wikizionario
  registry.py   dichiarazione e validazione dei comandi
  telegram_io.py dipendenze condivise e invio di media con cache dei file_id
  errors.py     gestione degli errori
  game.py       regole pure di 💯💯💯 e Fibonacci
  wiktionary.py estrazione delle definizioni italiane dal wikitext del Wikizionario
  services.py   API esterne con timeout e cache (comuni, COVID, Pokédex, meteo, cocktail, Wikizionario)
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

## Aggiungere un comando

Scrivi la funzione nel modulo di `abreveilverdetto/commands/` del tipo giusto (o in uno nuovo)
e aggiungila al registro `COMMANDS` in `abreveilverdetto/commands/__init__.py`:

```python
MenuCommand("chiave", "🎲 etichetta", funzione, row=2)
```

- `funzione(query, context)` riceve il click sul bottone del menu.
- `row` è la riga del menu; l'ordine nella lista è l'ordine dei bottoni nella riga.
- Se il comando ha bottoni propri, dichiara un `Callback("prefisso", "regex", handler)` in
  `callbacks=(...)` e genera il `callback_data` con `Callback.data(...)`.
- I comandi slash vanno in `slash=(SlashCommand(("nome",), handler, "descrizione"),)`:
  all'avvio il bot pubblica l'elenco su Telegram per l'autocompletamento.

Chiavi o prefissi duplicati, righe non consecutive, nomi non validi e `callback_data` oltre
i 64 byte fanno fallire l'avvio (e i test) con l'elenco degli errori.

## Configurazione

Variabili d'ambiente (vedi `.env.example`):

| Variabile | Obbligatoria | Descrizione |
|---|---|---|
| `TELEGRAM_TOKEN` | sì | Token di @BotFather |
| `DATABASE_URL` | in produzione | Connection string Postgres (Neon). Senza: storage in memoria |
| `WEBHOOK_BASE_URL` | no | URL pubblico del servizio. Su Render si usa `RENDER_EXTERNAL_URL`. Senza nessuno dei due: long polling |
| `WEBHOOK_SECRET` | no | Default: derivato dal token (stabile tra i riavvii) |
| `OPENWEATHERMAP_API_KEY` | no | Senza chiave `/comune` non mostra il meteo |
| `PORT` | no | Default 8000 (Render la imposta da sé, 10000) |
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

### 2. Web service su Render
Due modi equivalenti:

- **Blueprint**: Dashboard → *New* → *Blueprint* → repository `mfurlanetto/abreveilverdetto`.
  Render legge `render.yaml` (web service Docker, piano Free, Frankfurt) e chiede i valori di
  `TELEGRAM_TOKEN`, `DATABASE_URL` e `OPENWEATHERMAP_API_KEY`.
- **Manuale**: *New* → *Web Service* → repository → *Language* **Docker**, *Instance Type* **Free**,
  regione Frankfurt; in *Environment* aggiungi le stesse tre variabili.

Non servono altre impostazioni: Render imposta `PORT` e `RENDER_EXTERNAL_URL`, e all'avvio il bot
registra da solo il webhook su `https://<servizio>.onrender.com/telegram`. Lascia vuoto l'health check.

Piano Free ([documentazione Render](https://render.com/docs/free)): 750 ore-istanza al mese per workspace,
consumate solo mentre il servizio è acceso; si spegne dopo 15 minuti senza traffico e si riaccende
in circa un minuto alla prima richiesta. Telegram ritenta la consegna, quindi il primo messaggio dopo
una pausa arriva in ritardo ma non va perso (il bot non scarta mai gli update in coda). Non usare il
Postgres gratuito di Render: scade dopo 30 giorni.

Il codice non dipende da Render: funziona su qualsiasi host che esegua un container ed esponga una porta HTTP
(in quel caso imposta `WEBHOOK_BASE_URL`).

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
| parola | [Wikizionario](https://it.wiktionary.org) (API MediaWiki) | in tempo reale; contenuti **CC BY-SA 4.0**: ogni risposta cita la voce e la licenza |

### Wikizionario
- Ogni click fa una richiesta all'API con 20 pagine casuali; il bot sceglie una di quelle con una
  sezione italiana e almeno una definizione (circa metà delle pagine è in altre lingue).
- Wikimedia richiede uno User-Agent con un contatto, che il bot invia
  ([linee guida](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_API_Usage_Guidelines)),
  e applica un limite per indirizzo IP ai client non autenticati
  ([limiti](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits)). Se risponde 429 il bot
  avvisa di riprovare dopo un minuto. Su un host con IP di uscita condivisi il limite può
  scattare anche per traffico di altri.
- `tests/data/wiktionary_samples.json` contiene voci reali del Wikizionario (CC BY-SA 4.0,
  autori: contributori del Wikizionario) usate per testare il parser.
