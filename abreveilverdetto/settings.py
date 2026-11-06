"""Configurazione letta dalle variabili d'ambiente.

Nessun segreto vive nel repository: token e chiavi arrivano solo dall'ambiente.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MEDIA_DIR = ROOT / "media"


class ConfigError(RuntimeError):
    """Configurazione mancante o non valida."""


def derive_webhook_secret(token: str) -> str:
    """Segreto del webhook stabile tra i riavvii, derivato dal token.

    Deve restare uguale tra un avvio e l'altro: con lo scale-to-zero l'update che
    risveglia l'istanza è stato spedito da Telegram con il segreto precedente.
    """
    return hmac.new(token.encode(), b"abreveilverdetto-webhook", hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    database_url: str | None = None
    webhook_base_url: str | None = None
    webhook_secret: str = ""
    webhook_path: str = "telegram"
    port: int = 8000
    listen: str = "0.0.0.0"  # noqa: S104 - deve ascoltare su tutte le interfacce nel container
    openweathermap_api_key: str | None = None
    timezone: ZoneInfo = field(default_factory=lambda: ZoneInfo("Europe/Rome"))
    http_timeout: float = 10.0
    # Per un Bot API server locale o per i test end-to-end; di norma non va impostato.
    telegram_api_base_url: str | None = None

    @property
    def use_webhook(self) -> bool:
        return bool(self.webhook_base_url)

    @property
    def webhook_url(self) -> str:
        if not self.webhook_base_url:
            raise ConfigError("WEBHOOK_BASE_URL non impostato")
        return f"{self.webhook_base_url.rstrip('/')}/{self.webhook_path}"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if env is None else env)
        token = env.get("TELEGRAM_TOKEN", "").strip()
        if not token:
            raise ConfigError("TELEGRAM_TOKEN è obbligatorio")

        kwargs: dict[str, object] = {
            "telegram_token": token,
            "database_url": env.get("DATABASE_URL") or None,
            "webhook_base_url": env.get("WEBHOOK_BASE_URL") or None,
            "openweathermap_api_key": env.get("OPENWEATHERMAP_API_KEY") or None,
            "telegram_api_base_url": env.get("TELEGRAM_API_BASE_URL") or None,
        }
        if env.get("WEBHOOK_SECRET"):
            secret = env["WEBHOOK_SECRET"]
            # Vincoli del parametro secret_token di setWebhook (Bot API)
            if not (1 <= len(secret) <= 256) or not all(c.isascii() and (c.isalnum() or c in "_-") for c in secret):
                raise ConfigError("WEBHOOK_SECRET: 1-256 caratteri tra A-Z, a-z, 0-9, _ e -")
            kwargs["webhook_secret"] = secret
        else:
            kwargs["webhook_secret"] = derive_webhook_secret(token)
        if env.get("PORT"):
            kwargs["port"] = int(env["PORT"])
        if env.get("BOT_TIMEZONE"):
            kwargs["timezone"] = ZoneInfo(env["BOT_TIMEZONE"])
        return cls(**kwargs)  # type: ignore[arg-type]
