"""Regole pure della morra cinese."""

from datetime import UTC, datetime, timedelta

import pytest

from abreveilverdetto import morra
from abreveilverdetto.morra import PAPER, ROCK, SCISSORS, MorraError, MorraGame

T0 = datetime(2026, 11, 15, 20, 0, tzinfo=UTC)
A, B, C = 1, 2, 3


def open_game(target=None):
    return MorraGame(1, -100, A, "Ada", morra.OPEN, T0, target_id=target, target_name="Bob" if target else None)


def playing():
    return morra.accept(open_game(), B, "Bob", T0)


@pytest.mark.parametrize(
    ("c", "o", "expected"),
    [(ROCK, SCISSORS, 1), (SCISSORS, PAPER, 1), (PAPER, ROCK, 1), (SCISSORS, ROCK, 2), (ROCK, ROCK, 0)],
)
def test_round_winner(c, o, expected):
    assert morra.round_winner(c, o) == expected


def test_accetta():
    with pytest.raises(MorraError, match="te stesso"):
        morra.accept(open_game(), A, "Ada", T0)
    g = playing()
    assert (g.status, g.opponent_id, g.opponent_name) == (morra.PLAYING, B, "Bob")
    with pytest.raises(MorraError, match="già accettato"):
        morra.accept(g, C, "Cy", T0)


def test_sfida_diretta_solo_al_destinatario():
    g = open_game(target=B)
    with pytest.raises(MorraError, match="per Bob"):
        morra.accept(g, C, "Cy", T0)
    assert morra.accept(g, B, "Bob", T0).status == morra.PLAYING


def test_annulla_solo_lo_sfidante_e_solo_prima_di_iniziare():
    with pytest.raises(MorraError, match="Solo chi"):
        morra.cancel(open_game(), B, T0)
    assert morra.cancel(open_game(), A, T0).status == morra.CANCELLED
    with pytest.raises(MorraError, match="già iniziata"):
        morra.cancel(playing(), A, T0)


def test_mosse_segrete_e_round():
    g = playing()
    with pytest.raises(MorraError, match="Non stai giocando"):
        morra.choose(g, C, ROCK, T0)
    g, r = morra.choose(g, A, ROCK, T0)
    assert r is None and g.challenger_choice == ROCK and g.has_chosen(A) and not g.has_chosen(B)
    with pytest.raises(MorraError, match="già scelto"):
        morra.choose(g, A, PAPER, T0)
    g, r = morra.choose(g, B, SCISSORS, T0)
    assert r.winner == 1
    assert (g.challenger_score, g.opponent_score, g.history) == (1, 0, "rs")
    assert g.challenger_choice is None and g.opponent_choice is None  # nuovo round


def test_pari_si_ripete_e_non_conta():
    g, _ = morra.choose(playing(), A, ROCK, T0)
    g, r = morra.choose(g, B, ROCK, T0)
    assert r.winner == 0
    assert (g.challenger_score, g.opponent_score, g.history, g.status) == (0, 0, "", morra.PLAYING)


def play(g, c, o):
    g, _ = morra.choose(g, A, c, T0)
    return morra.choose(g, B, o, T0)


def test_al_meglio_di_3():
    g, _ = play(playing(), ROCK, SCISSORS)  # Ada 1-0
    g, _ = play(g, ROCK, PAPER)  # 1-1
    assert g.status == morra.PLAYING
    g, _ = play(g, PAPER, PAPER)  # pari
    g, _ = play(g, SCISSORS, PAPER)  # Ada 2-1
    assert g.status == morra.FINISHED
    assert g.winner == (A, "Ada") and g.loser == (B, "Bob")
    assert g.rounds == [("r", "s"), ("r", "p"), ("s", "p")]
    with pytest.raises(MorraError, match="finita"):
        morra.choose(g, A, ROCK, T0)


def test_vince_l_avversario_due_a_zero():
    g, _ = play(playing(), ROCK, PAPER)
    g, _ = play(g, SCISSORS, ROCK)
    assert g.status == morra.FINISHED and g.winner == (B, "Bob")


def test_sfida_aperta_scade_dopo_5_minuti():
    g = open_game()
    assert not g.is_expired(T0 + timedelta(minutes=4, seconds=59))
    assert g.is_expired(T0 + timedelta(minutes=5))
    with pytest.raises(MorraError, match="nessuno ha accettato"):
        morra.accept(g, B, "Bob", T0 + timedelta(minutes=5))


def test_mossa_entro_60_secondi_e_round_che_rinnova_il_tempo():
    g = playing()  # accettata a T0
    assert g.deadline == T0 + timedelta(seconds=60)
    g, _ = morra.choose(g, A, ROCK, T0 + timedelta(seconds=30))
    assert g.deadline == T0 + timedelta(seconds=60)  # una sola mossa non rinnova il tempo
    with pytest.raises(MorraError, match="tempo scaduto"):
        morra.choose(g, B, PAPER, T0 + timedelta(seconds=60))
    g, result = morra.choose(g, B, ROCK, T0 + timedelta(seconds=50))  # pari: il round si ripete
    assert result.winner == 0 and g.deadline == T0 + timedelta(seconds=110)
    g, _ = morra.choose(g, A, ROCK, T0 + timedelta(seconds=100))
    g, _ = morra.choose(g, B, SCISSORS, T0 + timedelta(seconds=105))
    assert g.deadline == T0 + timedelta(seconds=165)


def test_fine_partita_e_annullamento_tolgono_la_scadenza():
    g = playing()
    for t in (1, 2):
        g, _ = morra.choose(g, A, ROCK, T0 + timedelta(seconds=t))
        g, _ = morra.choose(g, B, SCISSORS, T0 + timedelta(seconds=t))
    assert g.status == morra.FINISHED and g.deadline is None and not g.is_expired(T0 + timedelta(days=1))
    assert morra.cancel(open_game(), A, T0).deadline is None


def test_expire():
    with pytest.raises(MorraError, match="non è scaduta"):
        morra.expire(playing(), T0)
    g = morra.expire(playing(), T0 + timedelta(seconds=60))
    assert (g.status, g.deadline) == (morra.EXPIRED, None)
    assert morra.expired_notice(g) == "Partita annullata: tempo scaduto per la mossa"
    assert morra.expired_notice(open_game()) == "Sfida scaduta: nessuno ha accettato in tempo"
    with pytest.raises(MorraError, match="tempo scaduto"):
        morra.choose(g, A, ROCK, T0)


def test_mossa_sconosciuta():
    with pytest.raises(MorraError, match="sconosciuta"):
        morra.choose(playing(), A, "x", T0)
