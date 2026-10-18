"""Ayarlar: config.toml + ortam değişkenleri (gizli anahtarlar)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .countries import CountryFilter


@dataclass
class SearchConfig:
    origins: list[str] = field(default_factory=lambda: ["IST"])
    weeks_ahead: int = 52
    currency: str = "try"
    max_transfers: int | None = None
    max_price: float | None = None
    market: str = "tr"


@dataclass
class DealConfig:
    # Normal fiyata göre en az bu kadar yüzde ucuz olmalı
    min_discount_pct: float = 25.0
    # Normal fiyat = son `history_days` gündeki hafta sonu fiyatlarının medyanı
    history_days: int = 90
    # Medyan hesabı için gereken en az gözlem sayısı
    min_samples: int = 6
    # Bu fiyatın altındaki her bilet, geçmişten bağımsız olarak fırsat sayılır
    always_notify_below: float | None = None
    # Aynı uçuş tekrar bildirilmeden önce fiyatın ne kadar daha düşmesi gerektiği (%)
    renotify_drop_pct: float = 5.0


@dataclass
class NotifyConfig:
    console: bool = True
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    ntfy_topic: str | None = None
    ntfy_server: str = "https://ntfy.sh"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_to: str | None = None


@dataclass
class Config:
    search: SearchConfig = field(default_factory=SearchConfig)
    deals: DealConfig = field(default_factory=DealConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    countries: CountryFilter = field(default_factory=CountryFilter)
    provider: str = "travelpayouts"
    travelpayouts_token: str | None = None
    db_path: str = "data/history.db"
    countries_file: str | None = None
    workers: int = 4


def _apply(obj, values: dict) -> None:
    for key, value in values.items():
        if not hasattr(obj, key):
            raise ValueError(f"Bilinmeyen ayar: {key}")
        setattr(obj, key, value)


def load_config(path: str | Path | None = None) -> Config:
    cfg = Config()
    if path and Path(path).exists():
        with open(path, "rb") as fh:
            raw = tomllib.load(fh)
        for section, target in (
            ("search", cfg.search),
            ("deals", cfg.deals),
            ("notify", cfg.notify),
            ("countries", cfg.countries),
        ):
            _apply(target, raw.pop(section, {}))
        _apply(cfg, raw)

    def env(name: str, default):
        # Boş değerler (ör. tanımsız GitHub secret) ayarı ezmesin
        return os.environ.get(name) or default

    cfg.travelpayouts_token = env("TRAVELPAYOUTS_TOKEN", cfg.travelpayouts_token)
    n = cfg.notify
    n.telegram_bot_token = env("TELEGRAM_BOT_TOKEN", n.telegram_bot_token)
    n.telegram_chat_id = env("TELEGRAM_CHAT_ID", n.telegram_chat_id)
    n.ntfy_topic = env("NTFY_TOPIC", n.ntfy_topic)
    n.smtp_host = env("SMTP_HOST", n.smtp_host)
    n.smtp_port = int(env("SMTP_PORT", n.smtp_port))
    n.smtp_user = env("SMTP_USER", n.smtp_user)
    n.smtp_password = env("SMTP_PASSWORD", n.smtp_password)
    n.email_to = env("EMAIL_TO", n.email_to)
    return cfg
