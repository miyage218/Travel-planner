"""Deterministik sahte veri: API anahtarı olmadan denemek ve test için."""

from __future__ import annotations

import calendar
import hashlib
from datetime import date

from .base import FlightProvider, Offer


def _rand(*parts) -> float:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


class MockProvider(FlightProvider):
    def round_trips(
        self, origin: str, destination: str, depart_month: str, return_month: str
    ) -> list[Offer]:
        year, month = map(int, depart_month.split("-"))
        base = 3000 + 12000 * _rand(origin, destination)
        offers = []
        for day in range(1, calendar.monthrange(year, month)[1] + 1):
            dep = date(year, month, day)
            if dep.weekday() != 4:
                continue
            ret = date.fromordinal(dep.toordinal() + 2)
            if ret.strftime("%Y-%m") != return_month:
                continue
            r = _rand(origin, destination, dep)
            # %10 ihtimalle fırsat fiyatı
            factor = 0.5 + 0.2 * r if r < 0.1 else 0.85 + 0.4 * r
            offers.append(
                Offer(
                    origin=origin,
                    destination=destination,
                    depart=dep,
                    ret=ret,
                    price=round(base * factor, -1),
                    currency="try",
                    airline="XX",
                    transfers=int(r * 3) % 2,
                    link=f"https://www.aviasales.com/search/{origin}{dep:%d%m}{destination}{ret:%d%m}1",
                )
            )
        return offers
