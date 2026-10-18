"""Bildirim kanalları: konsol, Telegram, ntfy (telefon push), e-posta."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import requests

from .config import NotifyConfig
from .deals import Deal

log = logging.getLogger(__name__)

DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def fmt_money(value: float, currency: str) -> str:
    symbol = {"try": "TL", "eur": "€", "usd": "$"}.get(currency.lower(), currency.upper())
    return f"{value:,.0f}".replace(",", ".") + f" {symbol}"


def format_deal(deal: Deal) -> str:
    o = deal.offer
    c = deal.country
    lines = [
        f"✈️ {o.origin} → {o.destination} · {c.name} ({c.visa_label})",
        f"📅 {DAYS[o.depart.weekday()]} {o.depart:%d.%m.%Y} → {DAYS[o.ret.weekday()]} {o.ret:%d.%m.%Y}",
    ]
    price = f"💰 {fmt_money(o.price, o.currency)}"
    if deal.baseline:
        price += (
            f" (normal ~{fmt_money(deal.baseline, o.currency)}, %{deal.discount_pct:.0f} ucuz)"
        )
    lines.append(price)
    transfers = "aktarmasız" if o.max_transfers == 0 else f"{o.max_transfers} aktarma"
    lines.append(f"🛫 {o.airline or '?'} · {transfers}")
    if c.note:
        lines.append(f"ℹ️ {c.note}")
    if o.link:
        lines.append(f"🔗 {o.link}")
    return "\n".join(lines)


def format_message(deals: list[Deal]) -> str:
    header = f"🔥 FIRSAT VAR! {len(deals)} uygun hafta sonu bileti bulundu\n"
    body = "\n\n".join(format_deal(d) for d in deals)
    footer = "\n\nVize kurallarını seyahatten önce mutlaka teyit edin."
    return header + "\n" + body + footer


def _chunks(text: str, size: int) -> list[str]:
    parts, current = [], ""
    for block in text.split("\n\n"):
        if current and len(current) + len(block) + 2 > size:
            parts.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}" if current else block
    if current:
        parts.append(current)
    return [p[:size] for p in parts]


class Notifier:
    def __init__(self, cfg: NotifyConfig):
        self.cfg = cfg

    @property
    def channels(self) -> list[str]:
        c = self.cfg
        out = []
        if c.console:
            out.append("console")
        if c.telegram_bot_token and c.telegram_chat_id:
            out.append("telegram")
        if c.ntfy_topic:
            out.append("ntfy")
        if c.smtp_host and c.email_to:
            out.append("email")
        return out

    def send(self, deals: list[Deal]) -> None:
        if not deals:
            return
        self.send_text(format_message(deals), title=f"✈️ {len(deals)} uçak bileti fırsatı")

    def send_text(self, text: str, title: str = "Uçak bileti fırsatı") -> None:
        for channel in self.channels:
            try:
                getattr(self, f"_send_{channel}")(text, title)
            except Exception as exc:  # bir kanal bozuksa diğerleri yine çalışsın
                log.error("%s bildirimi gönderilemedi: %s", channel, exc)

    def _send_console(self, text: str, title: str) -> None:
        print(text)

    def _send_telegram(self, text: str, title: str) -> None:
        url = f"https://api.telegram.org/bot{self.cfg.telegram_bot_token}/sendMessage"
        for part in _chunks(text, 4000):
            r = requests.post(
                url,
                json={
                    "chat_id": self.cfg.telegram_chat_id,
                    "text": part,
                    "disable_web_page_preview": True,
                },
                timeout=30,
            )
            r.raise_for_status()

    def _send_ntfy(self, text: str, title: str) -> None:
        url = f"{self.cfg.ntfy_server.rstrip('/')}/{self.cfg.ntfy_topic}"
        for part in _chunks(text, 3500):
            r = requests.post(
                url,
                data=part.encode("utf-8"),
                params={"title": title, "tags": "airplane", "priority": "high"},
                timeout=30,
            )
            r.raise_for_status()

    def _send_email(self, text: str, title: str) -> None:
        c = self.cfg
        msg = EmailMessage()
        msg["Subject"] = title
        msg["From"] = c.smtp_user or c.email_to
        msg["To"] = c.email_to
        msg.set_content(text)
        with smtplib.SMTP(c.smtp_host, c.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            if c.smtp_user:
                smtp.login(c.smtp_user, c.smtp_password or "")
            smtp.send_message(msg)
