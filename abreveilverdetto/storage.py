"""Persistenza: Postgres in produzione, memoria per sviluppo locale e test.

Tutto lo stato del bot vive qui (nessun pickle, nessuno stato nel processo), così
l'istanza può essere spenta e riaccesa in qualsiasi momento senza perdere nulla.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from importlib import resources
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import duel
from .duel import DuelError, DuelGame
from .morra import ACCEPT_TIMEOUT, EXPIRED, FINISHED, OPEN, MorraError, MorraGame, RoundResult

logger = logging.getLogger(__name__)

MorraAction = Callable[[MorraGame], tuple[MorraGame, RoundResult | None]]
DuelAction = Callable[[DuelGame], tuple[DuelGame, duel.Round | None]]


@dataclass(frozen=True)
class Game:
    id: int
    chat_id: int
    user_id: int
    value: int
    finished: bool


@dataclass(frozen=True)
class DailyBest:
    user_id: int
    user_name: str
    value: int
    runs: int


@dataclass(frozen=True)
class WinSummary:
    wins: int
    top_user_id: int
    top_user_name: str
    top_wins: int


def is_better(value: int, runs: int, current: DailyBest | None) -> bool:
    """Valore più alto vince; a parità di valore vince chi ha usato meno giri.

    A parità assoluta resta il primo che ha ottenuto il punteggio.
    Valori oltre 100 non sono mai un record.
    """
    if value > 100:
        return False
    if current is None:
        return True
    return value > current.value or (value == current.value and runs < current.runs)


class Storage(Protocol):
    async def setup(self) -> None: ...
    async def close(self) -> None: ...

    async def try_acquire_cooldown(self, user_id: int, now: datetime, cooldown: timedelta) -> bool: ...
    async def create_game(self, chat_id: int, user_id: int, value: int, now: datetime) -> int: ...
    async def get_game(self, game_id: int) -> Game | None: ...
    async def finish_game(self, game_id: int, user_id: int, now: datetime) -> int | None: ...
    async def submit_daily(
        self, chat_id: int, day: date, user_id: int, user_name: str, value: int, runs: int
    ) -> tuple[bool, DailyBest | None]: ...
    async def record_win(self, chat_id: int, user_id: int, user_name: str, now: datetime) -> WinSummary: ...
    async def leaderboard(self, chat_id: int, limit: int = 20) -> list[tuple[str, int]]: ...
    async def purge_games(self, older_than: datetime) -> int: ...

    async def get_file_id(self, key: str) -> str | None: ...
    async def set_file_id(self, key: str, file_id: str) -> None: ...
    async def delete_file_id(self, key: str) -> None: ...

    async def create_morra(
        self,
        chat_id: int,
        challenger_id: int,
        challenger_name: str,
        target_id: int | None,
        target_name: str | None,
        now: datetime,
    ) -> MorraGame: ...
    async def get_morra(self, game_id: int) -> MorraGame | None: ...
    async def apply_morra(self, game_id: int, action: MorraAction) -> tuple[MorraGame, RoundResult | None]: ...
    async def morra_leaderboard(self, chat_id: int, limit: int = 20) -> list[tuple[str, int, int]]: ...
    async def set_morra_message(self, game_id: int, message_id: int) -> None: ...
    async def expire_morra(self, now: datetime) -> list[MorraGame]: ...
    async def next_morra_deadline(self) -> datetime | None: ...

    async def create_duel(
        self,
        chat_id: int,
        challenger_id: int,
        challenger_name: str,
        target_id: int | None,
        target_name: str | None,
        now: datetime,
    ) -> DuelGame: ...
    async def get_duel(self, game_id: int) -> DuelGame | None: ...
    async def apply_duel(self, game_id: int, action: DuelAction) -> tuple[DuelGame, duel.Round | None]: ...
    async def set_duel_message(self, game_id: int, message_id: int) -> None: ...
    async def due_duels(self, now: datetime) -> list[DuelGame]: ...
    async def next_duel_deadline(self) -> datetime | None: ...
    async def duel_leaderboard(self, chat_id: int, limit: int = 20) -> list[tuple[str, int, int]]: ...


# --------------------------------------------------------------------------------------
# Implementazione in memoria
# --------------------------------------------------------------------------------------


class MemoryStorage:
    """Stessa semantica della versione Postgres; i dati si perdono al riavvio."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._cooldown: dict[int, datetime] = {}
        self._games: dict[int, Game] = {}
        self._game_created: dict[int, datetime] = {}
        self._next_game = 1
        self._daily: dict[tuple[int, date], DailyBest] = {}
        self._wins: dict[tuple[int, int], tuple[str, int, datetime]] = {}
        self._file_ids: dict[str, str] = {}
        self._morra: dict[int, MorraGame] = {}
        self._morra_created: dict[int, datetime] = {}
        self._next_morra = 1
        self._morra_stats: dict[tuple[int, int], tuple[str, int, int]] = {}
        self._duels: dict[int, DuelGame] = {}
        self._duel_created: dict[int, datetime] = {}
        self._next_duel = 1
        self._duel_stats: dict[tuple[int, int], tuple[str, int, int]] = {}

    async def setup(self) -> None:
        logger.warning("DATABASE_URL non impostato: uso storage in memoria (dati persi al riavvio)")

    async def close(self) -> None:
        return None

    async def try_acquire_cooldown(self, user_id: int, now: datetime, cooldown: timedelta) -> bool:
        async with self._lock:
            last = self._cooldown.get(user_id)
            if last is not None and last > now - cooldown:
                return False
            self._cooldown[user_id] = now
            return True

    async def create_game(self, chat_id: int, user_id: int, value: int, now: datetime) -> int:
        async with self._lock:
            game_id = self._next_game
            self._next_game += 1
            self._games[game_id] = Game(game_id, chat_id, user_id, value, finished=False)
            self._game_created[game_id] = now
            return game_id

    async def get_game(self, game_id: int) -> Game | None:
        return self._games.get(game_id)

    async def finish_game(self, game_id: int, user_id: int, now: datetime) -> int | None:
        async with self._lock:
            game = self._games.get(game_id)
            if game is None or game.finished or game.user_id != user_id:
                return None
            self._games[game_id] = replace(game, finished=True)
            return game.value

    async def submit_daily(
        self, chat_id: int, day: date, user_id: int, user_name: str, value: int, runs: int
    ) -> tuple[bool, DailyBest | None]:
        async with self._lock:
            current = self._daily.get((chat_id, day))
            if is_better(value, runs, current):
                best = DailyBest(user_id, user_name, value, runs)
                self._daily[(chat_id, day)] = best
                return True, best
            return False, current

    async def record_win(self, chat_id: int, user_id: int, user_name: str, now: datetime) -> WinSummary:
        async with self._lock:
            _, wins, _ = self._wins.get((chat_id, user_id), (user_name, 0, now))
            self._wins[(chat_id, user_id)] = (user_name, wins + 1, now)
            rows = [(uid, name, w, last) for (cid, uid), (name, w, last) in self._wins.items() if cid == chat_id]
            rows.sort(key=lambda r: (-r[2], r[3]))
            top_uid, top_name, top_wins, _ = rows[0]
            return WinSummary(wins + 1, top_uid, top_name, top_wins)

    async def leaderboard(self, chat_id: int, limit: int = 20) -> list[tuple[str, int]]:
        rows = [(name, w, last) for (cid, _), (name, w, last) in self._wins.items() if cid == chat_id]
        rows.sort(key=lambda r: (-r[1], r[2]))
        return [(name, w) for name, w, _ in rows[:limit]]

    async def purge_games(self, older_than: datetime) -> int:
        async with self._lock:
            old = [gid for gid, created in self._game_created.items() if created < older_than]
            for gid in old:
                self._games.pop(gid, None)
                self._game_created.pop(gid, None)
            old_morra = [gid for gid, created in self._morra_created.items() if created < older_than]
            for gid in old_morra:
                self._morra.pop(gid, None)
                self._morra_created.pop(gid, None)
            old_duels = [gid for gid, created in self._duel_created.items() if created < older_than]
            for gid in old_duels:
                self._duels.pop(gid, None)
                self._duel_created.pop(gid, None)
            return len(old) + len(old_morra) + len(old_duels)

    async def create_morra(
        self,
        chat_id: int,
        challenger_id: int,
        challenger_name: str,
        target_id: int | None,
        target_name: str | None,
        now: datetime,
    ) -> MorraGame:
        async with self._lock:
            game = MorraGame(
                id=self._next_morra,
                chat_id=chat_id,
                challenger_id=challenger_id,
                challenger_name=challenger_name,
                status=OPEN,
                updated_at=now,
                target_id=target_id,
                target_name=target_name,
                deadline=now + ACCEPT_TIMEOUT,
            )
            self._next_morra += 1
            self._morra[game.id] = game
            self._morra_created[game.id] = now
            return game

    async def get_morra(self, game_id: int) -> MorraGame | None:
        return self._morra.get(game_id)

    async def apply_morra(self, game_id: int, action: MorraAction) -> tuple[MorraGame, RoundResult | None]:
        async with self._lock:
            game = self._morra.get(game_id)
            if game is None:
                raise MorraError("Partita non trovata")
            new, result = action(game)
            self._morra[game_id] = new
            if game.status != FINISHED and new.status == FINISHED:
                self._record_morra(new)
            return new, result

    def _record_morra(self, game: MorraGame) -> None:
        (wid, wname), (lid, lname) = game.winner, game.loser
        _, w, l_ = self._morra_stats.get((game.chat_id, wid), (wname, 0, 0))
        self._morra_stats[(game.chat_id, wid)] = (wname, w + 1, l_)
        _, w, l_ = self._morra_stats.get((game.chat_id, lid), (lname, 0, 0))
        self._morra_stats[(game.chat_id, lid)] = (lname, w, l_ + 1)

    async def morra_leaderboard(self, chat_id: int, limit: int = 20) -> list[tuple[str, int, int]]:
        rows = [v for (cid, _), v in self._morra_stats.items() if cid == chat_id]
        rows.sort(key=lambda r: (-r[1], r[2], r[0]))
        return rows[:limit]

    async def set_morra_message(self, game_id: int, message_id: int) -> None:
        async with self._lock:
            if game_id in self._morra:
                self._morra[game_id] = replace(self._morra[game_id], message_id=message_id)

    async def expire_morra(self, now: datetime) -> list[MorraGame]:
        async with self._lock:
            expired = []
            for gid, game in self._morra.items():
                if game.is_active and game.deadline is not None and game.deadline <= now:
                    self._morra[gid] = replace(game, status=EXPIRED, updated_at=now, deadline=None)
                    expired.append(self._morra[gid])
            return expired

    async def next_morra_deadline(self) -> datetime | None:
        deadlines = [g.deadline for g in self._morra.values() if g.is_active and g.deadline is not None]
        return min(deadlines, default=None)

    async def create_duel(
        self,
        chat_id: int,
        challenger_id: int,
        challenger_name: str,
        target_id: int | None,
        target_name: str | None,
        now: datetime,
    ) -> DuelGame:
        async with self._lock:
            game = DuelGame(
                id=self._next_duel,
                chat_id=chat_id,
                challenger_id=challenger_id,
                challenger_name=challenger_name,
                status=duel.OPEN,
                updated_at=now,
                target_id=target_id,
                target_name=target_name,
                deadline=now + duel.ACCEPT_TIMEOUT,
            )
            self._next_duel += 1
            self._duels[game.id] = game
            self._duel_created[game.id] = now
            return game

    async def get_duel(self, game_id: int) -> DuelGame | None:
        return self._duels.get(game_id)

    async def apply_duel(self, game_id: int, action: DuelAction) -> tuple[DuelGame, duel.Round | None]:
        async with self._lock:
            game = self._duels.get(game_id)
            if game is None:
                raise DuelError("Duello non trovato")
            new, result = action(game)
            self._duels[game_id] = new
            if game.status != duel.FINISHED and new.status == duel.FINISHED:
                (wid, wname), (lid, lname) = new.winner, new.loser
                _, w, l_ = self._duel_stats.get((new.chat_id, wid), (wname, 0, 0))
                self._duel_stats[(new.chat_id, wid)] = (wname, w + 1, l_)
                _, w, l_ = self._duel_stats.get((new.chat_id, lid), (lname, 0, 0))
                self._duel_stats[(new.chat_id, lid)] = (lname, w, l_ + 1)
            return new, result

    async def set_duel_message(self, game_id: int, message_id: int) -> None:
        async with self._lock:
            if game_id in self._duels:
                self._duels[game_id] = replace(self._duels[game_id], message_id=message_id)

    async def due_duels(self, now: datetime) -> list[DuelGame]:
        return [g for g in self._duels.values() if g.is_due(now)]

    async def next_duel_deadline(self) -> datetime | None:
        deadlines = [g.deadline for g in self._duels.values() if g.is_active and g.deadline is not None]
        return min(deadlines, default=None)

    async def duel_leaderboard(self, chat_id: int, limit: int = 20) -> list[tuple[str, int, int]]:
        rows = [v for (cid, _), v in self._duel_stats.items() if cid == chat_id]
        rows.sort(key=lambda r: (-r[1], r[2], r[0]))
        return rows[:limit]

    async def get_file_id(self, key: str) -> str | None:
        return self._file_ids.get(key)

    async def set_file_id(self, key: str, file_id: str) -> None:
        self._file_ids[key] = file_id

    async def delete_file_id(self, key: str) -> None:
        self._file_ids.pop(key, None)


