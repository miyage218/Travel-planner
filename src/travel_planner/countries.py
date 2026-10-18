"""Ülke ve vize veri seti."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources

VISA_LABELS = {
    "vizesiz": "🟢 Vizesiz",
    "kapida_vize": "🟡 Kapıda vize",
    "e_vize": "🟠 E-vize",
    "vizeli": "🔴 Vizeli",
}


@dataclass(frozen=True)
class Country:
    code: str
    name: str
    region: str
    visa: str
    airports: tuple[str, ...]
    note: str = ""

    @property
    def visa_label(self) -> str:
        return VISA_LABELS.get(self.visa, self.visa)


@dataclass
class CountryFilter:
    visa: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)

    def matches(self, country: Country) -> bool:
        if self.include and country.code not in self.include:
            return False
        if country.code in self.exclude:
            return False
        if self.visa and country.visa not in self.visa:
            return False
        if self.regions and country.region not in self.regions:
            return False
        return True


def load_countries(path: str | None = None) -> list[Country]:
    if path:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    else:
        raw = json.loads(
            resources.files("travel_planner").joinpath("data/countries.json").read_text("utf-8")
        )
    countries = []
    for item in raw["countries"]:
        if item["visa"] not in VISA_LABELS:
            raise ValueError(f"{item['code']}: bilinmeyen vize durumu {item['visa']!r}")
        countries.append(
            Country(
                code=item["code"],
                name=item["name"],
                region=item["region"],
                visa=item["visa"],
                airports=tuple(item["airports"]),
                note=item.get("note", ""),
            )
        )
    return countries


def select_countries(countries: list[Country], flt: CountryFilter) -> list[Country]:
    return [c for c in countries if flt.matches(c)]
