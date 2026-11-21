"""✊ MORRA: morra cinese tra due persone del gruppo, al meglio di 3.

Le mosse restano segrete: chi preme un bottone vede la propria scelta solo nella
notifica del bottone (answerCallbackQuery), il messaggio pubblico dice solo se
ha già scelto. Lo stato vive nello storage (regge riavvii e scale-to-zero).

Scadenze: 5 minuti per accettare, 60 secondi per ogni mossa. Allo scadere la
partita è annullata e il bot cancella il proprio messaggio (expire_due_games,
chiamata dal timer di deadlines.py); se Telegram non lo consente il messaggio
viene invece modificato in "⌛ …".
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import replace
from datetime import datetime

from telegram import Bot, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ChatType
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from .. import morra
from ..deadlines import retry_floor
from ..morra import MOVES, MorraError, MorraGame, RoundResult
from ..registry import Callback
from ..telegram_io import HTML, Deps, deps, display_name
from ..text import esc

logger = logging.getLogger(__name__)

TITLE = "✊✋✌️ <b>MORRA CINESE</b>"
PRIVATE_TEXT = "✊✋✌️ La morra si gioca in due: aggiungimi a un gruppo e lancia la sfida da 🎮 GIOCHI."
ACCEPT, CANCEL = "a", "x"


def _emoji(move: str) -> str:
    return MOVES[move][0]


def _round_line(number: int, c: str, o: str, game: MorraGame) -> str:
    winner = game.challenger_name if morra.round_winner(c, o) == 1 else game.opponent_name or ""
    return f"Round {number}: {_emoji(c)} vs {_emoji(o)} → {esc(winner)}"


def _why(result: RoundResult) -> str:
    if result.winner == 1:
        return morra.WHY[(result.challenger_move, result.opponent_move)]
    return morra.WHY[(result.opponent_move, result.challenger_move)]


def render(game: MorraGame, result: RoundResult | None, rng: random.Random, battute: list[str]) -> str:
    c, o = esc(game.challenger_name), esc(game.opponent_name or "")
    if game.status == morra.OPEN:
        who = f"{c} sfida {esc(game.target_name)}!" if game.target_name else "A breve qualcuno accetterà la sfida."
        accept = int(morra.ACCEPT_TIMEOUT.total_seconds() // 60)
        move = int(morra.MOVE_TIMEOUT.total_seconds())
        return (
            f"{TITLE}\n{who}\n\n<i>Al meglio di 3 · la sfida scade tra {accept} minuti,"
            f" poi {move} secondi per ogni mossa.</i>"
        )
    if game.status == morra.CANCELLED:
        return f"{TITLE}\nSfida annullata da {c}."
    if game.status == morra.EXPIRED:
        return f"{TITLE}\n⌛ {esc(morra.expired_notice(game))}."

    lines = [f"{TITLE}\n<b>{c} {game.challenger_score} – {game.opponent_score} {o}</b>"]
    lines += [_round_line(i, rc, ro, game) for i, (rc, ro) in enumerate(game.rounds, start=1)]
    if result is not None and result.winner == 0:
        lines.append(f"Pari: {_emoji(result.challenger_move)} contro {_emoji(result.opponent_move)}, si ripete!")
    elif result is not None:
        lines.append(f"<i>{esc(_why(result)).capitalize()}.</i>")

    if game.status == morra.FINISHED:
        (_, winner), (_, loser) = game.winner, game.loser
        lines.append(f"\n🏆 <b>Vince {esc(winner)}!</b>")
        lines.append(esc(rng.choice(battute)).format(vincitore=esc(winner), perdente=esc(loser)))
        return "\n".join(lines)

    def mark(chosen: bool) -> str:
        return "✅" if chosen else "⏳"

    seconds = int(morra.MOVE_TIMEOUT.total_seconds())
    lines.append(f"\nRound {len(game.rounds) + 1}: scegliete la vostra mossa entro {seconds} secondi (resta segreta).")
    lines.append(f"{c}: {mark(game.challenger_choice is not None)} · {o}: {mark(game.opponent_choice is not None)}")
    return "\n".join(lines)


def keyboard(game: MorraGame) -> InlineKeyboardMarkup | None:
    if game.status == morra.OPEN:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("ACCETTO", callback_data=MORRA_ACTION.data(game.id, ACCEPT)),
                    InlineKeyboardButton("ANNULLA", callback_data=MORRA_ACTION.data(game.id, CANCEL)),
                ]
            ]
        )
    if game.status == morra.PLAYING:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(f"{emoji} {name}", callback_data=MORRA_ACTION.data(game.id, move))
                    for move, (emoji, name) in MOVES.items()
                ]
            ]
        )
    return None


def _is_private(message: Message) -> bool:
    return message.chat.type == ChatType.PRIVATE


async def morra_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dal menu: sfida aperta, il primo che accetta gioca."""
    d = deps(context)
    if _is_private(query.message):
        await query.edit_message_text(PRIVATE_TEXT)
        return
    user = query.from_user
    game = await d.storage.create_morra(query.message.chat.id, user.id, display_name(user), None, None, d.now())
    battute = d.content.texts["morra_battute"]
    await query.edit_message_text(render(game, None, d.rng, battute), parse_mode=HTML, reply_markup=keyboard(game))
    await _track(d, game, query.message.message_id)


