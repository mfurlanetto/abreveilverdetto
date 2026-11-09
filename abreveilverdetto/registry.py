"""Registro unico dei comandi del bot.

Ogni comando si dichiara una volta sola: bottone del menu, funzione, eventuali
bottoni propri e comandi slash. Menu, routing e registrazione degli handler si
ricavano da qui, e le incoerenze (chiavi duplicate, prefissi in conflitto,
callback_data troppo lunghi) fanno fallire l'avvio invece di un bottone muto.

Aggiungere un comando del menu = una voce ``MenuCommand`` in ``COMMANDS``
(abreveilverdetto/commands/__init__.py).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

MENU_PREFIX = "menu"
MAX_CALLBACK_DATA_BYTES = 64  # limite della Bot API per callback_data
MAX_BUTTONS_PER_ROW = 8  # oltre, i bottoni diventano illeggibili sul telefono

_KEY = re.compile(r"^[a-z0-9]+$")
# Comandi slash: 1-32 caratteri tra lettere minuscole, cifre e underscore (Bot API, BotCommand)
_SLASH = re.compile(r"^[a-z0-9_]{1,32}$")

Handler = Callable[[Any, Any], Awaitable[None]]


class RegistryError(ValueError):
    """Dichiarazione dei comandi incoerente."""


@dataclass(frozen=True)
class Callback:
    """Bottoni propri di un comando: callback_data ``<prefix>:<…>`` che rispetta ``pattern``.

    ``pattern`` descrive solo la parte dopo ``<prefix>:``; la regex completa è
    ancorata automaticamente.
    """

    prefix: str
    pattern: str
    handler: Handler

    @property
    def regex(self) -> str:
        return rf"^{re.escape(self.prefix)}:(?:{self.pattern})$"

    def data(self, *parts: object) -> str:
        """callback_data per un bottone di questo comando, con controllo del limite di 64 byte."""
        value = ":".join([self.prefix, *map(str, parts)])
        if not re.match(self.regex, value):
            raise RegistryError(f"callback_data {value!r} non rispetta {self.regex}")
        if len(value.encode()) > MAX_CALLBACK_DATA_BYTES:
            raise RegistryError(f"callback_data {value!r} supera {MAX_CALLBACK_DATA_BYTES} byte")
        return value


@dataclass(frozen=True)
class SlashCommand:
    names: tuple[str, ...]
    handler: Handler
    description: str


@dataclass(frozen=True)
class MenuCommand:
    key: str
    label: str
    action: Handler  # (CallbackQuery, context)
    row: int
    callbacks: tuple[Callback, ...] = ()

    @property
    def callback_data(self) -> str:
        return f"{MENU_PREFIX}:{self.key}"


@dataclass(frozen=True)
class Registry:
    menu: tuple[MenuCommand, ...]
    slash: tuple[SlashCommand, ...] = ()
    _by_key: dict[str, MenuCommand] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate()
        object.__setattr__(self, "_by_key", {c.key: c for c in self.menu})

    # --- Validazione ------------------------------------------------------------------

    def _validate(self) -> None:
        errors: list[str] = []
        keys: set[str] = set()
        for cmd in self.menu:
            if not _KEY.match(cmd.key):
                errors.append(f"chiave {cmd.key!r}: solo lettere minuscole e cifre")
            if cmd.key in keys:
                errors.append(f"chiave duplicata: {cmd.key!r}")
            keys.add(cmd.key)
            if not cmd.label.strip():
                errors.append(f"{cmd.key}: etichetta vuota")
            if len(cmd.callback_data.encode()) > MAX_CALLBACK_DATA_BYTES:
                errors.append(f"{cmd.key}: callback_data oltre {MAX_CALLBACK_DATA_BYTES} byte")

        prefixes: dict[str, str] = {MENU_PREFIX: "(menu)"}
        for cmd in self.menu:
            for cb in cmd.callbacks:
                if not _KEY.match(cb.prefix):
                    errors.append(f"{cmd.key}: prefisso {cb.prefix!r} non valido")
                if cb.prefix in prefixes:
                    errors.append(f"{cmd.key}: prefisso {cb.prefix!r} già usato da {prefixes[cb.prefix]}")
                prefixes[cb.prefix] = cmd.key
                try:
                    re.compile(cb.regex)
                except re.error as exc:
                    errors.append(f"{cmd.key}: regex {cb.pattern!r} non valida ({exc})")

        rows = sorted({c.row for c in self.menu})
        if rows and rows != list(range(len(rows))):
            errors.append(f"righe del menu non consecutive da 0: {rows}")
        for row in rows:
            size = sum(1 for c in self.menu if c.row == row)
            if size > MAX_BUTTONS_PER_ROW:
                errors.append(f"riga {row}: {size} bottoni (max {MAX_BUTTONS_PER_ROW})")

        names: set[str] = set()
        for sc in self.slash:
            if not sc.names:
                errors.append("comando slash senza nome")
            for name in sc.names:
                if not _SLASH.match(name):
                    errors.append(f"/{name}: nome non valido per Telegram")
                if name in names:
                    errors.append(f"/{name}: duplicato")
                names.add(name)
            if not (1 <= len(sc.description) <= 256):
                errors.append(f"/{sc.names[0] if sc.names else '?'}: descrizione di 1-256 caratteri")

        if errors:
            raise RegistryError("Registro comandi non valido:\n- " + "\n- ".join(errors))

    # --- Accesso ----------------------------------------------------------------------

    def get(self, key: str) -> MenuCommand | None:
        return self._by_key.get(key)

    def keys(self) -> list[str]:
        return [c.key for c in self.menu]

    def layout(self) -> list[list[MenuCommand]]:
        """Righe del menu nell'ordine di dichiarazione."""
        rows: dict[int, list[MenuCommand]] = {}
        for cmd in self.menu:
            rows.setdefault(cmd.row, []).append(cmd)
        return [rows[r] for r in sorted(rows)]

    def callbacks(self) -> Iterator[Callback]:
        for cmd in self.menu:
            yield from cmd.callbacks

    @property
    def menu_regex(self) -> str:
        return rf"^{MENU_PREFIX}:[a-z0-9]+$"
