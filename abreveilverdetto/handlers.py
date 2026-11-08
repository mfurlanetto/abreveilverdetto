"""Handler Telegram.

Il bot è senza stato in memoria: i bottoni portano nel ``callback_data`` tutto ciò
che serve e lo stato di gioco sta nello storage. Riavvii e scale-to-zero non
interrompono nulla, e più persone possono usare il menu nello stesso gruppo.

Formato del callback_data (max 64 byte per la Bot API):
    menu:<comando>          voce del menu principale
    cts:<n>                 numero di membri del CTS
    magic:<mazzo>|info      pesca una carta o mostra i mazzi
    c100:<id>:y|n           un altro giro a /centocentocento
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from telegram import (
    CallbackQuery,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    Message,
    Update,
    User,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from . import emoji, game
from .content import MAGIC_DECKS, Content
from .services import ServiceError, Services
from .settings import Settings
from .storage import Storage
from .text import esc, greeting, number_emoji, signed, spaced_upper, table, translate_measure

logger = logging.getLogger(__name__)

HTML = ParseMode.HTML
C100_COOLDOWN = timedelta(minutes=1)
FIBONACCI_PROMPT = "Fibonacci: numero massimo di iterazioni (1-10)?"
BRISCOLA = "Come fa 15+18 non fa 36 dio te maledica te do 'n sciafon che te copo d** ***"
GENERIC_ERROR = "Qualcosa è andato storto 🙈 Riprova tra poco."


@dataclass
class Deps:
    settings: Settings
    content: Content
    storage: Storage
    services: Services
    rng: random.Random

    def now(self) -> datetime:
        return datetime.now(self.settings.timezone)


def deps(context: ContextTypes.DEFAULT_TYPE) -> Deps:
    return context.application.bot_data["deps"]


def display_name(user: User) -> str:
    return user.full_name or (f"@{user.username}" if user.username else str(user.id))


# --------------------------------------------------------------------------------------
# Invio media con cache dei file_id
# --------------------------------------------------------------------------------------


async def send_media(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    path: Path,
    *,
    kind: str = "photo",
    caption: str | None = None,
) -> Message:
    """Invia un file locale riusando il file_id Telegram se già caricato.

    Il primo invio carica il file; i successivi passano solo l'identificativo.
    Se il file_id non è più valido si ricarica il file.
    """
    d = deps(context)
    send = context.bot.send_photo if kind == "photo" else context.bot.send_animation
    size = (await asyncio.to_thread(path.stat)).st_size
    key = f"{kind}:{path.relative_to(d.content.media_dir).as_posix()}:{size}"

    file_id = await d.storage.get_file_id(key)
    if file_id:
        try:
            return await send(chat_id, file_id, caption=caption, parse_mode=HTML)
        except BadRequest:
            logger.info("file_id scaduto per %s, ricarico il file", key)
            await d.storage.delete_file_id(key)

    upload = InputFile(await asyncio.to_thread(path.read_bytes), filename=path.name)
    message = await send(chat_id, upload, caption=caption, parse_mode=HTML)
    sent = message.photo[-1].file_id if kind == "photo" and message.photo else None
    if kind != "photo" and message.animation:
        sent = message.animation.file_id
    elif kind != "photo" and message.document:
        sent = message.document.file_id
    if sent:
        await d.storage.set_file_id(key, sent)
    return message


async def drop_menu(query: CallbackQuery) -> None:
    """Cancella il messaggio del menu prima di rispondere con un media."""
    try:
        await query.delete_message()
    except TelegramError:
        # Messaggio già cancellato o più vecchio di 48 ore: non è un problema.
        logger.debug("Impossibile cancellare il menu", exc_info=True)


async def replace_with_media(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    path: Path,
    *,
    kind: str = "photo",
    caption: str | None = None,
) -> None:
    await drop_menu(query)
    await send_media(context, query.message.chat.id, path, kind=kind, caption=caption)


async def replace_with_remote_photo(query: CallbackQuery, url: str, caption: str) -> None:
    """Foto da URL; se Telegram non riesce a scaricarla, ripiega sul solo testo."""
    try:
        await query.get_bot().send_photo(query.message.chat.id, url, caption=caption, parse_mode=HTML)
    except BadRequest:
        logger.warning("Telegram non ha accettato la foto remota %s", url)
        await query.edit_message_text(caption, parse_mode=HTML)
        return
    await drop_menu(query)


# --------------------------------------------------------------------------------------
# Menu
# --------------------------------------------------------------------------------------

MenuAction = Callable[[CallbackQuery, ContextTypes.DEFAULT_TYPE], Awaitable[None]]

# (chiave, etichetta); l'ordine definisce la tastiera, 3 bottoni per riga.
MENU_LAYOUT: list[list[tuple[str, str]]] = [
    [("saluti", "👋 saluti"), ("cts", "🔬 cts"), ("dpcm", "📜 dpcm")],
    [("conte", "🙇 conte"), ("bimbe", "😻 bimbe"), ("comune", "🏙 comune")],
    [("covid", "🧪 covid"), ("giurato", "🤦 giurato"), ("torta", "🥧 torta")],
    [("fibonacci", "🔢 fibonacci"), ("c100", "💯 💯 💯"), ("ghesboro", "🦁 ghesboro")],
    [("pokemon", "🦕 pokemon"), ("nazione", "🌍 nazione")],
    [("cocktail", "🍸 cocktail"), ("santi", "👼 santi"), ("magic", "🃏 Magic")],
    [("lercio", "📰 Lercio.it")],
]


def menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=f"menu:{key}") for key, label in row] for row in MENU_LAYOUT]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("Seleziona comando:", reply_markup=menu_keyboard())


async def on_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    key = query.data.removeprefix("menu:")
    action = MENU_ACTIONS.get(key)
    if action is None:
        await query.edit_message_text("Comando sconosciuto. Usa /start.")
        return
    logger.info("Comando %s", key)
    await action(query, context)


async def on_stale_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bottoni di vecchi menu (versione precedente del bot o formati sconosciuti)."""
    await update.callback_query.answer("Menu scaduto: usa /start", show_alert=False)


