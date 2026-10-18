from datetime import date

from travel_planner.config import Config, DealConfig
from travel_planner.countries import CountryFilter, load_countries, select_countries
from travel_planner.deals import is_deal, should_notify
from travel_planner.notifiers import format_message
from travel_planner.providers import FlightProvider, MockProvider, Offer
from travel_planner.scanner import filter_new_deals, mark_notified, scan
from travel_planner.storage import Storage
from travel_planner.weekends import upcoming_weekends


def test_countries_dataset_is_valid():
    countries = load_countries()
    assert len(countries) > 180
    codes = {c.code for c in countries}
    assert {"RS", "GE", "JP", "DE", "US"} <= codes
    assert all(c.airports for c in countries)
    visa_free = select_countries(countries, CountryFilter(visa=["vizesiz"]))
    assert all(c.visa == "vizesiz" for c in visa_free)


def test_weekends_are_friday_to_sunday():
    weekends = upcoming_weekends(date(2026, 10, 18), 10)  # pazar
    assert weekends[0].depart == date(2026, 10, 23)
    assert all(w.depart.weekday() == 4 and (w.ret - w.depart).days == 2 for w in weekends)
    # bugün cuma ise o hafta sonu da dahil
    assert upcoming_weekends(date(2026, 10, 23), 1)[0].depart == date(2026, 10, 23)
    # ay sınırını aşan hafta sonu: 30 Ekim cuma → 1 Kasım pazar
    assert ("2026-10", "2026-11") in {w.months for w in weekends}


def test_deal_rules():
    cfg = DealConfig(min_discount_pct=25)
    assert is_deal(700, 1000, cfg)
    assert not is_deal(800, 1000, cfg)
    assert not is_deal(100, None, cfg)
    assert is_deal(100, None, DealConfig(always_notify_below=500))
    assert should_notify(900, None, cfg)
    assert not should_notify(990, 1000, cfg)
    assert should_notify(940, 1000, cfg)


class FixedProvider(FlightProvider):
    """Her hafta sonu 1000 TL, tek bir hafta sonu 500 TL; ayrıca hafta sonu dışı teklifler."""

    def __init__(self, cheap_friday: date):
        self.cheap_friday = cheap_friday

    def round_trips(self, origin, destination, depart_month, return_month):
        out = []
        for w in upcoming_weekends(date(2026, 10, 18), 12):
            if w.months != (depart_month, return_month):
                continue
            price = 500 if w.depart == self.cheap_friday else 1000
            out.append(Offer(origin, destination, w.depart, w.ret, price, "try", "PC"))
            out.append(Offer(origin, destination, w.depart, date.fromordinal(w.ret.toordinal() + 1), 100, "try"))
        return out


def test_scan_detects_and_deduplicates_deals():
    cheap = date(2026, 11, 13)
    cfg = Config()
    countries = select_countries(load_countries(), CountryFilter(include=["RS"]))
    weekends = upcoming_weekends(date(2026, 10, 18), 12)
    storage = Storage(":memory:")

    result = scan(FixedProvider(cheap), storage, countries, weekends, cfg)
    assert [d.offer.depart for d in result.deals] == [cheap]
    deal = result.deals[0]
    assert deal.baseline == 1000 and round(deal.discount_pct) == 50
    assert deal.offer.ret == date(2026, 11, 15)  # pazartesi dönüşlü 100 TL'lik teklif sayılmadı

    new = filter_new_deals(result.deals, storage, cfg)
    assert len(new) == 1
    mark_notified(new, storage)
    again = scan(FixedProvider(cheap), storage, countries, weekends, cfg)
    assert filter_new_deals(again.deals, storage, cfg) == []

    text = format_message(new)
    assert "Sırbistan" in text and "Vizesiz" in text and "500 TL" in text


def test_mock_provider_scan_runs_end_to_end():
    cfg = Config(provider="mock")
    countries = select_countries(load_countries(), CountryFilter(regions=["Kafkasya"]))
    result = scan(MockProvider(), Storage(":memory:"), countries, upcoming_weekends(date(2026, 10, 18), 52), cfg)
    assert result.cheapest
    for best in result.cheapest.values():
        assert all(o.depart.weekday() == 4 for o in best.values())
