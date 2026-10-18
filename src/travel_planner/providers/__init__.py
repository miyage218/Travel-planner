from .base import FlightProvider, Offer
from .mock import MockProvider
from .travelpayouts import TravelpayoutsProvider

__all__ = ["FlightProvider", "Offer", "MockProvider", "TravelpayoutsProvider", "make_provider"]


def make_provider(cfg) -> FlightProvider:
    if cfg.provider == "mock":
        return MockProvider()
    if cfg.provider == "travelpayouts":
        if not cfg.travelpayouts_token:
            raise SystemExit(
                "TRAVELPAYOUTS_TOKEN ortam değişkeni gerekli "
                "(ücretsiz: https://www.travelpayouts.com → Profil → API token)."
            )
        return TravelpayoutsProvider(
            cfg.travelpayouts_token, currency=cfg.search.currency, market=cfg.search.market
        )
    raise SystemExit(f"Bilinmeyen sağlayıcı: {cfg.provider}")
