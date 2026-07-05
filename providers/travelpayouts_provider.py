"""Travelpayouts provider — free affiliate flight data API.

Free registration with no credit card required. Provides cached/aggregated
fares, price trends, and popular routes. Best for price comparison and
trend analysis rather than live booking.

Get your token: https://www.travelpayouts.com/developers/api
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from providers.base import (
    AuthError, FlightOffer, FlightProvider, FlightSegment,
    NetworkError, NoResultsError, ProviderError, ProviderInfo,
    RateLimitError, SearchResult,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.travelpayouts.com"
TIMEOUT = 30.0


class TravelpayoutsProvider(FlightProvider):
    """Travelpayouts affiliate data API provider.

    Parameters
    ----------
    token: Your Travelpayouts API token.
    """

    def __init__(self, token: str) -> None:
        self._token = token.strip()
        self._client = httpx.Client(timeout=TIMEOUT, headers={"X-Access-Token": self._token})

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="Travelpayouts", slug="travelpayouts",
            description="Free affiliate flight data API. Cached/aggregated fares.",
            requires_api_key=True, api_key_url="https://www.travelpayouts.com/developers/api",
            free_tier="Free registration, per-minute rate limits",
            rate_limit="30-600 RPM depending on endpoint",
            best_for="Price trends, deal pages, affiliate sites",
            supports_pos_comparison=False, status="active",
        )

    def validate_credentials(self) -> bool:
        try:
            resp = self._client.get(f"{BASE_URL}/v1/prices/cheap",
                params={"origin": "HEL", "destination": "LHR", "depart_date": "2026-01", "currency": "eur", "token": self._token},
                timeout=10.0)
            return resp.status_code == 200
        except Exception:
            return False

    def search_flights(
        self, origin: str, destination: str, departure_date: str,
        return_date: str | None = None, adults: int = 1, children: int = 0,
        cabin_class: str = "ECONOMY", currency: str = "EUR", max_results: int = 10,
    ) -> SearchResult:
        start = time.perf_counter()
        month = departure_date[:7]
        params: dict[str, Any] = {
            "origin": origin.upper(), "destination": destination.upper(),
            "depart_date": month, "currency": currency.lower(), "token": self._token,
        }
        if return_date: params["return_date"] = return_date[:7]

        try:
            resp = self._client.get(f"{BASE_URL}/v1/prices/cheap", params=params)
        except httpx.HTTPError as exc:
            raise NetworkError(f"Travelpayouts request failed: {exc}") from exc

        if resp.status_code == 401: raise AuthError("Invalid Travelpayouts token")
        if resp.status_code == 429: raise RateLimitError("Travelpayouts rate limit exceeded")
        if resp.status_code >= 400: raise ProviderError(f"Travelpayouts error: {resp.text[:500]}")

        data = resp.json().get("data", {})
        route_key = f"{origin.upper()}-{destination.upper()}"
        raw_offers = data.get(route_key, {})
        if not raw_offers: raise NoResultsError(f"No fares found {origin} → {destination} for {month}")

        offers = []
        for offer_id, raw in list(raw_offers.items())[:max_results]:
            parsed = self._parse_offer(raw, offer_id, origin, destination, currency)
            if parsed: offers.append(parsed)

        duration = time.perf_counter() - start
        prices = [o.price for o in offers]
        return SearchResult(
            offers=offers, total_offers=len(offers),
            cheapest_price=min(prices) if prices else 0.0,
            average_price=round(sum(prices)/len(prices), 2) if prices else 0.0,
            most_expensive_price=max(prices) if prices else 0.0,
            search_duration_seconds=round(duration, 2),
        )

    def _parse_offer(self, raw: dict, offer_id: str, origin: str, destination: str, currency: str) -> FlightOffer | None:
        try:
            price = float(raw.get("price", 0))
            airline = raw.get("airline", "")
            dep_time = raw.get("departure_at", "")
            return FlightOffer(
                id=f"tp-{offer_id}", price=price, currency=currency.upper(),
                airline=airline, airline_name=self._AIRLINE_NAMES.get(airline, airline),
                segments=[FlightSegment(
                    departure_airport=origin, departure_time=dep_time,
                    arrival_airport=destination, arrival_time=dep_time,
                    airline=airline, airline_name=self._AIRLINE_NAMES.get(airline, airline),
                    flight_number=offer_id, duration="",
                )],
                total_duration="", stops=0, cabin_class="ECONOMY",
                source="travelpayouts", deep_link=raw.get("link"),
            )
        except Exception as exc:
            logger.warning("Failed to parse Travelpayouts offer: %s", exc)
            return None

    _AIRLINE_NAMES = {
        "AY": "Finnair", "BA": "British Airways", "AF": "Air France",
        "LH": "Lufthansa", "TK": "Turkish", "EK": "Emirates",
        "QR": "Qatar", "AA": "American", "DL": "Delta", "UA": "United",
        "FR": "Ryanair", "U2": "easyJet", "PC": "Pegasus", "6E": "IndiGo",
        "AI": "Air India",
    }
