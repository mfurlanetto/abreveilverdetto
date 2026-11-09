"""Comandi che usano fonti dati esterne o dataset: COVID, comune, nazione, Pokémon, cocktail."""

from __future__ import annotations

import logging

from telegram import CallbackQuery
from telegram.ext import ContextTypes

from .. import emoji
from ..services import ServiceError
from ..telegram_io import HTML, deps, replace_with_media, replace_with_remote_photo
from ..text import esc, signed, spaced_upper, table, translate_measure

logger = logging.getLogger(__name__)


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
