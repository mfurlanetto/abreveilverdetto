import random
from collections import Counter

from abreveilverdetto import game


def test_draw_multipli_di_5_tra_5_e_100_equiprobabili():
    rng = random.Random(42)
    counts = Counter(game.draw(rng) for _ in range(20_000))
    assert set(counts) == set(range(5, 101, 5))
    # 20 valori equiprobabili: ~1000 ciascuno
    assert all(800 < c < 1200 for c in counts.values())


def test_118_non_raggiungibile_130_si():
    singles = set(range(5, 101, 5))
    totals = singles | {a + b for a in singles for b in singles}
    assert 118 not in totals
    assert 130 in totals


def test_pick_animation():
    assert game.pick_animation(100, 1) is game.WIN_ANIMATION
    assert game.pick_animation(100, 2) is game.WIN_ANIMATION
    assert game.pick_animation(130, 2).file.endswith("130_MartinGarrix.gif")
    assert game.pick_animation(95, 2) is game.SO_CLOSE_ANIMATION
    assert game.pick_animation(105, 2) is game.SO_CLOSE_ANIMATION
    assert game.pick_animation(95, 1) is None
    assert game.pick_animation(60, 2) is None


def test_result_emoji():
    assert game.result_emoji(95) != game.result_emoji(100) != game.result_emoji(105)


def test_fibonacci():
    assert game.fibonacci(0) == []
    assert game.fibonacci(1) == [1]
    assert game.fibonacci(10) == [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]


def test_fibonacci_reply_limiti():
    rng = random.Random(1)
    assert game.fibonacci_reply("1", rng) == "1"
    assert game.fibonacci_reply("0", rng).startswith("Il minimo è 1.")
    out = game.fibonacci_reply("50", rng)
    assert out.startswith("Il massimo consentito è 10.")
    assert len(out.splitlines()[-1].split(", ")) <= 10
    assert "non è un numero" in game.fibonacci_reply("ciao", rng)


def test_fibonacci_reply_lunghezza_sempre_valida():
    rng = random.Random(7)
    for n in range(1, 11):
        for _ in range(50):
            seq = game.fibonacci_reply(str(n), rng).split(", ")
            assert 1 <= len(seq) <= n
