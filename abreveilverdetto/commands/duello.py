"""🔫 DUELLO: chi spara per primo dopo il "FUOCO!", al meglio di 3.

Il "FUOCO!" arriva dopo un ritardo casuale: lo scrive il timer delle scadenze
(deadlines.py) chiamando ``on_duel_deadline``. Il bottone SPARA porta il numero
del round, così un click arrivato dopo la fine del round non vale per il successivo.

Il risultato dipende da quando i click arrivano al server, non da quando sono
stati premuti: la rete di ognuno conta. È un gioco goliardico, va bene così.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

from telegram import Bot, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ChatType
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from .. import duel
from ..duel import DuelError, DuelGame, Round
from ..registry import Callback
from ..telegram_io import HTML, Deps, deps, display_name
from ..text import esc

logger = logging.getLogger(__name__)

TITLE = "🔫 <b>DUELLO</b>"
PRIVATE_TEXT = "🔫 Il duello si fa in due: aggiungimi a un gruppo e lancia la sfida da 🎮 GIOCHI."
ACCEPT, CANCEL = "a", "x"


def fire_delay(rng: random.Random) -> timedelta:
    low, high = duel.FIRE_DELAY
    return timedelta(seconds=rng.uniform(low, high))


def _seconds(ms: int) -> str:
    return f"{ms / 1000:.2f}".replace(".", ",") + " s"


def _round_line(number: int, r: Round, game: DuelGame) -> str:
    winner = esc(game.name(r.winner))
    if r.kind == duel.FALSE_START:
        return f"Round {number}: 💥 {esc(game.name(3 - r.winner))} spara prima del via → {winner}"
    reaction = f" in {_seconds(r.reaction_ms)}" if r.reaction_ms is not None else ""
    return f"Round {number}: 🎯 {winner}{reaction}"


def render(game: DuelGame, rng: random.Random, battute: list[str]) -> str:
    c, o = esc(game.challenger_name), esc(game.opponent_name or "")
    if game.status == duel.OPEN:
        who = f"{c} sfida {esc(game.target_name)}!" if game.target_name else "A breve qualcuno accetterà la sfida."
        accept = int(duel.ACCEPT_TIMEOUT.total_seconds() // 60)
        return (
            f"{TITLE}\n{who}\n\n<i>Al meglio di 3 · spara dopo il 🔥 FUOCO!: chi spara prima del via"
            f" regala il round. La sfida scade tra {accept} minuti.</i>"
        )
    if game.status == duel.CANCELLED:
        return f"{TITLE}\nSfida annullata da {c}."
    if game.status == duel.EXPIRED:
        return f"{TITLE}\n⌛ {esc(duel.expired_notice(game))}."

    lines = [f"{TITLE}\n<b>{c} {game.challenger_score} – {game.opponent_score} {o}</b>"]
    lines += [_round_line(i, r, game) for i, r in enumerate(game.rounds, start=1)]
    if game.status == duel.FINISHED:
        (_, winner), (_, loser) = game.winner, game.loser
        lines.append(f"\n🏆 <b>Vince {esc(winner)}!</b>")
        lines.append(esc(rng.choice(battute)).format(vincitore=esc(winner), perdente=esc(loser)))
    elif game.status == duel.ARMED:
        lines.append(f"\nRound {game.round}: 🤠 pronti… non sparate prima del via!")
    else:
        seconds = int(duel.SHOOT_TIMEOUT.total_seconds())
        lines.append(f"\nRound {game.round}: 🔥 <b>FUOCO!</b> ({seconds} secondi)")
    return "\n".join(lines)


def keyboard(game: DuelGame) -> InlineKeyboardMarkup | None:
    if game.status == duel.OPEN:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("ACCETTO", callback_data=DUEL_ACTION.data(game.id, ACCEPT)),
                    InlineKeyboardButton("ANNULLA", callback_data=DUEL_ACTION.data(game.id, CANCEL)),
                ]
            ]
        )
    if game.status in (duel.ARMED, duel.FIRE):
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔫 SPARA", callback_data=DUEL_ACTION.data(game.id, game.round))]]
        )
    return None


def _is_private(message: Message) -> bool:
    return message.chat.type == ChatType.PRIVATE


async def _track(d: Deps, game: DuelGame, message_id: int) -> None:
    await d.storage.set_duel_message(game.id, message_id)
    if d.game_timer is not None:
        d.game_timer.schedule(game.deadline)


async def duello_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dal menu: sfida aperta, il primo che accetta duella."""
    d = deps(context)
    if _is_private(query.message):
        await query.edit_message_text(PRIVATE_TEXT)
        return
    user = query.from_user
    game = await d.storage.create_duel(query.message.chat.id, user.id, display_name(user), None, None, d.now())
    battute = d.content.texts["duello_battute"]
    await query.edit_message_text(render(game, d.rng, battute), parse_mode=HTML, reply_markup=keyboard(game))
    await _track(d, game, query.message.message_id)


