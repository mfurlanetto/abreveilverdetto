"""Persistenza: Postgres in produzione, memoria per sviluppo locale e test.

Tutto lo stato del bot vive qui (nessun pickle, nessuno stato nel processo), così
l'istanza può essere spenta e riaccesa in qualsiasi momento senza perdere nulla.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from importlib import resources
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

logger = logging.getLogger(__name__)


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
            return len(old)

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
        return int(status.split()[-1])

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


def create_storage(database_url: str | None) -> Storage:
    return PostgresStorage(database_url) if database_url else MemoryStorage()
