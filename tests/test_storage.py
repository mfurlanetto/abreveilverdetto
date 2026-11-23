import asyncio
from datetime import UTC, date, datetime, timedelta

import pytest

from abreveilverdetto import morra as morra_rules
from abreveilverdetto.morra import MorraError
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


# --- Morra cinese ------------------------------------------------------------------


async def test_morra_ciclo_completo_e_statistiche(storage):
    g = await storage.create_morra(CHAT, 1, "Ada", None, None, NOW)
    assert (g.status, g.challenger_name) == (morra_rules.OPEN, "Ada")
    assert await storage.get_morra(g.id) == g

    g, _ = await storage.apply_morra(g.id, lambda x: (morra_rules.accept(x, 2, "Bob", NOW), None))
    for c, o in [("r", "s"), ("p", "p"), ("r", "s")]:
        await storage.apply_morra(g.id, lambda x, c=c: morra_rules.choose(x, 1, c, NOW))
        g, _ = await storage.apply_morra(g.id, lambda x, o=o: morra_rules.choose(x, 2, o, NOW))
    assert g.status == morra_rules.FINISHED and g.winner == (1, "Ada")
    assert (await storage.get_morra(g.id)).history == "rs,rs"
    assert await storage.morra_leaderboard(CHAT) == [("Ada", 1, 0), ("Bob", 0, 1)]
    assert await storage.morra_leaderboard(CHAT + 1) == []


async def test_morra_errore_non_modifica_lo_stato(storage):
    g = await storage.create_morra(CHAT, 1, "Ada", None, None, NOW)
    with pytest.raises(MorraError):
        await storage.apply_morra(g.id, lambda x: (morra_rules.accept(x, 1, "Ada", NOW), None))
    assert (await storage.get_morra(g.id)).status == morra_rules.OPEN
    with pytest.raises(MorraError, match="non trovata"):
        await storage.apply_morra(999_999, lambda x: (x, None))


async def test_morra_accettazioni_contemporanee(storage):
    g = await storage.create_morra(CHAT, 1, "Ada", None, None, NOW)

    async def try_accept(uid):
        try:
            await storage.apply_morra(g.id, lambda x: (morra_rules.accept(x, uid, f"U{uid}", NOW), None))
            return uid
        except MorraError:
            return None

    winners = [u for u in await asyncio.gather(*(try_accept(u) for u in range(2, 7))) if u]
    assert len(winners) == 1
    assert (await storage.get_morra(g.id)).opponent_id == winners[0]


async def test_morra_purge(storage):
    old = await storage.create_morra(CHAT, 1, "Ada", None, None, NOW - timedelta(days=10))
    new = await storage.create_morra(CHAT, 1, "Ada", None, None, NOW)
    assert await storage.purge_games(NOW - timedelta(days=7)) == 1
    assert await storage.get_morra(old.id) is None
    assert await storage.get_morra(new.id) is not None


async def test_morra_scadenze_e_messaggio(storage):
    g = await storage.create_morra(CHAT, 1, "Ada", None, None, NOW)
    assert g.deadline == NOW + morra_rules.ACCEPT_TIMEOUT
    await storage.set_morra_message(g.id, 4242)
    assert (await storage.get_morra(g.id)).message_id == 4242

    playing = await storage.create_morra(CHAT, 1, "Ada", None, None, NOW)
    await storage.apply_morra(playing.id, lambda x: (morra_rules.accept(x, 2, "Bob", NOW), None))
    assert (await storage.get_morra(playing.id)).deadline == NOW + morra_rules.MOVE_TIMEOUT
    assert await storage.next_morra_deadline() == NOW + morra_rules.MOVE_TIMEOUT

    assert await storage.expire_morra(NOW + timedelta(seconds=59)) == []
    expired = await storage.expire_morra(NOW + timedelta(seconds=60))
    assert [e.id for e in expired] == [playing.id] and expired[0].status == morra_rules.EXPIRED
    assert await storage.expire_morra(NOW + timedelta(seconds=60)) == []  # una volta sola
    assert await storage.next_morra_deadline() == NOW + morra_rules.ACCEPT_TIMEOUT

    expired = await storage.expire_morra(NOW + morra_rules.ACCEPT_TIMEOUT)
    assert [(e.id, e.message_id) for e in expired] == [(g.id, 4242)]
    assert await storage.next_morra_deadline() is None


