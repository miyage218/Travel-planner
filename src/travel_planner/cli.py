"""Komut satırı arayüzü."""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from datetime import date

from .config import load_config
from .countries import VISA_LABELS, load_countries, select_countries
from .notifiers import Notifier, fmt_money, format_deal
from .providers import make_provider
from .scanner import filter_new_deals, mark_notified, scan
from .storage import Storage
from .weekends import upcoming_weekends


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _apply_overrides(cfg, args) -> None:
    if getattr(args, "provider", None):
        cfg.provider = args.provider
    if getattr(args, "visa", None):
        cfg.countries.visa = _csv(args.visa)
    if getattr(args, "region", None):
        cfg.countries.regions = _csv(args.region)
    if getattr(args, "only", None):
        cfg.countries.include = [c.upper() for c in _csv(args.only)]
    if getattr(args, "origin", None):
        cfg.search.origins = [o.upper() for o in _csv(args.origin)]
    if getattr(args, "weeks", None):
        cfg.search.weeks_ahead = args.weeks


def cmd_scan(cfg, args) -> int:
    countries = select_countries(load_countries(cfg.countries_file), cfg.countries)
    weekends = upcoming_weekends(date.today(), cfg.search.weeks_ahead)
    storage = Storage(cfg.db_path)
    provider = make_provider(cfg)

    result = scan(provider, storage, countries, weekends, cfg)
    new_deals = filter_new_deals(result.deals, storage, cfg)
    logging.info(
        "%d sorgu, %d teklif, %d rota için hafta sonu fiyatı, %d fırsat (%d yeni)",
        result.queries, result.offers, len(result.cheapest), len(result.deals), len(new_deals),
    )

    if args.dry_run:
        for d in new_deals:
            print(format_deal(d), end="\n\n")
    elif new_deals:
        Notifier(cfg.notify).send(new_deals)
        mark_notified(new_deals, storage)
    else:
        print("Bu taramada yeni fırsat yok.")
    storage.prune(keep_days=max(cfg.deals.history_days * 2, 180))
    return 0


def cmd_countries(cfg, args) -> int:
    countries = select_countries(load_countries(cfg.countries_file), cfg.countries)
    for c in countries:
        note = f"  ({c.note})" if c.note else ""
        print(f"{c.code:5} {c.name:30} {c.visa_label:16} {','.join(c.airports):14}{note}")
    counts = Counter(c.visa for c in countries)
    print(f"\nToplam {len(countries)} ülke: " + ", ".join(
        f"{VISA_LABELS[k]} {counts[k]}" for k in VISA_LABELS if counts[k]
    ))
    return 0


def cmd_weekends(cfg, args) -> int:
    for w in upcoming_weekends(date.today(), cfg.search.weeks_ahead):
        print(f"Cuma {w.depart:%d.%m.%Y} → Pazar {w.ret:%d.%m.%Y}")
    return 0


def cmd_cheapest(cfg, args) -> int:
    """Veritabanındaki son taramadan, her hafta sonu için en ucuz ülkeler."""
    storage = Storage(cfg.db_path)
    countries = {a: c for c in load_countries(cfg.countries_file) for a in c.airports}
    rows = storage.conn.execute(
        "SELECT depart, ret, destination, MIN(price), currency, link FROM observations"
        " WHERE scanned_at = (SELECT MAX(scanned_at) FROM observations) AND depart >= ?"
        " GROUP BY depart, destination ORDER BY depart, MIN(price)",
        (date.today().isoformat(),),
    ).fetchall()
    if not rows:
        print("Henüz veri yok, önce `travel-planner scan` çalıştırın.")
        return 0
    shown: Counter = Counter()
    for depart, ret, dest, price, currency, link in rows:
        if shown[depart] >= args.top:
            continue
        shown[depart] += 1
        c = countries.get(dest)
        name = f"{c.name} {c.visa_label}" if c else dest
        print(f"{depart} → {ret}  {dest:4} {name:42} {fmt_money(price, currency):>12}  {link}")
    return 0


def cmd_test_notify(cfg, args) -> int:
    notifier = Notifier(cfg.notify)
    print("Aktif kanallar:", ", ".join(notifier.channels) or "yok")
    notifier.send_text("✅ Travel Planner test bildirimi: kurulum çalışıyor.", title="Test")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="travel-planner",
        description="Türk pasaportuyla gidilebilecek ülkelere cuma-pazar uçak bileti fırsatı tarayıcısı",
    )
    parser.add_argument("-c", "--config", default="config.toml", help="ayar dosyası")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    def filters(p):
        p.add_argument("--visa", help="ör. vizesiz,kapida_vize,e_vize,vizeli")
        p.add_argument("--region", help="ör. Avrupa,Asya,Orta Doğu,Kafkasya,Afrika,Amerika,Okyanusya")
        p.add_argument("--only", help="sadece bu ülke kodları, ör. RS,GE,JP")

    p = sub.add_parser("scan", help="tüm hafta sonlarını tara, fırsatları bildir")
    filters(p)
    p.add_argument("--origin", help="kalkış şehir/havalimanı kodları, ör. IST,SAW,ESB")
    p.add_argument("--weeks", type=int, help="kaç hafta ileriye bakılsın")
    p.add_argument("--provider", choices=["travelpayouts", "mock"])
    p.add_argument("--dry-run", action="store_true", help="bildirim göndermeden yazdır")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("countries", help="ülke/vize listesini göster")
    filters(p)
    p.set_defaults(func=cmd_countries)

    p = sub.add_parser("weekends", help="taranacak cuma-pazar tarihlerini göster")
    p.add_argument("--weeks", type=int)
    p.set_defaults(func=cmd_weekends)

    p = sub.add_parser("cheapest", help="son taramada her hafta sonunun en ucuz rotaları")
    p.add_argument("--top", type=int, default=5)
    p.set_defaults(func=cmd_cheapest)

    p = sub.add_parser("test-notify", help="bildirim kanallarını dene")
    p.set_defaults(func=cmd_test_notify)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    cfg = load_config(args.config)
    _apply_overrides(cfg, args)
    return args.func(cfg, args)


if __name__ == "__main__":
    sys.exit(main())
