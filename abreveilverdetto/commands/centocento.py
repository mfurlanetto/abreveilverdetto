"""💯💯💯: partita a uno o due tiri, record giornaliero, vittorie e /bravitutti."""

from __future__ import annotations

from datetime import timedelta

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.ext import ContextTypes

from .. import game
from ..registry import Callback
from ..telegram_io import HTML, deps, display_name, replace_with_media
from ..text import esc, number_emoji

C100_COOLDOWN = timedelta(minutes=1)


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
                InlineKeyboardButton("NO", callback_data=C100_ANSWER.data(game_id, "n")),
                InlineKeyboardButton("YES", callback_data=C100_ANSWER.data(game_id, "y")),
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


def _short(name: str) -> str:
    return name if len(name) <= 20 else name[:19] + "…"


async def bravitutti(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Classifiche della chat: vittorie a 💯💯💯, vittorie/sconfitte a morra cinese e duello."""
    d = deps(context)
    chat_id = update.effective_chat.id
    c100 = await d.storage.leaderboard(chat_id)
    morra = await d.storage.morra_leaderboard(chat_id)
    duels = await d.storage.duel_leaderboard(chat_id)
    if not c100 and not morra and not duels:
        await update.effective_message.reply_text("Nessuna vittoria registrata in questa chat. Ancora.")
        return

    sections = []
    if c100:
        names = [_short(name) for name, _ in c100]
        width = max(len(n) for n in names) + 2
        body = "\n".join(f"{n + ':':<{width}}{wins:>4}" for n, (_, wins) in zip(names, c100, strict=True))
        sections.append(f"<b>HIGHSCORES 💯💯💯</b>\n<pre>{esc(body)}</pre>")
    if morra:
        sections.append(_wins_losses("MORRA CINESE ✊✋✌️", morra))
    if duels:
        sections.append(_wins_losses("DUELLO 🔫", duels))
    await update.effective_message.reply_text("\n\n".join(sections), parse_mode=HTML)


def _wins_losses(title: str, rows: list[tuple[str, int, int]]) -> str:
    names = [_short(name) for name, _, _ in rows]
    width = max(len(n) for n in names) + 2
    header = f"{'':<{width}}{'V':>4}{'S':>4}"
    lines = [f"{n + ':':<{width}}{w:>4}{lo:>4}" for n, (_, w, lo) in zip(names, rows, strict=True)]
    return f"<b>{title}</b> (V vinte, S perse)\n<pre>{esc(chr(10).join([header, *lines]))}</pre>"


C100_ANSWER = Callback("c100", r"\d+:[yn]", on_c100)
