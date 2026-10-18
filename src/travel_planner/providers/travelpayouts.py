"""Travelpayouts (Aviasales) Data API.

Fiyatlar son ~48 saatte Aviasales'te yapılan aramalardan önbelleğe alınır; yani
anlık değil, ama bütün dünya için ücretsiz ve tarama için yeterince taze.
Dokümantasyon: https://support.travelpayouts.com/hc/en-us/articles/203956163
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import date

import requests

from .base import FlightProvider, Offer

log = logging.getLogger(__name__)

API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
SITE_URL = "https://www.aviasales.com"


class TravelpayoutsProvider(FlightProvider):
    def __init__(
        self,
        token: str,
        currency: str = "try",
        market: str = "tr",
        min_interval: float = 0.25,
        retries: int = 4,
        session: requests.Session | None = None,
    ):
        self.token = token
        self.currency = currency.lower()
        self.market = market
        self.min_interval = min_interval
        self.retries = retries
        self.session = session or requests.Session()
        self._lock = threading.Lock()
        self._last_call = 0.0

    def _throttle(self) -> None:
        with self._lock:
            wait = self._last_call + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

    def _get(self, params: dict) -> dict:
        for attempt in range(self.retries):
            self._throttle()
            try:
                resp = self.session.get(
                    API_URL, params=params, headers={"X-Access-Token": self.token}, timeout=30
                )
            except requests.RequestException as exc:
                log.warning("Ağ hatası (%s), tekrar deneniyor: %s", params["destination"], exc)
            else:
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code not in (429, 500, 502, 503, 504):
                    log.warning("API %s: %s", resp.status_code, resp.text[:200])
                    return {}
                log.info("API %s, bekleniyor...", resp.status_code)
            time.sleep(2 ** (attempt + 1))
        return {}

    def round_trips(
        self, origin: str, destination: str, depart_month: str, return_month: str
    ) -> list[Offer]:
        params = {
            "origin": origin,
            "destination": destination,
            "departure_at": depart_month,
            "return_at": return_month,
            "one_way": "false",
            "unique": "false",
            "sorting": "price",
            "currency": self.currency,
            "market": self.market,
            "limit": 1000,
            "page": 1,
        }
        data = self._get(params)
        if not data.get("success"):
            return []
        currency = data.get("currency", self.currency)
        offers = []
        for row in data.get("data", []):
            try:
                offers.append(
                    Offer(
                        origin=row.get("origin_airport") or row["origin"],
                        destination=row.get("destination_airport") or row["destination"],
                        depart=date.fromisoformat(row["departure_at"][:10]),
                        ret=date.fromisoformat(row["return_at"][:10]),
                        price=float(row["price"]),
                        currency=currency,
                        airline=row.get("airline", ""),
                        transfers=int(row.get("transfers", 0)),
                        return_transfers=int(row.get("return_transfers", 0)),
                        link=SITE_URL + row["link"] if row.get("link") else "",
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                log.debug("Atlanan satır %s: %s", row, exc)
        return offers
