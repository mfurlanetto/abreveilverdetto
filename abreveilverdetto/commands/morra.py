"""✊ MORRA: morra cinese tra due persone del gruppo, al meglio di 3.

Le mosse restano segrete: chi preme un bottone vede la propria scelta solo nella
notifica del bottone (answerCallbackQuery), il messaggio pubblico dice solo se
ha già scelto. Lo stato vive nello storage (regge riavvii e scale-to-zero).
"""

from __future__ import annotations

import logging
import random
from dataclasses import replace

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ChatType
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from .. import morra
from ..morra import MOVES, MorraError, MorraGame, RoundResult
from ..registry import Callback
from ..telegram_io import HTML, deps, display_name
from ..text import esc

logger = logging.getLogger(__name__)

TITLE = "✊✋✌️ <b>MORRA CINESE</b>"
PRIVATE_TEXT = "✊✋✌️ La morra si gioca in due: aggiungimi a un gruppo e sfida qualcuno con /morra."
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
        return f"{TITLE}\n{who}\n\n<i>Al meglio di 3 · la sfida scade dopo 10 minuti senza mosse.</i>"
    if game.status == morra.CANCELLED:
        return f"{TITLE}\nSfida annullata da {c}."
    if game.status == morra.EXPIRED:
        return f"{TITLE}\n⌛ Sfida scaduta."

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

    lines.append(f"\nRound {len(game.rounds) + 1}: scegliete la vostra mossa (resta segreta).")
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


async def morra_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/morra: sfida aperta, oppure diretta se è una risposta al messaggio di qualcuno."""
    d = deps(context)
    message = update.effective_message
    if _is_private(message):
        await message.reply_text(PRIVATE_TEXT)
        return
    user = update.effective_user
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if target is not None and (target.is_bot or target.id == user.id):
        target = None
    game = await d.storage.create_morra(
        message.chat.id,
        user.id,
        display_name(user),
        target.id if target else None,
        display_name(target) if target else None,
        d.now(),
    )
    battute = d.content.texts["morra_battute"]
    await message.reply_text(render(game, None, d.rng, battute), parse_mode=HTML, reply_markup=keyboard(game))


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
    if game.is_expired(now):
        await query.answer("Sfida scaduta (10 minuti senza mosse)")
        expired = replace(game, status=morra.EXPIRED)
        await _edit(query, render(expired, None, d.rng, battute), None)
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


MORRA_ACTION = Callback("morra", r"\d+:[axrps]", on_morra)
