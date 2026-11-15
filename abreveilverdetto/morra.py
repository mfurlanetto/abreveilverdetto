"""Morra cinese tra due persone: regole pure, senza Telegram né database.

Una partita va "al meglio di 3": vince chi arriva per primo a 2 round vinti.
Un round pari si ripete e non conta, quindi la partita non finisce mai in parità.
Le transizioni di stato sono funzioni pure: lo storage le applica dentro un lock
(memoria) o una transazione con SELECT ... FOR UPDATE (Postgres).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

WINS_NEEDED = 2
TIMEOUT = timedelta(minutes=10)

ROCK, PAPER, SCISSORS = "r", "p", "s"
MOVES = {ROCK: ("✊", "SASSO"), PAPER: ("✋", "CARTA"), SCISSORS: ("✌️", "FORBICE")}
BEATS = {ROCK: SCISSORS, PAPER: ROCK, SCISSORS: PAPER}
WHY = {
    (ROCK, SCISSORS): "il sasso spacca le forbici",
    (PAPER, ROCK): "la carta avvolge il sasso",
    (SCISSORS, PAPER): "le forbici tagliano la carta",
}

OPEN, PLAYING, FINISHED, CANCELLED, EXPIRED = "open", "playing", "finished", "cancelled", "expired"


class MorraError(Exception):
    """Azione non consentita; il messaggio è mostrato all'utente (notifica del bottone)."""


@dataclass(frozen=True)
class MorraGame:
    id: int
    chat_id: int
    challenger_id: int
    challenger_name: str
    status: str
    updated_at: datetime
    target_id: int | None = None
    target_name: str | None = None
    opponent_id: int | None = None
    opponent_name: str | None = None
    challenger_choice: str | None = None
    opponent_choice: str | None = None
    challenger_score: int = 0
    opponent_score: int = 0
    history: str = ""  # round giocati (pari esclusi): "rs,pr" = sfidante,avversario

    @property
    def rounds(self) -> list[tuple[str, str]]:
        return [(r[0], r[1]) for r in self.history.split(",") if len(r) == 2]

    @property
    def winner(self) -> tuple[int, str] | None:
        if self.status != FINISHED or self.opponent_id is None:
            return None
        if self.challenger_score > self.opponent_score:
            return self.challenger_id, self.challenger_name
        return self.opponent_id, self.opponent_name or ""

    @property
    def loser(self) -> tuple[int, str] | None:
        if self.status != FINISHED or self.opponent_id is None:
            return None
        if self.challenger_score > self.opponent_score:
            return self.opponent_id, self.opponent_name or ""
        return self.challenger_id, self.challenger_name

    def is_expired(self, now: datetime) -> bool:
        return self.status in (OPEN, PLAYING) and now - self.updated_at >= TIMEOUT

    def has_chosen(self, user_id: int) -> bool:
        if user_id == self.challenger_id:
            return self.challenger_choice is not None
        if user_id == self.opponent_id:
            return self.opponent_choice is not None
        return False


@dataclass(frozen=True)
class RoundResult:
    challenger_move: str
    opponent_move: str
    winner: int  # 0 pari, 1 sfidante, 2 avversario


def round_winner(challenger: str, opponent: str) -> int:
    if challenger == opponent:
        return 0
    return 1 if BEATS[challenger] == opponent else 2


def _check_alive(game: MorraGame, now: datetime) -> None:
    if game.is_expired(now):
        raise MorraError("Sfida scaduta (10 minuti senza mosse)")
    if game.status == CANCELLED:
        raise MorraError("Sfida annullata")
    if game.status == FINISHED:
        raise MorraError("Partita già finita")


def accept(game: MorraGame, user_id: int, user_name: str, now: datetime) -> MorraGame:
    _check_alive(game, now)
    if game.status != OPEN:
        raise MorraError("Qualcuno ha già accettato")
    if user_id == game.challenger_id:
        raise MorraError("Non puoi sfidare te stesso")
    if game.target_id is not None and user_id != game.target_id:
        raise MorraError(f"La sfida è per {game.target_name or 'un altro'}")
    return replace(game, status=PLAYING, opponent_id=user_id, opponent_name=user_name, updated_at=now)


def cancel(game: MorraGame, user_id: int, now: datetime) -> MorraGame:
    _check_alive(game, now)
    if user_id != game.challenger_id:
        raise MorraError("Solo chi ha lanciato la sfida può annullarla")
    if game.status != OPEN:
        raise MorraError("La partita è già iniziata")
    return replace(game, status=CANCELLED, updated_at=now)


def choose(game: MorraGame, user_id: int, move: str, now: datetime) -> tuple[MorraGame, RoundResult | None]:
    """Registra una mossa; quando entrambi hanno scelto risolve il round."""
    if move not in MOVES:
        raise MorraError("Mossa sconosciuta")
    _check_alive(game, now)
    if game.status != PLAYING:
        raise MorraError("Aspetta che qualcuno accetti la sfida")
    if user_id not in (game.challenger_id, game.opponent_id):
        raise MorraError("Non stai giocando questa partita")
    if game.has_chosen(user_id):
        raise MorraError("Hai già scelto in questo round")

    if user_id == game.challenger_id:
        game = replace(game, challenger_choice=move, updated_at=now)
    else:
        game = replace(game, opponent_choice=move, updated_at=now)
    if game.challenger_choice is None or game.opponent_choice is None:
        return game, None

    c, o = game.challenger_choice, game.opponent_choice
    result = RoundResult(c, o, round_winner(c, o))
    game = replace(game, challenger_choice=None, opponent_choice=None)
    if result.winner == 0:
        return game, result
    history = ",".join(filter(None, [game.history, c + o]))
    cs = game.challenger_score + (result.winner == 1)
    os_ = game.opponent_score + (result.winner == 2)
    status = FINISHED if max(cs, os_) >= WINS_NEEDED else PLAYING
    return replace(game, challenger_score=cs, opponent_score=os_, history=history, status=status), result