async def _track(d: Deps, game: MorraGame, message_id: int) -> None:
    """Salva il messaggio da cancellare alla scadenza e sveglia il timer."""
    await d.storage.set_morra_message(game.id, message_id)
    if d.game_timer is not None:
        d.game_timer.schedule(game.deadline)


async def remove_expired(bot: Bot, game: MorraGame, battute: list[str]) -> None:
    """Cancella il messaggio di una partita scaduta; se non si può, lo trasforma in "⌛ …".

    Telegram consente ai bot di cancellare i propri messaggi nei gruppi entro 48 ore
    (https://core.telegram.org/bots/api#deletemessage): qui si parla di minuti, ma il
    messaggio potrebbe essere già stato cancellato a mano.
    """
    if game.message_id is None:
        return
    try:
        await bot.delete_message(game.chat_id, game.message_id)
        return
    except TelegramError as exc:
        logger.info("Messaggio della morra %d non cancellato: %s", game.id, exc)
    try:
        await bot.edit_message_text(
            render(game, None, random.Random(), battute), game.chat_id, game.message_id, parse_mode=HTML
        )
    except TelegramError:
        logger.info("Messaggio della morra %d non modificabile", game.id)


async def _remove_safely(bot: Bot, game: MorraGame, battute: list[str]) -> bool:
    try:
        await remove_expired(bot, game, battute)
        return True
    except Exception:  # la partita è già annullata nel DB: resta solo il messaggio
        logger.exception("Messaggio della morra %d non rimosso", game.id)
        return False


async def expire_due_games(bot: Bot, d: Deps, now: datetime) -> datetime | None:
    """Annulla le partite scadute, ne cancella i messaggi (in parallelo); restituisce la scadenza successiva."""
    battute = d.content.texts["morra_battute"]
    expired = await d.storage.expire_morra(now)  # un solo UPDATE atomico per tutte
    await asyncio.gather(*(_remove_safely(bot, g, battute) for g in expired))
    return retry_floor(await d.storage.next_morra_deadline(), now)


async def _edit(query: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None) -> None:
    try:
        await query.edit_message_text(text, parse_mode=HTML, reply_markup=markup)
    except BadRequest as exc:  # stesso contenuto: non è un errore
        if "not modified" not in str(exc).lower():
            raise


async def on_morra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    d = deps(context)
    _, game_id_raw, action = query.data.split(":")
    game_id = int(game_id_raw)
    user = query.from_user
    now = d.now()
    battute = d.content.texts["morra_battute"]

    game = await d.storage.get_morra(game_id)
    if game is None:
        await query.answer("Partita non trovata")
        return
    if game.is_expired(now):  # il timer non è ancora passato: si annulla qui
        await query.answer(morra.expired_notice(game))
        try:
            expired, _ = await d.storage.apply_morra(game_id, lambda g: (morra.expire(g, now), None))
        except MorraError:  # nel frattempo il timer l'ha già annullata
            return
        await remove_expired(query.get_bot(), replace(expired, message_id=query.message.message_id), battute)
        return

    try:
        if action == ACCEPT:
            new, result = await d.storage.apply_morra(
                game_id, lambda g: (morra.accept(g, user.id, display_name(user), now), None)
            )
            notice = "Sfida accettata: scegli la tua mossa!"
        elif action == CANCEL:
            new, result = await d.storage.apply_morra(game_id, lambda g: (morra.cancel(g, user.id, now), None))
            notice = "Sfida annullata"
        else:
            new, result = await d.storage.apply_morra(game_id, lambda g: morra.choose(g, user.id, action, now))
            emoji, name = MOVES[action]
            notice = f"Hai scelto {emoji} {name} (gli altri non lo vedono)"
    except MorraError as exc:
        await query.answer(str(exc))
        return

    await query.answer(notice)
    await _edit(query, render(new, result, d.rng, battute), keyboard(new))
    if d.game_timer is not None:
        d.game_timer.schedule(new.deadline)


MORRA_ACTION = Callback("morra", r"\d+:[axrps]", on_morra)
