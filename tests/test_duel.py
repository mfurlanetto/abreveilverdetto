"""Regole pure del duello."""

from datetime import UTC, datetime, timedelta

import pytest

from abreveilverdetto import duel
from abreveilverdetto.duel import DuelError, DuelGame, Round

T0 = datetime(2026, 11, 21, 20, 0, tzinfo=UTC)
A, B, C = 1, 2, 3
DELAY = timedelta(seconds=5)


def open_game(target=None):
    return DuelGame(
        1,
        -100,
        A,
        "Ada",
        duel.OPEN,
        T0,
        target_id=target,
        target_name="Bob" if target else None,
        deadline=T0 + duel.ACCEPT_TIMEOUT,
    )


def armed():
    return duel.accept(open_game(), B, "Bob", T0, DELAY)


def fired():
    return duel.fire(armed(), T0 + DELAY)


def test_accetta_e_arma_il_round():
    with pytest.raises(DuelError, match="te stesso"):
        duel.accept(open_game(), A, "Ada", T0, DELAY)
    g = armed()
    assert (g.status, g.opponent_id, g.round, g.deadline) == (duel.ARMED, B, 1, T0 + DELAY)
    with pytest.raises(DuelError, match="già accettato"):
        duel.accept(g, C, "Cy", T0, DELAY)
    with pytest.raises(DuelError, match="per Bob"):
        duel.accept(open_game(target=B), C, "Cy", T0, DELAY)


def test_sfida_scade_dopo_5_minuti():
    g = open_game()
    assert not g.is_expired(T0 + timedelta(minutes=4, seconds=59))
    assert g.is_expired(T0 + duel.ACCEPT_TIMEOUT)
    with pytest.raises(DuelError, match="nessuno ha accettato"):
        duel.accept(g, B, "Bob", T0 + duel.ACCEPT_TIMEOUT, DELAY)


def test_fuoco_solo_all_ora_prevista():
    with pytest.raises(DuelError, match="momento del via"):
        duel.fire(armed(), T0 + DELAY - timedelta(milliseconds=1))
    g = fired()
    assert (g.status, g.deadline) == (duel.FIRE, T0 + DELAY + duel.SHOOT_TIMEOUT)
    assert not g.is_expired(T0 + DELAY)  # ARMED -> FIRE non è una scadenza


def test_fuoco_solo_per_il_round_previsto():
    g, _ = duel.shoot(armed(), A, 1, T0 + timedelta(seconds=1), DELAY)  # falsa partenza: ora round 2
    with pytest.raises(DuelError, match="Round cambiato"):
        duel.fire(g, T0 + timedelta(minutes=1), round_no=1)
    assert duel.fire(g, T0 + timedelta(minutes=1), round_no=2).status == duel.FIRE


def test_colpo_valido_con_tempo_di_reazione():
    g, r = duel.shoot(fired(), B, 1, T0 + DELAY + timedelta(milliseconds=420), DELAY)
    assert r == Round(2, duel.SHOT, 420)
    assert (g.opponent_score, g.round, g.status) == (1, 2, duel.ARMED)
    assert g.deadline == T0 + DELAY + timedelta(milliseconds=420) + DELAY
    assert g.rounds == [r]


def test_falsa_partenza_regala_il_round_anche_se_il_timer_e_in_ritardo():
    g, r = duel.shoot(armed(), A, 1, T0 + timedelta(seconds=1), DELAY)
    assert r == Round(2, duel.FALSE_START)
    assert g.opponent_score == 1
    # Ora del via passata ma "FUOCO!" non ancora scritto: per chi gioca è ancora prima del via.
    g, r = duel.shoot(armed(), B, 1, T0 + DELAY + timedelta(seconds=1), DELAY)
    assert r == Round(1, duel.FALSE_START)


def test_colpo_del_round_precedente_non_conta():
    g, _ = duel.shoot(fired(), A, 1, T0 + DELAY + timedelta(milliseconds=300), DELAY)
    with pytest.raises(DuelError, match="Troppo tardi"):
        duel.shoot(g, B, 1, T0 + DELAY + timedelta(milliseconds=350), DELAY)
    with pytest.raises(DuelError, match="Non stai partecipando"):
        duel.shoot(g, C, 2, T0 + DELAY, DELAY)


def test_al_meglio_di_3():
    g = armed()
    now = T0
    for shooter in (A, B, A):
        now += DELAY
        g = duel.fire(g, now)
        g, _ = duel.shoot(g, shooter, g.round, now + timedelta(milliseconds=200), DELAY)
        now += timedelta(milliseconds=200)
    assert (g.status, g.challenger_score, g.opponent_score, g.deadline) == (duel.FINISHED, 2, 1, None)
    assert g.winner == (A, "Ada") and g.loser == (B, "Bob")
    with pytest.raises(DuelError, match="già finito"):
        duel.shoot(g, A, g.round, now, DELAY)


def test_nessuno_spara_entro_10_secondi():
    g = fired()
    assert not g.is_expired(T0 + DELAY + timedelta(seconds=9))
    assert g.is_expired(T0 + DELAY + duel.SHOOT_TIMEOUT)
    with pytest.raises(DuelError, match="nessuno ha sparato"):
        duel.shoot(g, A, 1, T0 + DELAY + duel.SHOOT_TIMEOUT, DELAY)
    g = duel.expire(g, T0 + DELAY + duel.SHOOT_TIMEOUT)
    assert (g.status, g.deadline) == (duel.EXPIRED, None)


def test_tick():
    assert duel.tick(armed(), T0 + DELAY).status == duel.FIRE
    assert duel.tick(fired(), T0 + DELAY + duel.SHOOT_TIMEOUT).status == duel.EXPIRED
    assert duel.tick(open_game(), T0 + duel.ACCEPT_TIMEOUT).status == duel.EXPIRED
    with pytest.raises(DuelError):
        duel.tick(armed(), T0)


def test_annulla():
    with pytest.raises(DuelError, match="Solo chi"):
        duel.cancel(open_game(), B, T0)
    with pytest.raises(DuelError, match="già iniziato"):
        duel.cancel(armed(), A, T0)
    assert duel.cancel(open_game(), A, T0).status == duel.CANCELLED


@pytest.mark.parametrize("r", [Round(1, duel.SHOT, 420), Round(2, duel.FALSE_START), Round(2, duel.SHOT, 0)])
def test_round_encode_decode(r):
    assert Round.decode(r.encode()) == r
