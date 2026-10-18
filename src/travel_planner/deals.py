"""Fırsat tespiti: fiyat, rotanın normal fiyatından belirgin şekilde düşük mü?"""

from __future__ import annotations

from dataclasses import dataclass

from .config import DealConfig
from .countries import Country
from .providers import Offer


@dataclass
class Deal:
    country: Country
    route_origin: str
    route_destination: str
    offer: Offer
    baseline: float | None

    @property
    def discount_pct(self) -> float | None:
        if not self.baseline:
            return None
        return (1 - self.offer.price / self.baseline) * 100


def is_deal(price: float, baseline: float | None, cfg: DealConfig) -> bool:
    if cfg.always_notify_below is not None and price <= cfg.always_notify_below:
        return True
    if baseline is None:
        return False
    return price <= baseline * (1 - cfg.min_discount_pct / 100)


def should_notify(price: float, last_notified: float | None, cfg: DealConfig) -> bool:
    if last_notified is None:
        return True
    return price <= last_notified * (1 - cfg.renotify_drop_pct / 100)