async def _show(bot: Bot, game: DuelGame, text: str) -> None:
    try:
        await bot.edit_message_text(text, game.chat_id, game.message_id, parse_mode=HTML, reply_markup=keyboard(game))
    except BadRequest as exc:  # stesso contenuto: non è un errore
        if "not modified" not in str(exc).lower():
            raise


async def remove_expired(bot: Bot, game: DuelGame, battute: list[str]) -> None:
    """Cancella il messaggio di un duello scaduto; se non si può, lo trasforma in "⌛ …"."""
    if game.message_id is None:
        return
    try:
        await bot.delete_message(game.chat_id, game.message_id)
        return
    except TelegramError as exc:
        logger.info("Messaggio del duello %d non cancellato: %s", game.id, exc)
    try:
        await bot.edit_message_text(render(game, random.Random(), battute), game.chat_id, game.message_id)
    except TelegramError:
        logger.info("Messaggio del duello %d non modificabile", game.id)


async def on_duel_deadline(bot: Bot, d: Deps, now: datetime) -> datetime | None:
    """Dal timer: "FUOCO!" per i round pronti, annullamento per sfide e colpi mai arrivati."""
    battute = d.content.texts["duello_battute"]
    for due in await d.storage.due_duels(now):
        try:
            game, _ = await d.storage.apply_duel(due.id, lambda g: (duel.tick(g, now), None))
        except DuelError:  # un click è arrivato prima del timer e ha già cambiato lo stato
            continue
        if game.status == duel.FIRE and game.message_id is not None:
            try:
                await _show(bot, game, render(game, d.rng, battute))
            except TelegramError:
                logger.warning("FUOCO! non mostrato per il duello %d", game.id, exc_info=True)
        elif game.status == duel.EXPIRED:
            await remove_expired(bot, game, battute)
    return await d.storage.next_duel_deadline()


async def on_duel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    d = deps(context)
    _, game_id_raw, action = query.data.split(":")
    game_id = int(game_id_raw)
    user = query.from_user
    now = d.now()
    battute = d.content.texts["duello_battute"]

    game = await d.storage.get_duel(game_id)
    if game is None:
        await query.answer("Duello non trovato")
        return
    if game.is_expired(now):  # il timer non è ancora passato: si annulla qui
        await query.answer(duel.expired_notice(game))
        try:
            expired, _ = await d.storage.apply_duel(game_id, lambda g: (duel.expire(g, now), None))
        except DuelError:
            return
        await remove_expired(query.get_bot(), expired, battute)
        return

    try:
        if action == ACCEPT:
            delay = fire_delay(d.rng)
            new, _ = await d.storage.apply_duel(
                game_id, lambda g: (duel.accept(g, user.id, display_name(user), now, delay), None)
            )
            notice = "Sfida accettata: aspetta il 🔥 FUOCO!"
        elif action == CANCEL:
            new, _ = await d.storage.apply_duel(game_id, lambda g: (duel.cancel(g, user.id, now), None))
            notice = "Sfida annullata"
        else:
            delay = fire_delay(d.rng)
            new, result = await d.storage.apply_duel(game_id, lambda g: duel.shoot(g, user.id, int(action), now, delay))
            if result.kind == duel.FALSE_START:
                notice = "💥 Troppo presto! Il round va all'avversario"
            else:
                notice = f"🎯 Centro in {_seconds(result.reaction_ms)}!"
    except DuelError as exc:
        await query.answer(str(exc))
        return

    await query.answer(notice)
    try:
        await query.edit_message_text(render(new, d.rng, battute), parse_mode=HTML, reply_markup=keyboard(new))
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise
    if d.game_timer is not None:
        d.game_timer.schedule(new.deadline)


# a: accetta, x: annulla, numero: colpo nel round indicato
DUEL_ACTION = Callback("duel", r"\d+:(?:[ax]|\d{1,2})", on_duel)
