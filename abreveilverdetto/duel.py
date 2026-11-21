"""Duello tra due persone: regole pure, senza Telegram né database.

Al meglio di 3: vince chi arriva per primo a 2 round vinti. In ogni round il bot
scrive "pronti…" e, dopo un ritardo casuale (FIRE_DELAY), "FUOCO!": il primo che
spara dopo il via prende il punto, chi spara prima del via lo regala all'altro.

Fasi di un round: ARMED (si aspetta il via) -> FIRE (via dato, si spara).
Il passaggio ad ARMED -> FIRE lo fa il timer (deadlines.py) quando ha già scritto
"FUOCO!" nello storage: un colpo conta come valido solo se arriva dopo.

Scadenze: la sfida va accettata entro ACCEPT_TIMEOUT; dopo il via, se nessuno
spara entro SHOOT_TIMEOUT il duello è annullato (EXPIRED, non conta in classifica).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

WINS_NEEDED = 2
ACCEPT_TIMEOUT = timedelta(minutes=5)
FIRE_DELAY = (3.0, 10.0)  # secondi, estremi del ritardo casuale del "FUOCO!"
SHOOT_TIMEOUT = timedelta(seconds=10)

OPEN, ARMED, FIRE = "open", "armed", "fire"
FINISHED, CANCELLED, EXPIRED = "finished", "cancelled", "expired"
ACTIVE = (OPEN, ARMED, FIRE)

SHOT, FALSE_START = "s", "f"


class DuelError(Exception):
    """Azione non consentita; il messaggio è mostrato all'utente (notifica del bottone)."""


@dataclass(frozen=True)
class Round:
    winner: int  # 1 sfidante, 2 avversario
    kind: str  # SHOT: il vincitore ha sparato per primo; FALSE_START: l'altro ha sparato prima del via
    reaction_ms: int | None = None  # tempo di reazione del vincitore dopo il "FUOCO!"

    def encode(self) -> str:
        return f"{self.winner}{self.kind}{self.reaction_ms if self.reaction_ms is not None else ''}"

    @classmethod
    def decode(cls, token: str) -> Round:
        ms = token[2:]
        return cls(int(token[0]), token[1], int(ms) if ms else None)


@dataclass(frozen=True)
class DuelGame:
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
    round: int = 1
    challenger_score: int = 0
    opponent_score: int = 0
    history: str = ""  # round giocati, Round.encode() separati da virgole
    deadline: datetime | None = None  # OPEN: scadenza; ARMED: ora del via; FIRE: scadenza per sparare
    message_id: int | None = None

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE

    @property
    def rounds(self) -> list[Round]:
        return [Round.decode(t) for t in self.history.split(",") if t]

    def side(self, user_id: int) -> int | None:
        if user_id == self.challenger_id:
            return 1
        if user_id == self.opponent_id:
            return 2
        return None

    def name(self, side: int) -> str:
        return self.challenger_name if side == 1 else self.opponent_name or ""

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

    def is_due(self, now: datetime) -> bool:
        """Il timer deve intervenire: dare il via (ARMED) o annullare (OPEN, FIRE)."""
        return self.is_active and self.deadline is not None and now >= self.deadline

    def is_expired(self, now: datetime) -> bool:
        return self.status in (OPEN, FIRE) and self.is_due(now)


def expired_notice(game: DuelGame) -> str:
    if game.opponent_id is None:
        return "Sfida scaduta: nessuno ha accettato in tempo"
    return "Duello annullato: nessuno ha sparato in tempo"


def _check_alive(game: DuelGame, now: datetime) -> None:
    if game.status == EXPIRED or game.is_expired(now):
        raise DuelError(expired_notice(game))
    if game.status == CANCELLED:
        raise DuelError("Sfida annullata")
    if game.status == FINISHED:
        raise DuelError("Duello già finito")


def accept(game: DuelGame, user_id: int, user_name: str, now: datetime, delay: timedelta) -> DuelGame:
    _check_alive(game, now)
    if game.status != OPEN:
        raise DuelError("Qualcuno ha già accettato")
    if user_id == game.challenger_id:
        raise DuelError("Non puoi sfidare te stesso")
    if game.target_id is not None and user_id != game.target_id:
        raise DuelError(f"La sfida è per {game.target_name or 'un altro'}")
    return replace(
        game, status=ARMED, opponent_id=user_id, opponent_name=user_name, updated_at=now, deadline=now + delay
    )


def cancel(game: DuelGame, user_id: int, now: datetime) -> DuelGame:
    _check_alive(game, now)
    if user_id != game.challenger_id:
        raise DuelError("Solo chi ha lanciato la sfida può annullarla")
    if game.status != OPEN:
        raise DuelError("Il duello è già iniziato")
    return replace(game, status=CANCELLED, updated_at=now, deadline=None)


def fire(game: DuelGame, now: datetime) -> DuelGame:
    """Il via: da qui in poi un colpo è valido. Lo chiama il timer all'ora prevista."""
    if game.status != ARMED or not game.is_due(now):
        raise DuelError("Non è ancora il momento del via")
    return replace(game, status=FIRE, updated_at=now, deadline=now + SHOOT_TIMEOUT)


def expire(game: DuelGame, now: datetime) -> DuelGame:
    if not game.is_expired(now):
        raise DuelError("Il duello non è scaduto")
    return replace(game, status=EXPIRED, updated_at=now, deadline=None)


def tick(game: DuelGame, now: datetime) -> DuelGame:
    """Azione del timer su un duello in scadenza: via (ARMED) o annullamento (OPEN, FIRE)."""
    return fire(game, now) if game.status == ARMED else expire(game, now)


def shoot(game: DuelGame, user_id: int, round_no: int, now: datetime, next_delay: timedelta) -> tuple[DuelGame, Round]:
    """Un colpo nel round ``round_no`` (quello del bottone premuto)."""
    _check_alive(game, now)
    if game.status == OPEN:
        raise DuelError("Aspetta che qualcuno accetti la sfida")
    side = game.side(user_id)
    if side is None:
        raise DuelError("Non stai partecipando a questo duello")
    if round_no != game.round:  # bottone di un round già chiuso (l'altro è stato più veloce)
        raise DuelError("Troppo tardi: round già finito")

    if game.status == ARMED:  # prima del via, anche se il timer è in ritardo: l'avversario non l'ha visto
        result = Round(3 - side, FALSE_START)
    else:
        fired_at = game.deadline - SHOOT_TIMEOUT
        result = Round(side, SHOT, max(0, round((now - fired_at).total_seconds() * 1000)))

    cs = game.challenger_score + (result.winner == 1)
    os_ = game.opponent_score + (result.winner == 2)
    finished = max(cs, os_) >= WINS_NEEDED
    new = replace(
        game,
        challenger_score=cs,
        opponent_score=os_,
        history=",".join(filter(None, [game.history, result.encode()])),
        round=game.round + 1,
        status=FINISHED if finished else ARMED,
        deadline=None if finished else now + next_delay,
        updated_at=now,
    )
    return new, result