async def test_duello_ciclo_completo_scadenze_e_statistiche(storage):
    from abreveilverdetto import duel

    delay = timedelta(seconds=5)
    g = await storage.create_duel(CHAT, 1, "Ada", None, None, NOW)
    assert (g.status, g.deadline) == (duel.OPEN, NOW + duel.ACCEPT_TIMEOUT)
    await storage.set_duel_message(g.id, 99)
    assert (await storage.get_duel(g.id)).message_id == 99

    g, _ = await storage.apply_duel(g.id, lambda x: (duel.accept(x, 2, "Bob", NOW, delay), None))
    assert await storage.next_duel_deadline() == NOW + delay
    assert await storage.due_duels(NOW) == []
    now = NOW
    for shooter in (1, 1):
        now += delay
        assert [d.id for d in await storage.due_duels(now)] == [g.id]
        g, _ = await storage.apply_duel(g.id, lambda x, n=now: (duel.tick(x, n), None))
        assert g.status == duel.FIRE
        g, _ = await storage.apply_duel(g.id, lambda x, s=shooter, n=now: duel.shoot(x, s, x.round, n, delay))
    assert g.status == duel.FINISHED and (await storage.get_duel(g.id)).history == g.history
    assert await storage.duel_leaderboard(CHAT) == [("Ada", 1, 0), ("Bob", 0, 1)]
    assert await storage.next_duel_deadline() is None

    with pytest.raises(duel.DuelError):
        await storage.apply_duel(g.id, lambda x: (duel.cancel(x, 1, NOW), None))
    with pytest.raises(duel.DuelError):
        await storage.apply_duel(999_999, lambda x: (x, None))


async def test_duello_purge(storage):
    old = await storage.create_duel(CHAT, 1, "Ada", None, None, NOW - timedelta(days=10))
    await storage.purge_games(NOW - timedelta(days=7))
    assert await storage.get_duel(old.id) is None


async def test_duello_diti_piu_veloci(storage):
    from abreveilverdetto import duel

    delay = timedelta(seconds=5)

    async def round_won(game, shooter, ms):
        fire_at = game.deadline
        game, _ = await storage.apply_duel(game.id, lambda x: (duel.tick(x, fire_at), None))
        shot_at = fire_at + timedelta(milliseconds=ms)
        game, _ = await storage.apply_duel(game.id, lambda x: duel.shoot(x, shooter, x.round, shot_at, delay))
        return game

    g = await storage.create_duel(CHAT, 1, "Ada", None, None, NOW)
    g, _ = await storage.apply_duel(g.id, lambda x: (duel.accept(x, 2, "Bob", NOW, delay), None))
    g = await round_won(g, 1, 450)
    assert await storage.fastest_fingers(CHAT) == [("Ada", 450)]
    assert await storage.duel_leaderboard(CHAT) == []  # duello non finito: niente vittorie, ma il record c'è
    g, _ = await storage.apply_duel(g.id, lambda x: duel.shoot(x, 2, x.round, NOW, delay))  # falsa partenza di Bob
    assert await storage.fastest_fingers(CHAT) == [("Ada", 450)]  # i punti regalati non hanno un tempo
    assert g.status == duel.FINISHED

    g2 = await storage.create_duel(CHAT, 2, "Bob", None, None, NOW)
    g2, _ = await storage.apply_duel(g2.id, lambda x: (duel.accept(x, 1, "Ada", NOW, delay), None))
    g2 = await round_won(g2, 1, 900)  # più lento del record: resta 450
    g2 = await round_won(g2, 2, 210)
    assert await storage.fastest_fingers(CHAT) == [("Bob", 210), ("Ada", 450)]
    assert await storage.fastest_fingers(CHAT, limit=1) == [("Bob", 210)]
    assert await storage.fastest_fingers(CHAT + 1) == []
    assert await storage.duel_leaderboard(CHAT) == [("Ada", 1, 0), ("Bob", 0, 1)]