# --------------------------------------------------------------------------------------
# Implementazione Postgres (asyncpg)
# --------------------------------------------------------------------------------------


def normalize_dsn(dsn: str) -> str:
    """Adatta la connection string copiata da Neon/Supabase ad asyncpg.

    asyncpg non conosce ``channel_binding`` (Neon lo aggiunge di default) e lo
    inoltrerebbe al server come parametro di sessione, che lo rifiuta.
    """
    parts = urlsplit(dsn)
    if parts.scheme == "postgres":
        parts = parts._replace(scheme="postgresql")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "channel_binding"]
    return urlunsplit(parts._replace(query=urlencode(query)))


class PostgresStorage:
    def __init__(self, dsn: str) -> None:
        self._dsn = normalize_dsn(dsn)
        self._pool = None

    async def setup(self) -> None:
        import asyncpg

        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=0,
            max_size=5,
            # Neon sospende il database quando è inattivo: chiudiamo per primi le
            # connessioni ferme invece di ritrovarcele chiuse dal server.
            max_inactive_connection_lifetime=60,
            # Compatibile anche con l'endpoint "pooled" (PgBouncer in transaction mode).
            statement_cache_size=0,
            command_timeout=15,
        )
        schema = resources.files(__package__).joinpath("schema.sql").read_text(encoding="utf-8")
        async with self._pool.acquire() as conn:
            await conn.execute(schema)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    @property
    def pool(self):
        if self._pool is None:
            raise RuntimeError("PostgresStorage.setup() non è stato chiamato")
        return self._pool

    async def try_acquire_cooldown(self, user_id: int, now: datetime, cooldown: timedelta) -> bool:
        # Upsert condizionale: atomico anche con due click contemporanei.
        row = await self.pool.fetchrow(
            """
            INSERT INTO c100_cooldown (user_id, last_run) VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET last_run = EXCLUDED.last_run
            WHERE c100_cooldown.last_run <= $3
            RETURNING user_id
            """,
            user_id,
            now,
            now - cooldown,
        )
        return row is not None

    async def create_game(self, chat_id: int, user_id: int, value: int, now: datetime) -> int:
        return await self.pool.fetchval(
            "INSERT INTO c100_games (chat_id, user_id, value, created_at) VALUES ($1, $2, $3, $4) RETURNING id",
            chat_id,
            user_id,
            value,
            now,
        )

    async def get_game(self, game_id: int) -> Game | None:
        row = await self.pool.fetchrow(
            "SELECT id, chat_id, user_id, value, finished_at IS NOT NULL AS finished FROM c100_games WHERE id = $1",
            game_id,
        )
        return Game(**dict(row)) if row else None

    async def finish_game(self, game_id: int, user_id: int, now: datetime) -> int | None:
        # Il secondo click sullo stesso bottone non trova più finished_at IS NULL.
        return await self.pool.fetchval(
            """
            UPDATE c100_games SET finished_at = $3
            WHERE id = $1 AND user_id = $2 AND finished_at IS NULL
            RETURNING value
            """,
            game_id,
            user_id,
            now,
        )

    async def submit_daily(
        self, chat_id: int, day: date, user_id: int, user_name: str, value: int, runs: int
    ) -> tuple[bool, DailyBest | None]:
        async with self.pool.acquire() as conn:
            if value <= 100:
                row = await conn.fetchrow(
                    """
                    INSERT INTO c100_daily_best AS d (chat_id, day, user_id, user_name, value, runs)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (chat_id, day) DO UPDATE
                        SET user_id = EXCLUDED.user_id, user_name = EXCLUDED.user_name,
                            value = EXCLUDED.value, runs = EXCLUDED.runs
                        WHERE EXCLUDED.value > d.value
                           OR (EXCLUDED.value = d.value AND EXCLUDED.runs < d.runs)
                    RETURNING user_id, user_name, value, runs
                    """,
                    chat_id,
                    day,
                    user_id,
                    user_name,
                    value,
                    runs,
                )
                if row is not None:
                    return True, DailyBest(**dict(row))
            row = await conn.fetchrow(
                "SELECT user_id, user_name, value, runs FROM c100_daily_best WHERE chat_id = $1 AND day = $2",
                chat_id,
                day,
            )
            return False, DailyBest(**dict(row)) if row else None

    async def record_win(self, chat_id: int, user_id: int, user_name: str, now: datetime) -> WinSummary:
        async with self.pool.acquire() as conn, conn.transaction():
            wins = await conn.fetchval(
                """
                INSERT INTO c100_wins AS w (chat_id, user_id, user_name, wins, last_win)
                VALUES ($1, $2, $3, 1, $4)
                ON CONFLICT (chat_id, user_id) DO UPDATE
                    SET wins = w.wins + 1, user_name = EXCLUDED.user_name, last_win = EXCLUDED.last_win
                RETURNING wins
                """,
                chat_id,
                user_id,
                user_name,
                now,
            )
            top = await conn.fetchrow(
                """
                SELECT user_id, user_name, wins FROM c100_wins
                WHERE chat_id = $1 ORDER BY wins DESC, last_win LIMIT 1
                """,
                chat_id,
            )
            return WinSummary(wins, top["user_id"], top["user_name"], top["wins"])

    async def leaderboard(self, chat_id: int, limit: int = 20) -> list[tuple[str, int]]:
        rows = await self.pool.fetch(
            "SELECT user_name, wins FROM c100_wins WHERE chat_id = $1 ORDER BY wins DESC, last_win LIMIT $2",
            chat_id,
            limit,
        )
        return [(r["user_name"], r["wins"]) for r in rows]

    async def purge_games(self, older_than: datetime) -> int:
        status = await self.pool.execute("DELETE FROM c100_games WHERE created_at < $1", older_than)
        morra = await self.pool.execute("DELETE FROM morra_games WHERE created_at < $1", older_than)
        duels = await self.pool.execute("DELETE FROM duel_games WHERE created_at < $1", older_than)
        return sum(int(r.split()[-1]) for r in (status, morra, duels))

    async def create_morra(
        self,
        chat_id: int,
        challenger_id: int,
        challenger_name: str,
        target_id: int | None,
        target_name: str | None,
        now: datetime,
    ) -> MorraGame:
        row = await self.pool.fetchrow(
            """
            INSERT INTO morra_games
                (chat_id, challenger_id, challenger_name, target_id, target_name, status,
                 created_at, updated_at, deadline)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $7, $8)
            RETURNING *
            """,
            chat_id,
            challenger_id,
            challenger_name,
            target_id,
            target_name,
            OPEN,
            now,
            now + ACCEPT_TIMEOUT,
        )
        return _morra_from_row(row)

    async def get_morra(self, game_id: int) -> MorraGame | None:
        row = await self.pool.fetchrow("SELECT * FROM morra_games WHERE id = $1", game_id)
        return _morra_from_row(row) if row else None

    async def apply_morra(self, game_id: int, action: MorraAction) -> tuple[MorraGame, RoundResult | None]:
        # FOR UPDATE: due click contemporanei vengono serializzati sulla stessa partita.
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow("SELECT * FROM morra_games WHERE id = $1 FOR UPDATE", game_id)
            if row is None:
                raise MorraError("Partita non trovata")
            game = _morra_from_row(row)
            new, result = action(game)  # MorraError -> rollback
            await conn.execute(
                """
                UPDATE morra_games SET
                    status = $2, opponent_id = $3, opponent_name = $4,
                    challenger_choice = $5, opponent_choice = $6,
                    challenger_score = $7, opponent_score = $8, history = $9, updated_at = $10,
                    deadline = $11
                WHERE id = $1
                """,
                game_id,
                new.status,
                new.opponent_id,
                new.opponent_name,
                new.challenger_choice,
                new.opponent_choice,
                new.challenger_score,
                new.opponent_score,
                new.history,
                new.updated_at,
                new.deadline,
            )
            if game.status != FINISHED and new.status == FINISHED:
                (wid, wname), (lid, lname) = new.winner, new.loser
                for uid, name, win, loss in ((wid, wname, 1, 0), (lid, lname, 0, 1)):
                    await conn.execute(
                        """
                        INSERT INTO morra_stats AS m (chat_id, user_id, user_name, wins, losses)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (chat_id, user_id) DO UPDATE SET
                            user_name = EXCLUDED.user_name,
                            wins = m.wins + EXCLUDED.wins,
                            losses = m.losses + EXCLUDED.losses
                        """,
                        new.chat_id,
                        uid,
                        name,
                        win,
                        loss,
                    )
            return new, result

    async def morra_leaderboard(self, chat_id: int, limit: int = 20) -> list[tuple[str, int, int]]:
        rows = await self.pool.fetch(
            """
            SELECT user_name, wins, losses FROM morra_stats
            WHERE chat_id = $1 ORDER BY wins DESC, losses, user_name LIMIT $2
            """,
            chat_id,
            limit,
        )
        return [(r["user_name"], r["wins"], r["losses"]) for r in rows]

    async def set_morra_message(self, game_id: int, message_id: int) -> None:
        await self.pool.execute("UPDATE morra_games SET message_id = $2 WHERE id = $1", game_id, message_id)

    async def expire_morra(self, now: datetime) -> list[MorraGame]:
        # Un solo UPDATE atomico: con più worker ogni partita scade (e viene cancellata) una volta.
        rows = await self.pool.fetch(
            """
            UPDATE morra_games SET status = $2, updated_at = $1, deadline = NULL
            WHERE status IN ('open', 'playing') AND deadline <= $1
            RETURNING *
            """,
            now,
            EXPIRED,
        )
        return [_morra_from_row(r) for r in rows]

    async def next_morra_deadline(self) -> datetime | None:
        return await self.pool.fetchval("SELECT min(deadline) FROM morra_games WHERE status IN ('open', 'playing')")

    async def create_duel(
        self,
        chat_id: int,
        challenger_id: int,
        challenger_name: str,
        target_id: int | None,
        target_name: str | None,
        now: datetime,
    ) -> DuelGame:
        row = await self.pool.fetchrow(
            """
            INSERT INTO duel_games
                (chat_id, challenger_id, challenger_name, target_id, target_name, status,
                 created_at, updated_at, deadline)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $7, $8)
            RETURNING *
            """,
            chat_id,
            challenger_id,
            challenger_name,
            target_id,
            target_name,
            duel.OPEN,
            now,
            now + duel.ACCEPT_TIMEOUT,
        )
        return _duel_from_row(row)

    async def get_duel(self, game_id: int) -> DuelGame | None:
        row = await self.pool.fetchrow("SELECT * FROM duel_games WHERE id = $1", game_id)
        return _duel_from_row(row) if row else None

    async def apply_duel(self, game_id: int, action: DuelAction) -> tuple[DuelGame, duel.Round | None]:
        # FOR UPDATE: i due colpi (e il "FUOCO!" del timer) vengono serializzati sulla stessa partita.
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow("SELECT * FROM duel_games WHERE id = $1 FOR UPDATE", game_id)
            if row is None:
                raise DuelError("Duello non trovato")
            game = _duel_from_row(row)
            new, result = action(game)  # DuelError -> rollback
            await conn.execute(
                """
                UPDATE duel_games SET
                    status = $2, opponent_id = $3, opponent_name = $4, round = $5,
                    challenger_score = $6, opponent_score = $7, history = $8,
                    deadline = $9, updated_at = $10
                WHERE id = $1
                """,
                game_id,
                new.status,
                new.opponent_id,
                new.opponent_name,
                new.round,
                new.challenger_score,
                new.opponent_score,
                new.history,
                new.deadline,
                new.updated_at,
            )
            if game.status != duel.FINISHED and new.status == duel.FINISHED:
                (wid, wname), (lid, lname) = new.winner, new.loser
                for uid, name, win, loss in ((wid, wname, 1, 0), (lid, lname, 0, 1)):
                    await conn.execute(
                        """
                        INSERT INTO duel_stats AS d (chat_id, user_id, user_name, wins, losses)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (chat_id, user_id) DO UPDATE SET
                            user_name = EXCLUDED.user_name,
                            wins = d.wins + EXCLUDED.wins,
                            losses = d.losses + EXCLUDED.losses
                        """,
                        new.chat_id,
                        uid,
                        name,
                        win,
                        loss,
                    )
            return new, result

    async def set_duel_message(self, game_id: int, message_id: int) -> None:
        await self.pool.execute("UPDATE duel_games SET message_id = $2 WHERE id = $1", game_id, message_id)

    async def due_duels(self, now: datetime) -> list[DuelGame]:
        rows = await self.pool.fetch(
            "SELECT * FROM duel_games WHERE status = ANY($2::text[]) AND deadline <= $1 ORDER BY deadline",
            now,
            list(duel.ACTIVE),
        )
        return [_duel_from_row(r) for r in rows]

    async def next_duel_deadline(self) -> datetime | None:
        return await self.pool.fetchval(
            "SELECT min(deadline) FROM duel_games WHERE status = ANY($1::text[])", list(duel.ACTIVE)
        )

    async def duel_leaderboard(self, chat_id: int, limit: int = 20) -> list[tuple[str, int, int]]:
        rows = await self.pool.fetch(
            """
            SELECT user_name, wins, losses FROM duel_stats
            WHERE chat_id = $1 ORDER BY wins DESC, losses, user_name LIMIT $2
            """,
            chat_id,
            limit,
        )
        return [(r["user_name"], r["wins"], r["losses"]) for r in rows]

    async def get_file_id(self, key: str) -> str | None:
        return await self.pool.fetchval("SELECT file_id FROM media_file_ids WHERE media_key = $1", key)

    async def set_file_id(self, key: str, file_id: str) -> None:
        await self.pool.execute(
            """
            INSERT INTO media_file_ids (media_key, file_id) VALUES ($1, $2)
            ON CONFLICT (media_key) DO UPDATE SET file_id = EXCLUDED.file_id
            """,
            key,
            file_id,
        )

    async def delete_file_id(self, key: str) -> None:
        await self.pool.execute("DELETE FROM media_file_ids WHERE media_key = $1", key)


def _morra_from_row(row: Any) -> MorraGame:
    data = dict(row)
    data.pop("created_at", None)
    return MorraGame(**data)


def _duel_from_row(row: Any) -> DuelGame:
    data = dict(row)
    data.pop("created_at", None)
    return DuelGame(**data)


def create_storage(database_url: str | None) -> Storage:
    return PostgresStorage(database_url) if database_url else MemoryStorage()
