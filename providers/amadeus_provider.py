"""Amadeus flight provider — LEGACY.

⚠️ DEPRECATION WARNING:
    Amadeus Self-Service API will be decommissioned on July 17, 2026.
    New users should use DuffelProvider instead.

This provider remains for existing users who already have Amadeus keys.

Docs: https://developers.amadeus.com
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

PROD_URL = "https://api.amadeus.com"
TEST_URL = "https://test.api.amadeus.com"
TIMEOUT = 30.0


class AmadeusProvider(FlightProvider):
    """Amadeus flight search provider (legacy).

    ⚠️ Decommissioning July 17, 2026. Migrate to Duffel.
    """

    def __init__(self, api_key: str, api_secret: str, test_mode: bool = True) -> None:
        self._api_key = api_key.strip()
        self._api_secret = api_secret.strip()
        self._base_url = TEST_URL if test_mode else PROD_URL
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._client = httpx.Client(timeout=TIMEOUT)

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="Amadeus", slug="amadeus",
            description="Legacy GDS flight API. Decommissioning July 2026.",
            requires_api_key=True, api_key_url="https://developers.amadeus.com",
            free_tier="~2,000 calls/month (test env, cached data)",
            rate_limit="10 TPS test / 40 TPS production",
            best_for="Existing users only — migrate to Duffel",
            supports_pos_comparison=True, status="deprecated",
        )

    def _get_token(self) -> str:
        if self._token and time.monotonic() < self._token_expiry - 60:
            return self._token
        try:
            resp = self._client.post(f"{self._base_url}/v1/security/oauth2/token", data={
                "grant_type": "client_credentials",
                "client_id": self._api_key,
                "client_secret": self._api_secret,
            })
        except httpx.HTTPError as exc:
            raise NetworkError(f"Amadeus auth failed: {exc}") from exc
        if resp.status_code == 401: raise AuthError("Invalid Amadeus credentials")
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.monotonic() + data.get("expires_in", 1799)
        return self._token

    def validate_credentials(self) -> bool:
        try:
            self._get_token()
            return True
        except Exception:
            return False

    def search_flights(
        self, origin: str, destination: str, departure_date: str,
        return_date: str | None = None, adults: int = 1, children: int = 0,
        cabin_class: str = "ECONOMY", currency: str = "EUR", max_results: int = 10,
    ) -> SearchResult:
        start = time.perf_counter()
        token = self._get_token()
        params = {
            "originLocationCode": origin.upper(),
            "destinationLocationCode": destination.upper(),
            "departureDate": departure_date,
            "adults": adults, "children": children,
            "travelClass": cabin_class.upper(),
            "currencyCode": currency.upper(),
            "max": max_results,
        }
        if return_date: params["returnDate"] = return_date

        try:
            resp = self._client.get(f"{self._base_url}/v2/shopping/flight-offers",
                                    params=params, headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError as exc:
            raise NetworkError(f"Amadeus request failed: {exc}") from exc

        if resp.status_code == 401: self._token = None; raise AuthError("Amadeus token expired")
        if resp.status_code == 429: raise RateLimitError("Amadeus rate limit exceeded")
        if resp.status_code >= 400: raise ProviderError(f"Amadeus error: {resp.text[:500]}")

        data = resp.json().get("data", [])
        if not data: raise NoResultsError(f"No flights found {origin} → {destination}")

        offers = [o for o in [self._parse_offer(r, currency) for r in data[:max_results]] if o]
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
            price_data = raw.get("price", {})
            amount = float(price_data.get("total", 0))
            curr = price_data.get("currency", currency)
            validating = raw.get("validatingAirlineCodes", [""])
            airline_code = validating[0] if validating else ""
            segments = []
            total_stops = 0
            total_duration = ""
            for itin in raw.get("itineraries", []):
                total_duration = itin.get("duration", "")
                for seg in itin.get("segments", []):
                    dep = seg.get("departure", {}); arr = seg.get("arrival", {})
                    carrier = seg.get("carrierCode", "")
                    segments.append(FlightSegment(
                        departure_airport=dep.get("iataCode", ""), departure_time=dep.get("at", ""),
                        arrival_airport=arr.get("iataCode", ""), arrival_time=arr.get("at", ""),
                        airline=carrier, airline_name=self._AIRLINE_NAMES.get(carrier, carrier),
                        flight_number=f"{carrier}{seg.get('number', '')}",
                        duration=seg.get("duration", ""), aircraft=seg.get("aircraft", {}).get("code"),
                    ))
                total_stops += max(0, len(itin.get("segments", [])) - 1)
            return FlightOffer(
                id=raw.get("id", ""), price=amount, currency=curr,
                airline=airline_code, airline_name=self._AIRLINE_NAMES.get(airline_code, airline_code),
                segments=segments, total_duration=total_duration, stops=total_stops,
                cabin_class="ECONOMY", source="amadeus", deep_link=None,
                last_ticketing_date=raw.get("lastTicketingDate"),
                bookable_seats=raw.get("numberOfBookableSeats"),
            )
        except Exception as exc:
            logger.warning("Failed to parse Amadeus offer: %s", exc)
            return None

    _AIRLINE_NAMES = {
        "AY": "Finnair", "BA": "British Airways", "AF": "Air France",
        "LH": "Lufthansa", "KL": "KLM", "TK": "Turkish Airlines",
        "EK": "Emirates", "QR": "Qatar Airways", "AA": "American Airlines",
        "DL": "Delta", "UA": "United", "VS": "Virgin Atlantic",
        "IB": "Iberia", "AZ": "ITA", "OS": "Austrian", "SK": "SAS",
        "DY": "Norwegian", "FR": "Ryanair", "U2": "easyJet",
        "LX": "SWISS", "SN": "Brussels", "LO": "LOT", "PC": "Pegasus",
        "6E": "IndiGo", "AI": "Air India", "SQ": "Singapore",
        "NH": "ANA", "JL": "JAL", "KE": "Korean Air",
    }

    def health_check(self) -> dict[str, Any]:
        healthy = self.validate_credentials()
        return {"provider": self.info.slug, "healthy": healthy, "deprecated": True,
                "sunset_date": "2026-07-17",
                "message": "⚠️ Amadeus decommissioning July 17, 2026. Migrate to Duffel." if healthy else "Invalid credentials"}
