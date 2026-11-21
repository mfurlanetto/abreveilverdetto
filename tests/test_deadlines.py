import asyncio
from datetime import UTC, datetime, timedelta

from abreveilverdetto.deadlines import RETRY_AFTER, DeadlineTimer

T0 = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


def test_schedule_tiene_solo_la_scadenza_piu_vicina():
    async def action():
        return None

    timer = DeadlineTimer(action, Clock())
    timer.schedule(None)
    assert timer.next is None
    timer.schedule(T0 + timedelta(seconds=60))
    timer.schedule(T0 + timedelta(minutes=5))
    assert timer.next == T0 + timedelta(seconds=60)
    timer.schedule(T0 + timedelta(seconds=10))
    assert timer.next == T0 + timedelta(seconds=10)


async def test_fire_programma_la_scadenza_successiva_e_riprova_dopo_un_errore():
    clock = Clock()
    results = [T0 + timedelta(minutes=5), RuntimeError("db giù")]

    async def action():
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    timer = DeadlineTimer(action, clock)
    await timer.fire()
    assert timer.next == T0 + timedelta(minutes=5)
    await timer.fire()
    assert timer.next == T0 + RETRY_AFTER


async def test_run_esegue_alla_scadenza_e_si_risveglia_per_una_scadenza_anticipata():
    clock = Clock()
    fired = asyncio.Event()

    async def action():
        fired.set()
        return None

    timer = DeadlineTimer(action, clock)
    task = asyncio.create_task(timer.run())
    try:
        timer.schedule(T0 + timedelta(hours=1))  # lontana: il timer dorme
        await asyncio.sleep(0.05)
        assert not fired.is_set()
        timer.schedule(T0)  # già scaduta: il timer si sveglia e la esegue subito
        await asyncio.wait_for(fired.wait(), timeout=1)
        assert timer.next is None
    finally:
        task.cancel()
