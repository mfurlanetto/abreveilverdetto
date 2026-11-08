"""Avvio: ``python -m abreveilverdetto``.

Con WEBHOOK_BASE_URL (o RENDER_EXTERNAL_URL, impostata da Render) usa il webhook;
altrimenti usa il long polling (sviluppo locale).
"""

from __future__ import annotations

import logging
import sys

from .app import ALLOWED_UPDATES, build_application
from .settings import ConfigError, Settings


def configure_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
        stream=sys.stdout,
    )
    # httpx logga ogni richiesta con l'URL completo: include il token del bot
    # (api.telegram.org/bot<TOKEN>/...) e la API key del meteo.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> int:
    configure_logging()
    log = logging.getLogger("abreveilverdetto")
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        log.error("Configurazione non valida: %s", exc)
        return 2

    app = build_application(settings)
    if settings.use_webhook:
        log.info("Avvio in modalità webhook su porta %d", settings.port)
        app.run_webhook(
            listen=settings.listen,
            port=settings.port,
            url_path=settings.webhook_path,
            webhook_url=settings.webhook_url,
            secret_token=settings.webhook_secret,
            allowed_updates=ALLOWED_UPDATES,
            # Mai True: con lo scale-to-zero l'update che risveglia l'istanza è in coda.
            drop_pending_updates=False,
        )
    else:
        log.info("WEBHOOK_BASE_URL non impostato: avvio in long polling")
        app.run_polling(allowed_updates=ALLOWED_UPDATES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
