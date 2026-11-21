"""Timer che si sveglia alla prossima scadenza nota, invece di interrogare il DB a intervalli.

Il polling continuo (es. ogni 5 secondi) terrebbe sveglio Neon, che sul piano gratuito
sospende il compute dopo 5 minuti di inattività e ha un monte ore mensile
(https://neon.com/docs/introduction/plans). Qui il DB viene letto solo quando c'è
davvero qualcosa da far scadere.

Uso: ``schedule(when)`` a ogni nuova scadenza; ``run()`` in un task di background
chiama ``action()`` alla scadenza più vicina. ``action`` restituisce la scadenza
successiva ancora in sospeso (o None), così le scadenze sopravvivono anche a un
riavvio: basta una ``schedule`` iniziale letta dallo storage.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

RETRY_AFTER = timedelta(seconds=30)


class DeadlineTimer:
    def __init__(
        self,
        action: Callable[[], Awaitable[datetime | None]],
        now: Callable[[], datetime],
    ) -> None:
        self._action = action
        self._now = now
        self._next: datetime | None = None
        self._wake = asyncio.Event()

    @property
    def next(self) -> datetime | None:
        return self._next

    def schedule(self, when: datetime | None) -> None:
        """Registra una scadenza; conta solo se anticipa quella già in programma."""
        if when is None or (self._next is not None and self._next <= when):
            return
        self._next = when
        self._wake.set()

    async def _sleep_until_due(self) -> bool:
        """True quando la scadenza in programma è arrivata; False se è cambiata nel frattempo."""
        self._wake.clear()
        if self._next is None:
            await self._wake.wait()
            return False
        delay = (self._next - self._now()).total_seconds()
        if delay <= 0:
            return True
        try:
            await asyncio.wait_for(self._wake.wait(), timeout=delay)
        except TimeoutError:
            return True
        return False

    async def fire(self) -> None:
        """Esegue l'azione e programma la scadenza successiva (in caso di errore riprova)."""
        self._next = None
        try:
            following = await self._action()
        except Exception:
            logger.exception("Gestione delle scadenze fallita, riprovo tra %s", RETRY_AFTER)
            following = self._now() + RETRY_AFTER
        self.schedule(following)

    async def run(self) -> None:
        while True:
            if await self._sleep_until_due():
                await self.fire()
