from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Offer:
    origin: str
    destination: str
    depart: date
    ret: date
    price: float
    currency: str
    airline: str = ""
    transfers: int = 0
    return_transfers: int = 0
    link: str = ""

    @property
    def max_transfers(self) -> int:
        return max(self.transfers, self.return_transfers)


class FlightProvider(ABC):
    @abstractmethod
    def round_trips(
        self, origin: str, destination: str, depart_month: str, return_month: str
    ) -> list[Offer]:
        """Verilen ay(lar)daki gidiş-dönüş tekliflerini döndürür (tüm tarih kombinasyonları)."""
