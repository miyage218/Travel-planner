"""Tüm ülkeler × tüm hafta sonları taraması."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date

from .config import Config
from .countries import Country
from .deals import Deal, is_deal, should_notify
from .providers import FlightProvider, Offer
from .storage import Storage, utcnow
from .weekends import Weekend

log = logging.getLogger(__name__)


@dataclass
class ScanResult:
    queries: int = 0
    offers: int = 0
    # (origin, destination) → {cuma tarihi: en ucuz teklif}
    cheapest: dict[tuple[str, str], dict[date, Offer]] = field(default_factory=dict)
    deals: list[Deal] = field(default_factory=list)


def _cheapest_weekend_offers(
    offers: list[Offer], weekends: set[tuple[date, date]], cfg: Config
) -> dict[date, Offer]:
    best: dict[date, Offer] = {}
    for o in offers:
        if (o.depart, o.ret) not in weekends:
            continue
        if cfg.search.max_transfers is not None and o.max_transfers > cfg.search.max_transfers:
            continue
        if o.depart not in best or o.price < best[o.depart].price:
            best[o.depart] = o
    return best


def scan(
    provider: FlightProvider,
    storage: Storage,
    countries: list[Country],
    weekends: list[Weekend],
    cfg: Config,
) -> ScanResult:
    result = ScanResult()
    weekend_pairs = {(w.depart, w.ret) for w in weekends}
    month_pairs = sorted({w.months for w in weekends})
    country_of = {}
    routes = []
    for country in countries:
        for airport in country.airports:
            country_of[airport] = country
            for origin in cfg.search.origins:
                routes.append((origin, airport))

    def fetch(origin: str, destination: str) -> tuple[str, str, list[Offer], int]:
        offers: list[Offer] = []
        for dep_month, ret_month in month_pairs:
            offers.extend(provider.round_trips(origin, destination, dep_month, ret_month))
        return origin, destination, offers, len(month_pairs)

    log.info(
        "%d ülke, %d rota, %d hafta sonu taranıyor (%d API sorgusu)",
        len(countries), len(routes), len(weekends), len(routes) * len(month_pairs),
    )
    with ThreadPoolExecutor(max_workers=cfg.workers) as pool:
        futures = [pool.submit(fetch, o, d) for o, d in routes]
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                origin, destination, offers, n_queries = fut.result()
            except Exception as exc:
                log.error("Rota taranamadı: %s", exc)
                continue
            result.queries += n_queries
            result.offers += len(offers)
            best = _cheapest_weekend_offers(offers, weekend_pairs, cfg)
            if best:
                result.cheapest[(origin, destination)] = best
            if i % 25 == 0:
                log.info("%d/%d rota tamamlandı", i, len(routes))

    currency = cfg.search.currency.lower()
    scanned_at = utcnow()
    for (origin, destination), best in result.cheapest.items():
        storage.add_observations(
            [
                (origin, destination, o.depart.isoformat(), o.ret.isoformat(), o.price,
                 currency, o.airline, o.max_transfers, o.link)
                for o in best.values()
            ],
            scanned_at=scanned_at,
        )

    for (origin, destination), best in result.cheapest.items():
        baseline = storage.baseline(
            origin, destination, currency, cfg.deals.history_days, cfg.deals.min_samples
        )
        for offer in best.values():
            if cfg.search.max_price is not None and offer.price > cfg.search.max_price:
                continue
            if not is_deal(offer.price, baseline, cfg.deals):
                continue
            result.deals.append(
                Deal(country_of[destination], origin, destination, offer, baseline)
            )

    result.deals.sort(key=lambda d: (-(d.discount_pct or 0), d.offer.price))
    return result


def filter_new_deals(deals: list[Deal], storage: Storage, cfg: Config) -> list[Deal]:
    """Daha önce bildirilmiş ve fiyatı yeterince düşmemiş fırsatları ayıklar."""
    fresh = []
    for d in deals:
        key = (d.route_origin, d.route_destination, d.offer.depart.isoformat(), d.offer.ret.isoformat())
        if should_notify(d.offer.price, storage.last_notified_price(*key), cfg.deals):
            fresh.append(d)
    return fresh


def mark_notified(deals: list[Deal], storage: Storage) -> None:
    for d in deals:
        storage.mark_notified(
            d.route_origin, d.route_destination,
            d.offer.depart.isoformat(), d.offer.ret.isoformat(), d.offer.price,
        )
