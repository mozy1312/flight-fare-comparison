"""Mock flight provider — generates realistic demo data.

Always works without any API key.  Useful for:
- UI development and testing
- Demonstrating the app before configuring real credentials
- Fallback when all real providers fail
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from providers.base import (
    FlightOffer, FlightProvider, FlightSegment,
    ProviderInfo, SearchResult,
)

logger = logging.getLogger(__name__)

_AIRLINES = [
    {"code": "AY", "name": "Finnair"}, {"code": "LH", "name": "Lufthansa"},
    {"code": "TK", "name": "Turkish Airlines"}, {"code": "BA", "name": "British Airways"},
    {"code": "AF", "name": "Air France"}, {"code": "EK", "name": "Emirates"},
    {"code": "QR", "name": "Qatar Airways"}, {"code": "KL", "name": "KLM"},
    {"code": "OS", "name": "Austrian Airlines"}, {"code": "LX", "name": "SWISS"},
]

_COUNTRIES = [
    ("Finland", "FI", "EUR"), ("Turkey", "TR", "TRY"), ("India", "IN", "INR"),
    ("Brazil", "BR", "BRL"), ("Argentina", "AR", "ARS"), ("Poland", "PL", "PLN"),
    ("Hungary", "HU", "HUF"), ("Romania", "RO", "RON"), ("Bulgaria", "BG", "BGN"),
    ("Malaysia", "MY", "MYR"), ("Thailand", "TH", "THB"), ("Indonesia", "ID", "IDR"),
    ("Philippines", "PH", "PHP"), ("Egypt", "EG", "EGP"), ("UAE", "AE", "AED"),
]


class MockProvider(FlightProvider):
    """Mock provider that returns synthetic but realistic flight data."""

    def __init__(self, seed: int | None = None) -> None:
        self._seed = seed

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="Demo Mode", slug="mock",
            description="Generates realistic demo data. No API key required.",
            requires_api_key=False, api_key_url="",
            free_tier="Unlimited", rate_limit="None",
            best_for="Development, testing, and demonstrations",
            supports_pos_comparison=True, status="active",
        )

    def validate_credentials(self) -> bool:
        return True

    def search_flights(
        self, origin: str, destination: str, departure_date: str,
        return_date: str | None = None, adults: int = 1, children: int = 0,
        cabin_class: str = "ECONOMY", currency: str = "EUR", max_results: int = 10,
    ) -> SearchResult:
        start = time.perf_counter()
        rng = random.Random(self._seed or hash(f"{origin}{destination}{departure_date}"))

        offers = []
        for country_name, country_code, local_currency in _COUNTRIES:
            num = rng.randint(1, 3)
            base = rng.uniform(80.0, 600.0)
            for _ in range(num):
                airline = rng.choice(_AIRLINES)
                price_local = round(base * rng.uniform(0.85, 1.35), 2)
                price_eur = round(price_local * rng.uniform(0.9, 1.1), 2)
                stops = rng.choices([0, 1, 2], weights=[30, 50, 20])[0]
                dur_h = rng.randint(2, 14)
                dur_m = rng.choice([0, 15, 30, 45])
                dep_h = rng.randint(6, 22)
                dep_m = rng.choice([0, 15, 30, 45])
                arr_h = (dep_h + dur_h + stops) % 24

                offers.append(FlightOffer(
                    id=f"mock-{country_code}-{rng.randint(1000,9999)}",
                    price=price_eur, currency="EUR",
                    airline=airline["code"], airline_name=airline["name"],
                    segments=[FlightSegment(
                        departure_airport=origin,
                        departure_time=f"{departure_date}T{dep_h:02d}:{dep_m:02d}:00",
                        arrival_airport=destination,
                        arrival_time=f"{departure_date}T{arr_h:02d}:{dep_m:02d}:00",
                        airline=airline["code"], airline_name=airline["name"],
                        flight_number=f"{airline['code']}{rng.randint(100,999)}",
                        duration=f"PT{dur_h}H{dur_m:02d}M",
                    )],
                    total_duration=f"{dur_h}h {dur_m:02d}m",
                    stops=stops, cabin_class=cabin_class.upper(),
                    source=f"mock-{country_code}",
                ))
            base += rng.uniform(-40, 80)

        offers.sort(key=lambda o: o.price)
        offers = offers[:max(15, max_results)]
        duration = time.perf_counter() - start
        prices = [o.price for o in offers]
        return SearchResult(
            offers=offers, total_offers=len(offers),
            cheapest_price=min(prices) if prices else 0.0,
            average_price=round(sum(prices) / len(prices), 2) if prices else 0.0,
            most_expensive_price=max(prices) if prices else 0.0,
            search_duration_seconds=round(duration, 2),
        )

    def health_check(self) -> dict[str, Any]:
        return {"provider": self.info.slug, "healthy": True, "message": "Demo mode — always available"}
