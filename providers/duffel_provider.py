"""Duffel flight provider — recommended replacement for Amadeus.

Duffel offers a modern REST API with 300+ airlines, free test mode,
no IATA accreditation required, and transparent pricing ($3/order).

Get your API key: https://duffel.com/signup
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

BASE_URL = "https://api.duffel.com/air"
TIMEOUT = 30.0


class DuffelProvider(FlightProvider):
    """Duffel flight search provider.

    Parameters
    ----------
    api_key: Your Duffel access token.
    test_mode: When ``True``, uses sandbox environment (free).
    """

    def __init__(self, api_key: str, test_mode: bool = True) -> None:
        self._api_key = api_key.strip()
        self._test_mode = test_mode
        self._client = httpx.Client(
            base_url=BASE_URL, timeout=TIMEOUT,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Duffel-Version": "v2",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="Duffel", slug="duffel",
            description="Modern flight booking API with 300+ airlines. Free test mode.",
            requires_api_key=True, api_key_url="https://duffel.com/signup",
            free_tier="Test mode free (sandbox data)",
            rate_limit="1,500:1 search-to-book ratio before excess fees",
            best_for="Booking startups, Amadeus migration",
            supports_pos_comparison=True, status="active",
        )

    def validate_credentials(self) -> bool:
        try:
            resp = self._client.get("/airlines?page=1&limit=1")
            return resp.status_code == 200
        except Exception:
            return False

    def search_flights(
        self, origin: str, destination: str, departure_date: str,
        return_date: str | None = None, adults: int = 1, children: int = 0,
        cabin_class: str = "ECONOMY", currency: str = "EUR", max_results: int = 10,
    ) -> SearchResult:
        start = time.perf_counter()
        slices = [{"origin": origin.upper(), "destination": destination.upper(), "departure_date": departure_date}]
        if return_date:
            slices.append({"origin": destination.upper(), "destination": origin.upper(), "departure_date": return_date})

        cabin_map = {"ECONOMY": "economy", "PREMIUM_ECONOMY": "premium_economy", "BUSINESS": "business", "FIRST": "first"}
        payload = {
            "slices": slices,
            "passengers": [{"type": "adult"}] * adults + [{"type": "child"}] * children,
            "cabin_class": cabin_map.get(cabin_class.upper(), "economy"),
            "max_connections": 2,
        }

        try:
            resp = self._client.post("/offer_requests", json={"data": payload})
        except httpx.HTTPError as exc:
            raise NetworkError(f"Duffel request failed: {exc}") from exc

        if resp.status_code == 401: raise AuthError("Invalid Duffel API key")
        if resp.status_code == 429: raise RateLimitError("Duffel rate limit exceeded")
        if resp.status_code >= 400: raise ProviderError(f"Duffel error: {resp.text[:500]}")

        raw_offers = resp.json().get("data", {}).get("offers", [])
        if not raw_offers: raise NoResultsError(f"No flights found {origin} → {destination}")

        offers = [o for o in [self._parse_offer(r, currency) for r in raw_offers[:max_results]] if o]
        duration = time.perf_counter() - start
        prices = [o.price for o in offers]
        return SearchResult(
            offers=offers, total_offers=len(offers),
            cheapest_price=min(prices) if prices else 0.0,
            average_price=round(sum(prices)/len(prices), 2) if prices else 0.0,
            most_expensive_price=max(prices) if prices else 0.0,
            search_duration_seconds=round(duration, 2),
        )

    def _parse_offer(self, raw: dict, currency: str) -> FlightOffer | None:
        try:
            amount = float(raw.get("total_amount", 0))
            curr = raw.get("total_currency", currency)
            segments = []
            total_stops = 0
            total_duration = ""
            for slc in raw.get("slices", []):
                for seg in slc.get("segments", []):
                    carrier = seg.get("marketing_carrier", {})
                    segments.append(FlightSegment(
                        departure_airport=seg.get("origin", {}).get("iata_code", ""),
                        departure_time=seg.get("departing_at", ""),
                        arrival_airport=seg.get("destination", {}).get("iata_code", ""),
                        arrival_time=seg.get("arriving_at", ""),
                        airline=carrier.get("iata_code", ""),
                        airline_name=carrier.get("name", ""),
                        flight_number=f"{carrier.get('iata_code', '')}{seg.get('marketing_carrier_flight_number', '')}",
                        duration=seg.get("duration", ""),
                        aircraft=seg.get("aircraft", {}).get("name"),
                    ))
                total_stops += max(0, len(slc.get("segments", [])) - 1)
                if slc.get("segments"): total_duration = slc["segments"][0].get("duration", "")

            owner = raw.get("owner", {})
            return FlightOffer(
                id=raw.get("id", ""), price=amount, currency=curr,
                airline=owner.get("iata_code", segments[0].airline if segments else ""),
                airline_name=owner.get("name", segments[0].airline_name if segments else ""),
                segments=segments, total_duration=total_duration,
                stops=total_stops, cabin_class=raw.get("cabin_class", "ECONOMY").upper(),
                source="duffel", deep_link=None,
                last_ticketing_date=raw.get("expires_at", ""),
            )
        except Exception as exc:
            logger.warning("Failed to parse Duffel offer: %s", exc)
            return None

    def health_check(self) -> dict[str, Any]:
        healthy = self.validate_credentials()
        return {"provider": self.info.slug, "healthy": healthy, "test_mode": self._test_mode,
                "message": "OK" if healthy else "Invalid API key or network issue"}
