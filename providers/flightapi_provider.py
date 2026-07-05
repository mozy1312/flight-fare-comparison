"""FlightAPI.io provider — budget-friendly flight search.

Free tier: 20-100 calls/month. Paid tiers from $49/month.
Good for prototypes and small projects.

Get your key: https://flightapi.io
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

BASE_URL = "https://api.flightapi.io"
TIMEOUT = 30.0


class FlightAPIProvider(FlightProvider):
    """FlightAPI.io provider.

    Parameters
    ----------
    api_key: Your FlightAPI.io API key.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key.strip()
        self._client = httpx.Client(timeout=TIMEOUT)

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="FlightAPI.io", slug="flightapi",
            description="Budget-friendly flight search API. 700+ airlines.",
            requires_api_key=True, api_key_url="https://flightapi.io",
            free_tier="20-100 free calls/month",
            rate_limit="Plan-dependent",
            best_for="Budget prototypes, price comparison dashboards",
            supports_pos_comparison=True, status="active",
        )

    def validate_credentials(self) -> bool:
        try:
            resp = self._client.get(f"{BASE_URL}/airlines", params={"key": self._api_key}, timeout=10.0)
            return resp.status_code == 200
        except Exception:
            return False

    def search_flights(
        self, origin: str, destination: str, departure_date: str,
        return_date: str | None = None, adults: int = 1, children: int = 0,
        cabin_class: str = "ECONOMY", currency: str = "EUR", max_results: int = 10,
    ) -> SearchResult:
        start = time.perf_counter()
        params: dict[str, Any] = {
            "key": self._api_key, "dep": origin.upper(), "arr": destination.upper(),
            "date": departure_date, "adults": adults, "currency": currency.upper(), "limit": max_results,
        }
        if return_date: params["returnDate"] = return_date
        endpoint = f"{BASE_URL}/roundtrip" if return_date else f"{BASE_URL}/oneway"

        try:
            resp = self._client.get(endpoint, params=params)
        except httpx.HTTPError as exc:
            raise NetworkError(f"FlightAPI.io request failed: {exc}") from exc

        if resp.status_code == 401: raise AuthError("Invalid FlightAPI.io key")
        if resp.status_code == 429: raise RateLimitError("FlightAPI.io rate limit exceeded")
        if resp.status_code >= 400: raise ProviderError(f"FlightAPI.io error: {resp.text[:500]}")

        data = resp.json()
        raw_offers = data if isinstance(data, list) else data.get("flights", [])
        if not raw_offers: raise NoResultsError(f"No flights found {origin} → {destination}")

        offers = []
        for i, raw in enumerate(raw_offers[:max_results]):
            parsed = self._parse_offer(raw, i, currency)
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

    def _parse_offer(self, raw: dict, idx: int, currency: str) -> FlightOffer | None:
        try:
            price = float(raw.get("price", raw.get("total_amount", 0)))
            curr = raw.get("currency", currency)
            legs = raw.get("legs", raw.get("segments", []))
            segments = []
            for leg in legs:
                segments.append(FlightSegment(
                    departure_airport=leg.get("departureAirport", leg.get("dep", "")),
                    departure_time=leg.get("departureTime", leg.get("depTime", "")),
                    arrival_airport=leg.get("arrivalAirport", leg.get("arr", "")),
                    arrival_time=leg.get("arrivalTime", leg.get("arrTime", "")),
                    airline=leg.get("airline", leg.get("carrier", "")).upper(),
                    airline_name=leg.get("airlineName", leg.get("airline", "")),
                    flight_number=leg.get("flightNumber", "") or str(idx),
                    duration=leg.get("duration", ""),
                ))
            return FlightOffer(
                id=raw.get("id", f"fp-{idx}"), price=price, currency=curr,
                airline=segments[0].airline if segments else "",
                airline_name=segments[0].airline_name if segments else "",
                segments=segments, total_duration=raw.get("totalDuration", ""),
                stops=max(0, len(segments) - 1), cabin_class="ECONOMY",
                source="flightapi.io", deep_link=raw.get("bookingUrl", raw.get("deeplink")),
            )
        except Exception as exc:
            logger.warning("Failed to parse FlightAPI.io offer: %s", exc)
            return None
