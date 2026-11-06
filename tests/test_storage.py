import asyncio
from datetime import UTC, date, datetime, timedelta

from abreveilverdetto.storage import DailyBest, is_better, normalize_dsn

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
DAY = date(2026, 11, 6)
CHAT = -100123


def test_is_better():
    best = DailyBest(1, "a", 90, 2)
    assert is_better(50, 1, None)
    assert not is_better(105, 1, None)
    assert is_better(95, 2, best)
    assert is_better(90, 1, best)
    assert not is_better(90, 2, best)  # parità assoluta: resta il primo
    assert not is_better(85, 1, best)


def test_normalize_dsn_per_neon():
    dsn = "postgres://u:p@ep-x.eu-central-1.aws.neon.tech/db?sslmode=require&channel_binding=require"
    assert normalize_dsn(dsn) == "postgresql://u:p@ep-x.eu-central-1.aws.neon.tech/db?sslmode=require"


async def test_cooldown(storage):
    cd = timedelta(minutes=1)
    assert await storage.try_acquire_cooldown(1, NOW, cd)
    assert not await storage.try_acquire_cooldown(1, NOW + timedelta(seconds=30), cd)
    assert await storage.try_acquire_cooldown(2, NOW, cd)
    assert await storage.try_acquire_cooldown(1, NOW + timedelta(seconds=61), cd)


async def test_cooldown_click_contemporanei(storage):
    results = await asyncio.gather(*(storage.try_acquire_cooldown(7, NOW, timedelta(minutes=1)) for _ in range(5)))
    assert sum(results) == 1


async def test_partita_si_chiude_una_volta_sola_e_solo_dal_proprietario(storage):
    gid = await storage.create_game(CHAT, 1, 60, NOW)
    game = await storage.get_game(gid)
    assert (game.user_id, game.value, game.finished) == (1, 60, False)

    assert await storage.finish_game(gid, 2, NOW) is None  # non è sua
    results = await asyncio.gather(*(storage.finish_game(gid, 1, NOW) for _ in range(3)))
    assert results.count(60) == 1
    assert results.count(None) == 2
    assert (await storage.get_game(gid)).finished
    assert await storage.get_game(999_999) is None


async def test_record_giornaliero(storage):
    assert await storage.submit_daily(CHAT, DAY, 1, "Ada", 105, 2) == (False, None)
    assert await storage.submit_daily(CHAT, DAY, 1, "Ada", 80, 2) == (True, DailyBest(1, "Ada", 80, 2))
    assert await storage.submit_daily(CHAT, DAY, 2, "Bob", 70, 1) == (False, DailyBest(1, "Ada", 80, 2))
    assert await storage.submit_daily(CHAT, DAY, 2, "Bob", 80, 1) == (True, DailyBest(2, "Bob", 80, 1))
    assert await storage.submit_daily(CHAT, DAY, 1, "Ada", 80, 1) == (False, DailyBest(2, "Bob", 80, 1))
    assert await storage.submit_daily(CHAT, DAY, 1, "Ada", 110, 2) == (False, DailyBest(2, "Bob", 80, 1))
    # chat e giorni diversi sono indipendenti
    assert (await storage.submit_daily(CHAT + 1, DAY, 3, "Cy", 10, 1))[0]
    assert (await storage.submit_daily(CHAT, DAY + timedelta(days=1), 3, "Cy", 10, 1))[0]


async def test_vittorie_e_classifica(storage):
    s1 = await storage.record_win(CHAT, 1, "Ada", NOW)
    assert (s1.wins, s1.top_user_id, s1.top_wins) == (1, 1, 1)
    s2 = await storage.record_win(CHAT, 2, "Bob", NOW + timedelta(minutes=1))
    assert (s2.wins, s2.top_user_name) == (1, "Ada")  # a parità vince chi ha vinto prima
    s3 = await storage.record_win(CHAT, 2, "Bob B.", NOW + timedelta(minutes=2))
    assert (s3.wins, s3.top_user_id, s3.top_user_name, s3.top_wins) == (2, 2, "Bob B.", 2)
    await storage.record_win(CHAT + 1, 3, "Cy", NOW)
    assert await storage.leaderboard(CHAT) == [("Bob B.", 2), ("Ada", 1)]
    assert await storage.leaderboard(CHAT + 1) == [("Cy", 1)]
    assert await storage.leaderboard(42) == []


async def test_file_id(storage):
    assert await storage.get_file_id("k") is None
    await storage.set_file_id("k", "A")
    await storage.set_file_id("k", "B")
    assert await storage.get_file_id("k") == "B"
    await storage.delete_file_id("k")
    assert await storage.get_file_id("k") is None


async def test_purge(storage):
    old = await storage.create_game(CHAT, 1, 10, NOW - timedelta(days=10))
    new = await storage.create_game(CHAT, 1, 10, NOW)
    assert await storage.purge_games(NOW - timedelta(days=7)) == 1
    assert await storage.get_game(old) is None
    assert await storage.get_game(new) is not None


async def test_setup_idempotente(storage):
    await storage.setup()
