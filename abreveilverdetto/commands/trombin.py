"""/trombin: riepilogo di indici di borsa e materie prime (Yahoo Finance)."""

from __future__ import annotations

from datetime import UTC, datetime

from telegram import Update
from telegram.ext import ContextTypes

from ..markets import INSTRUMENTS, Quote
from ..services import RateLimitedError
from ..telegram_io import HTML, deps
from ..text import esc

RATE_LIMITED_TEXT = "📈 Yahoo Finance mi chiede di rallentare: riprova tra un minuto."
CLOSED_MARK = "*"


def format_it(value: float, decimals: int = 2) -> str:
    """Numero all'italiana: 51399.88 -> '51.399,88'."""
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def format_change(pct: float | None) -> str:
    if pct is None:
        return "     n.d."
    arrow = "▲" if pct > 0.005 else "▼" if pct < -0.005 else "="
    sign = "+" if pct > 0 else "-" if pct < 0 else ""
    return f"{arrow} {sign}{format_it(abs(pct))}%"


def format_report(quotes: dict[str, Quote], now: datetime, local_tz) -> str:
    """Tabella monospazio raggruppata per indici e materie prime."""
    # Righe brevi: il blocco monospazio di Telegram sul telefono va a capo oltre ~35-38 caratteri.
    labels = {i.symbol: i.name for i in INSTRUMENTS}
    prices = {s: format_it(q.price, q.decimals) for s, q in quotes.items()}
    name_w = max(len(v) for v in labels.values())
    price_w = max((len(v) for v in prices.values()), default=4)

    lines: list[str] = []
    any_closed = False
    group = None
    for inst in INSTRUMENTS:
        if inst.group != group:
            if group is not None:
                lines.append("")
            group = inst.group
            lines.append(group)
        quote = quotes.get(inst.symbol)
        if quote is None:
            lines.append(f"{labels[inst.symbol]:<{name_w}} {'n.d.':>{price_w}}")
            continue
        closed = not quote.is_open(now)
        any_closed |= closed
        mark = f" {CLOSED_MARK}" if closed else ""
        price = prices[inst.symbol]
        lines.append(f"{labels[inst.symbol]:<{name_w}} {price:>{price_w}} {format_change(quote.change_pct)}{mark}")

    stamp = now.astimezone(local_tz).strftime("%d/%m/%Y %H:%M")
    parts = [f"📈 <b>TROMBIN</b> · {stamp}", f"<pre>{esc(chr(10).join(lines))}</pre>"]
    notes = [
        "Variazione rispetto alla chiusura precedente.",
        "Oro e argento in $/oncia, petrolio in $/barile, gas in $/MMBtu, rame in $/libbra.",
    ]
    if any_closed:
        notes.append(f"{CLOSED_MARK} mercato chiuso: ultima chiusura.")
    notes.append("Fonte: Yahoo Finance (dati non ufficiali, possibili ritardi).")
    parts.append("<i>" + esc(" ".join(notes)) + "</i>")
    return "\n".join(parts)


async def trombin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = deps(context)
    try:
        quotes = await d.services.market_quotes()
    except RateLimitedError:
        await update.effective_message.reply_text(RATE_LIMITED_TEXT)
        return
    text = format_report(quotes, datetime.now(UTC), d.settings.timezone)
    await update.effective_message.reply_text(text, parse_mode=HTML)
