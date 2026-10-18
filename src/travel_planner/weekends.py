"""Cuma gidiş / pazar dönüş tarih çiftleri."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

FRIDAY = 4


@dataclass(frozen=True)
class Weekend:
    depart: date  # Cuma
    ret: date  # Pazar

    @property
    def months(self) -> tuple[str, str]:
        return self.depart.strftime("%Y-%m"), self.ret.strftime("%Y-%m")


def upcoming_weekends(start: date, weeks: int) -> list[Weekend]:
    """`start` gününden (dahil) itibaren `weeks` adet cuma-pazar çifti."""
    first_friday = start + timedelta(days=(FRIDAY - start.weekday()) % 7)
    return [
        Weekend(depart=fri, ret=fri + timedelta(days=2))
        for fri in (first_friday + timedelta(weeks=i) for i in range(weeks))
    ]