# --------------------------------------------------------------------------------------
# Comandi testuali semplici
# --------------------------------------------------------------------------------------


async def saluti(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    template = d.content.pick_text("saluti", d.rng)
    text = template.format(greeting(d.now(), query.from_user.first_name))
    await query.edit_message_text(esc(text), parse_mode=HTML)


def _quote_action(list_name: str, prefix: str = "") -> MenuAction:
    async def action(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
        d = deps(context)
        text = d.content.pick_text(list_name, d.rng)
        await query.edit_message_text(f"{prefix}<i>“{esc(text)}”</i>", parse_mode=HTML)

    return action


async def lercio(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    text = d.content.pick_text("lercio", d.rng)
    await query.edit_message_text(f"+++ 🔴 ULTIM'ORA: {esc(text)}", parse_mode=HTML)


# --------------------------------------------------------------------------------------
# Immagini locali
# --------------------------------------------------------------------------------------


async def torta(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    await replace_with_media(query, context, d.content.pick_image("tortamele", d.rng))


async def conte(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    caption = esc(d.content.pick_text("conte", d.rng))
    await replace_with_media(query, context, d.content.pick_image("conte", d.rng), caption=caption)


async def bimbe(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    hearts = list(emoji.love.values())
    caption = "".join(d.rng.choice(hearts) for _ in range(3))
    await replace_with_media(query, context, d.content.pick_image("bimbe", d.rng), caption=caption)


async def santi(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    santo = d.rng.choice(d.content.santi)
    caption = (
        f"<b>{esc(santo['name'].upper())}</b>\n"
        f"<i>{esc(santo['func'])}</i>\n"
        f"{esc(d.content.pick_text('santi_frasi', d.rng))}"
    )
    await replace_with_media(query, context, d.content.media(f"santi/{santo['photo']}.jpg"), caption=caption)


# --------------------------------------------------------------------------------------
# CTS
# --------------------------------------------------------------------------------------


async def cts(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("5", callback_data="cts:5"), InlineKeyboardButton("10", callback_data="cts:10")]]
    )
    await query.edit_message_text("Quanti membri desideri?", reply_markup=keyboard)


async def on_cts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    d = deps(context)
    members = d.content.texts["cts_list"]
    size = min(int(query.data.removeprefix("cts:")), len(members))
    lines = ["<b>Comitato Tecnico-Scientifico</b>"] + [f"∘ {esc(m)}" for m in d.rng.sample(members, size)]
    await query.edit_message_text("\n".join(lines), parse_mode=HTML)


# --------------------------------------------------------------------------------------
# Magic
# --------------------------------------------------------------------------------------


async def magic(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [
        InlineKeyboardButton(f"{icon}{label}", callback_data=f"magic:{key}")
        for key, (icon, label, _) in MAGIC_DECKS.items()
    ]
    buttons.append(InlineKeyboardButton("ℹ Info", callback_data="magic:info"))
    keyboard = InlineKeyboardMarkup([buttons[:3], buttons[3:]])
    await query.edit_message_text("Choose Card Type", reply_markup=keyboard)


async def on_magic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    d = deps(context)
    choice = query.data.removeprefix("magic:")
    if choice == "info":
        lines = ["<b>DECKS</b>"] + [
            f"{icon} <i>{label}</i>: {len(d.content.images[directory])}"
            for icon, label, directory in MAGIC_DECKS.values()
        ]
        await query.edit_message_text("\n".join(lines), parse_mode=HTML)
        return
    _, _, directory = MAGIC_DECKS[choice]
    await replace_with_media(query, context, d.content.pick_image(directory, d.rng))


# --------------------------------------------------------------------------------------
# Fonti esterne
# --------------------------------------------------------------------------------------


async def covid(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    r = await d.services.covid()
    e = emoji.covid
    lines = [f"Ultimo aggiornamento: {r.date:%d/%m/%Y} alle {r.date:%H:%M}"]
    age_days = (d.now().replace(tzinfo=None) - r.date).days
    if age_days > 30:
        lines.append(f"⚠️ Il dataset della Protezione Civile non è aggiornato da {age_days} giorni")
    lines += [
        f"{e['biohazard']} {e['thermoFace']}  <i>{signed(r.nuovi_positivi)}</i>",
        f"{e['hospital']} {e['maskFace']}  <i>{r.ospedalizzati:,}</i> ({signed(r.var_ospedalizzati)})",
        f"{e['hospital']} {e['bed']}  <i>{r.terapia_intensiva:,}</i> ({signed(r.var_terapia_intensiva)})",
        f"{e['house']} {e['thermoFace']}  <i>{r.isolamento:,}</i> ({signed(r.var_isolamento)})",
        f"{e['latinCross']} {e['angel']}  <i>{r.deceduti:,}</i> ({signed(r.var_deceduti)})",
        f"{e['nose']} {e['testTube']}  <i>{r.tamponi:,}</i> ({signed(r.var_tamponi)})",
    ]
    if r.positivity is not None:
        lines.append(f"{e['biohazard']} / {e['testTube']} {r.positivity:.3}%")
    await query.edit_message_text("\n".join(lines), parse_mode=HTML)


async def comune(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    c = d.rng.choice(await d.services.comuni())
    color = d.content.severity_color(c.regione, c.provincia)
    zone = emoji.zone_color.get(color, "") if color else ""
    title = f"{zone} <b>{esc(spaced_upper(c.nome))}</b> {zone}".strip()
    rows = [f"{c.cap} {c.provincia} ({c.sigla})", f"{c.popolazione:,} abitanti"]

    weather = None
    if d.services.weather_enabled:
        try:
            weather = await d.services.weather(c.cap)
        except ServiceError:
            logger.warning("Meteo non disponibile per %s", c.cap, exc_info=True)
    if weather:
        rows.append(f"{weather.temperature:.1f} °C - {weather.description.capitalize()}")

    caption = f"{title}\n<pre>{esc(chr(10).join(rows))}</pre>"
    if weather:
        await replace_with_remote_photo(query, weather.icon_url, caption)
    else:
        await query.edit_message_text(caption, parse_mode=HTML)


def _country_name(country: dict) -> str:
    return country.get("name_it") or country["name"]


async def nazione(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    country = d.rng.choice(d.content.countries)
    region = country["region"] + (f", {country['subregion']}" if country.get("subregion") else "")
    rows = [
        ("Capitale", ", ".join(country["capital"]) or "-"),
        ("Paese in", region),
    ]
    if country.get("population"):
        rows.append(("Popolazione", f"{country['population']:,}"))
    if country.get("area"):
        rows.append(("Area", f"{country['area']:,.0f} km²"))
    if country["currencies"]:
        rows.append(("Moneta", "\n".join(f"{c['name']} ({c['code']})" for c in country["currencies"])))
    if country["languages"]:
        rows.append(("Lingua", "\n".join(country["languages"])))
    if country["timezones"]:
        rows.append(("Fuso orario", "\n".join(country["timezones"])))
    borders = [d.content.country_by_code(code) for code in country["borders"]]
    if borders:
        rows.append(("Confini", "\n".join(_country_name(b) for b in borders if b)))

    caption = f"{country['flag_emoji']} <b>{esc(spaced_upper(_country_name(country)))}</b>\n{table(rows)}"
    if len(caption) > 1024:  # limite delle didascalie: ripiega su foto + messaggio
        await replace_with_media(query, context, d.content.media(f"flags/{country['cca3'].lower()}.png"))
        await context.bot.send_message(query.message.chat.id, caption, parse_mode=HTML)
        return
    await replace_with_media(query, context, d.content.media(f"flags/{country['cca3'].lower()}.png"), caption=caption)


CESARA_ODDS = (151, 171)  # 20 possibilità su 171 di pescare la carta speciale


async def pokemon(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    number = d.rng.randint(1, CESARA_ODDS[1])
    if number > CESARA_ODDS[0]:
        heart = emoji.love["redHeart"]
        caption = f"#0 - <b>CESARA BUONAMICI</b>\nType(s): {heart}{heart}"
        await replace_with_media(query, context, d.content.media("others/cesara.jpg"), caption=caption)
        return
    p = await d.services.pokemon(number)
    types = "".join(emoji.pkmn_type.get(t, "") for t in p.types)
    caption = f"#{p.number} - <b>{esc(p.name.upper())}</b>\nType(s): {types}"
    await replace_with_remote_photo(query, p.image_url, caption)


def format_cocktail(drink: dict) -> str:
    e = emoji.cocktails
    lines = [
        f"<b>“{esc(drink.get('strDrink', '?').upper())}”</b>",
        f"{e['bartender']} Tipo: <i>{esc(drink.get('strCategory') or '-')}</i>",
        f"{e['glass']} Bicchiere: <i>{esc(drink.get('strGlass') or '-')}</i>",
        "~~~~~~~~~~~~~~~~~~",
        f"{e['receipt']} Ingredienti:",
    ]
    for i in range(1, 16):
        ingredient = (drink.get(f"strIngredient{i}") or "").strip()
        if not ingredient:
            continue
        measure = translate_measure(drink.get(f"strMeasure{i}"))
        lines.append(f"∘ {esc(measure) + ' di ' if measure else ''}{esc(ingredient)}")
    lines += ["~~~~~~~~~~~~~~~~~~", f"{e['spoon']} Istruzioni:", f"<i>{esc(drink.get('strInstructions') or '')}</i>"]
    return "\n".join(lines)


async def cocktail(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    drink = await d.services.random_cocktail()
    caption = format_cocktail(drink)
    image = drink.get("strDrinkThumb")
    if image and len(caption) <= 1024:
        await replace_with_remote_photo(query, image, caption)
    else:
        await query.edit_message_text(caption, parse_mode=HTML)


# --------------------------------------------------------------------------------------
# Fibonacci
# --------------------------------------------------------------------------------------


async def fibonacci_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    await drop_menu(query)
    user = query.from_user
    # ForceReply(selective) + menzione: in un gruppo il campo risposta si apre solo a chi ha cliccato.
    await context.bot.send_message(
        query.message.chat.id,
        f"{user.mention_html()} {esc(FIBONACCI_PROMPT)}",
        parse_mode=HTML,
        reply_markup=ForceReply(selective=True, input_field_placeholder="1-10"),
    )


async def fibonacci_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    raw = " ".join(context.args) if context.args else str(game.MAX_FIBONACCI)
    await update.effective_message.reply_text(esc(game.fibonacci_reply(raw, d.rng)), parse_mode=HTML)


async def fibonacci_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    await update.effective_message.reply_text(
        esc(game.fibonacci_reply(update.effective_message.text, d.rng)), parse_mode=HTML
    )


def is_fibonacci_answer(message: Message, bot_id: int) -> bool:
    replied = message.reply_to_message
    return bool(
        replied
        and replied.from_user
        and replied.from_user.id == bot_id
        and replied.text
        and replied.text.endswith(FIBONACCI_PROMPT)
    )


# --------------------------------------------------------------------------------------
# Centocentocento
# --------------------------------------------------------------------------------------


async def c100_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    user = query.from_user
    now = d.now()
    if not await d.storage.try_acquire_cooldown(user.id, now, C100_COOLDOWN):
        await query.edit_message_text("You should wait for the next try (1 minuto tra un tentativo e l'altro)")
        return

    value = game.draw(d.rng)
    if value == game.TARGET:  # niente di meglio di 100: partita chiusa al primo tiro
        await c100_finish(query, context, user, value, runs=1)
        return

    game_id = await d.storage.create_game(query.message.chat.id, user.id, value, now)
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("No", callback_data=f"c100:{game_id}:n"),
                InlineKeyboardButton("Yes", callback_data=f"c100:{game_id}:y"),
            ]
        ]
    )
    await query.edit_message_text(
        f"{esc(user.first_name)}: {number_emoji(value)}\nAnother run?", parse_mode=HTML, reply_markup=keyboard
    )


async def on_c100(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    d = deps(context)
    _, game_id_raw, answer = query.data.split(":")
    game_id = int(game_id_raw)

    game_row = await d.storage.get_game(game_id)
    if game_row is None or game_row.finished:
        await query.answer("Partita già conclusa")
        return
    if game_row.user_id != query.from_user.id:
        await query.answer("Non è la tua partita: usa /start per giocare", show_alert=True)
        return

    value = await d.storage.finish_game(game_id, query.from_user.id, d.now())
    if value is None:  # doppio click: l'altro click ha già chiuso la partita
        await query.answer("Partita già conclusa")
        return
    await query.answer()

    runs = 1
    if answer == "y":
        value += game.draw(d.rng)
        runs = 2
    await c100_finish(query, context, query.from_user, value, runs)


async def c100_finish(
    query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, user: User, value: int, runs: int
) -> None:
    d = deps(context)
    chat_id = query.message.chat.id
    name = display_name(user)
    now = d.now()

    lines = [f"{esc(user.first_name)}: {number_emoji(value)} {game.result_emoji(value)}"]
    is_best, best = await d.storage.submit_daily(chat_id, now.date(), user.id, name, value, runs)
    if is_best:
        lines.append("This is the best score for today!")
    elif best is not None:
        lines.append(
            f"Today {esc(best.user_name)} has already done the best score (value: {best.value} - runs: {best.runs})"
        )
    else:
        lines.append("Nessun punteggio valido oggi in questa chat.")

    if value == game.TARGET:
        summary = await d.storage.record_win(chat_id, user.id, name, now)
        lines.append(f"You have won {summary.wins} time{'s' if summary.wins > 1 else ''}")
        who = "You are" if summary.top_user_id == user.id else f"{esc(summary.top_user_name)} is"
        lines.append(f"{who} the top scorer with {summary.top_wins} win{'s' if summary.top_wins > 1 else ''}")

    animation = game.pick_animation(value, runs)
    if animation is None:
        await query.edit_message_text("\n".join(lines), parse_mode=HTML)
        return
    caption = esc(animation.caption) if animation.caption else "\n".join(lines)
    await replace_with_media(query, context, d.content.media(animation.file), kind="animation", caption=caption)


async def bravitutti(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    rows = await d.storage.leaderboard(update.effective_chat.id)
    if not rows:
        await update.effective_message.reply_text("Nessuna vittoria registrata in questa chat. Ancora.")
        return
    names = [name if len(name) <= 20 else name[:19] + "…" for name, _ in rows]
    width = max(len(n) for n in names) + 2
    body = "\n".join(f"{n + ':':<{width}}{wins:>4}" for n, (_, wins) in zip(names, rows, strict=True))
    await update.effective_message.reply_text(f"<b>HIGHSCORES</b>\n<pre>{esc(body)}</pre>", parse_mode=HTML)


# --------------------------------------------------------------------------------------
# Messaggi liberi
# --------------------------------------------------------------------------------------

_FIFTEEN = re.compile(r"(?<!\d)15(?!\d)")
_EIGHTEEN = re.compile(r"(?<!\d)18(?!\d)")


def mentions_15_and_18(text: str) -> bool:
    return bool(_FIFTEEN.search(text) and _EIGHTEEN.search(text))


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if is_fibonacci_answer(message, context.bot.id):
        await fibonacci_answer(update, context)
        return
    if mentions_15_and_18(message.text):
        d = deps(context)
        await send_media(context, message.chat.id, d.content.media("others/15e18.png"), caption=esc(BRISCOLA))


# --------------------------------------------------------------------------------------
# Errori
# --------------------------------------------------------------------------------------


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Nel log solo identificativi, non l'intero Update (contiene dati personali).
    where = ""
    if isinstance(update, Update):
        where = (
            f" (update_id={update.update_id}, chat_id={update.effective_chat.id if update.effective_chat else None})"
        )
    logger.error("Errore durante la gestione di un update%s", where, exc_info=context.error)

    if not isinstance(update, Update):
        return
    try:
        if update.callback_query:
            await update.callback_query.answer(GENERIC_ERROR, show_alert=True)
        elif update.effective_message:
            await update.effective_message.reply_text(GENERIC_ERROR)
    except TelegramError:
        logger.debug("Impossibile notificare l'errore all'utente", exc_info=True)


MENU_ACTIONS: dict[str, MenuAction] = {
    "saluti": saluti,
    "cts": cts,
    "dpcm": _quote_action("dpcm"),
    "conte": conte,
    "bimbe": bimbe,
    "comune": comune,
    "covid": covid,
    "giurato": _quote_action("giurato"),
    "torta": torta,
    "fibonacci": fibonacci_menu,
    "c100": c100_menu,
    "ghesboro": _quote_action("ghesboro"),
    "pokemon": pokemon,
    "nazione": nazione,
    "cocktail": cocktail,
    "santi": santi,
    "magic": magic,
    "lercio": lercio,
}
