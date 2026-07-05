"""Amadeus API client with authentication, error handling, and retries.

This module provides a production-ready HTTP client for the Amadeus
Self-Service APIs.  It handles OAuth2 authentication, automatic token
refresh, rate-limit backoff, and request retries with exponential backoff.

Example::

    client = AmadeusClient(api_key="...", api_secret="...", test_mode=True)
    offers = client.search_flights(
        origin="HEL", destination="LHR",
        departure_date="2025-07-15", adults=1,
    )
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PRODUCTION_BASE_URL = "https://api.amadeus.com"
TEST_BASE_URL = "https://test.api.amadeus.com"
AUTH_ENDPOINT = "/v1/security/oauth2/token"
FLIGHT_OFFERS_ENDPOINT = "/v2/shopping/flight-offers"
AIRPORT_SEARCH_ENDPOINT = "/v1/reference-data/locations"

DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30.0
BACKOFF_BASE_DELAY = 1.0


class APIError(Exception):
    """Base exception for all Amadeus API errors."""
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthError(APIError):
    """Raised when authentication fails."""


class RateLimitError(APIError):
    """Raised when the API rate limit is exceeded (HTTP 429)."""


class TimeoutError(APIError):
    """Raised when a request times out after all retries."""


class ValidationError(APIError):
    """Raised when request parameters fail validation."""


class NoResultsError(APIError):
    """Raised when the API returns no results for a valid query."""


class AmadeusClient:
    """Production-ready Amadeus API client.

    Parameters
    ----------
    api_key:
        Amadeus API key (consumer key).
    api_secret:
        Amadeus API secret (consumer secret).
    test_mode:
        When *True* requests are sent to the Amadeus test environment.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        test_mode: bool = False,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = TEST_BASE_URL if test_mode else PRODUCTION_BASE_URL
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

        logger.debug(
            "AmadeusClient initialised (test_mode=%s, base_url=%s)",
            test_mode,
            self._base_url,
        )

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str | None = None,
        adults: int = 1,
        children: int = 0,
        cabin_class: str = "ECONOMY",
        currency: str = "EUR",
        pos_code: str | None = None,
        max_results: int = 10,
    ) -> list[dict]:
        """Search flights via the Amadeus Flight Offers Search API v2.

        Parameters
        ----------
        origin:
            IATA airport code for the departure location (e.g. ``"HEL"``).
        destination:
            IATA airport code for the arrival location (e.g. ``"LHR"``).
        departure_date:
            Departure date in ``YYYY-MM-DD`` format.
        return_date:
            Return date in ``YYYY-MM-DD`` format.  Omit for one-way trips.
        adults:
            Number of adult passengers (1-9).
        children:
            Number of child passengers (0-9).
        cabin_class:
            Cabin class — one of ``ECONOMY``, ``PREMIUM_ECONOMY``, ``BUSINESS``, ``FIRST``.
        currency:
            Three-letter ISO currency code for pricing (e.g. ``"EUR"``).
        pos_code:
            Optional point-of-sale country code.
        max_results:
            Maximum number of flight offers to return (1-250).

        Returns
        -------
        list[dict]
            Raw offer dictionaries from the Amadeus API.

        Raises
        ------
        ValidationError
            When input parameters are invalid.
        AuthError
            When authentication fails.
        RateLimitError
            When the API rate limit is exceeded.
        TimeoutError
            When the request times out after all retries.
        APIError
            For any other API failure.
        """
        if not origin or not destination:
            raise ValidationError("Origin and destination are required")
        if len(origin) != 3 or len(destination) != 3:
            raise ValidationError(
                f"IATA codes must be 3 letters, got origin={origin!r} "
                f"destination={destination!r}"
            )
        if not (1 <= adults <= 9):
            raise ValidationError(f"adults must be 1-9, got {adults}")
        if not (0 <= children <= 9):
            raise ValidationError(f"children must be 0-9, got {children}")

        params: dict[str, Any] = {
            "originLocationCode": origin.upper(),
            "destinationLocationCode": destination.upper(),
            "departureDate": departure_date,
            "adults": adults,
            "children": children,
            "travelClass": cabin_class.upper(),
            "currencyCode": currency.upper(),
            "max": max_results,
        }

        if return_date:
            params["returnDate"] = return_date

        if pos_code:
            logger.debug("POS code %s provided (using currency %s for pricing)", pos_code, currency)

        logger.info(
            "Searching flights: %s -> %s on %s (class=%s, currency=%s, max=%d)",
            origin.upper(), destination.upper(), departure_date,
            cabin_class, currency, max_results,
        )

        data = self._make_request("GET", FLIGHT_OFFERS_ENDPOINT, params=params)
        offers = data.get("data", [])

        if not offers:
            logger.info("No flight offers found for the given criteria")
            raise NoResultsError(
                f"No flights found from {origin} to {destination} on {departure_date}"
            )

        logger.info("Retrieved %d flight offers", len(offers))
        return offers

    def get_airport_autocomplete(self, keyword: str) -> list[dict]:
        """Search airports and cities for autocomplete suggestions.

        Calls the Amadeus Airport & City Search API.

        Parameters
        ----------
        keyword:
            Search term — can be a city name, airport code, or partial text.

        Returns
        -------
        list[dict]
            Matching airport/city entries from the API.

        Raises
        ------
        ValidationError
            When the keyword is empty.
        APIError
            On API failure.
        """
        keyword = keyword.strip()
        if not keyword:
            raise ValidationError("Keyword cannot be empty")

        params: dict[str, Any] = {
            "keyword": keyword,
            "subType": "AIRPORT,CITY",
            "page[limit]": 10,
        }

        logger.debug("Airport autocomplete search: keyword=%r", keyword)
        data = self._make_request("GET", AIRPORT_SEARCH_ENDPOINT, params=params)
        results = data.get("data", [])
        logger.debug("Found %d autocomplete results for %r", len(results), keyword)
        return results

    def _get_auth_token(self) -> str:
        """Obtain (or reuse) an OAuth2 bearer token.

        Tokens are cached in-memory until 60 seconds before their
        advertised expiry to avoid race conditions.

        Returns
        -------
        str
            The bearer token string.

        Raises
        ------
        AuthError
            When the credentials are rejected by the Amadeus auth server.
        """
        if self._access_token and time.monotonic() < (self._token_expires_at - 60):
            logger.debug("Reusing cached access token")
            return self._access_token

        logger.debug("Requesting new OAuth2 token from %s", AUTH_ENDPOINT)

        try:
            response = httpx.post(
                f"{self._base_url}{AUTH_ENDPOINT}",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._api_key,
                    "client_secret": self._api_secret,
                },
                timeout=DEFAULT_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            logger.error("Network error during authentication: %s", exc)
            raise AuthError(f"Failed to connect to auth server: {exc}") from exc

        if response.status_code == 401:
            logger.error("Authentication failed — invalid API credentials")
            raise AuthError("Invalid Amadeus API credentials (HTTP 401)", status_code=401)

        response.raise_for_status()
        token_data = response.json()

        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 1799)
        self._token_expires_at = time.monotonic() + expires_in

        logger.debug("Obtained new token (expires_in=%ds)", expires_in)
        return self._access_token

    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict:
        """Execute an HTTP request against the Amadeus API with retries.

        Handles authentication, timeout retries with exponential backoff,
        rate-limit detection, and token refresh on 401.

        Parameters
        ----------
        method:
            HTTP method — ``"GET"`` or ``"POST"``.
        endpoint:
            API endpoint path.
        **kwargs:
            Extra arguments forwarded to ``httpx.request``.

        Returns
        -------
        dict
            Parsed JSON response body.

        Raises
        ------
        AuthError
            On authentication failure after token refresh attempt.
        RateLimitError
            On persistent rate-limiting (HTTP 429).
        TimeoutError
            After exhausting all retry attempts.
        APIError
            For any other unrecoverable API error.
        """
        token = self._get_auth_token()
        url = f"{self._base_url}{endpoint}"
        headers: dict[str, str] = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }

        delay = BACKOFF_BASE_DELAY

        for attempt in range(1, DEFAULT_MAX_RETRIES + 1):
            logger.debug("API request %s %s (attempt %d/%d)", method.upper(), endpoint, attempt, DEFAULT_MAX_RETRIES)

            try:
                with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                    response = client.request(
                        method=method.upper(),
                        url=url,
                        headers=headers,
                        **kwargs,
                    )

            except httpx.TimeoutException as exc:
                logger.warning("Request timeout on attempt %d/%d", attempt, DEFAULT_MAX_RETRIES)
                if attempt < DEFAULT_MAX_RETRIES:
                    time.sleep(delay)
                    delay *= 2
                    continue
                logger.error("Request timed out after %d attempts", DEFAULT_MAX_RETRIES)
                raise TimeoutError(
                    f"Request to {endpoint} timed out after {DEFAULT_MAX_RETRIES} retries"
                ) from exc

            except httpx.HTTPError as exc:
                logger.warning("Network error on attempt %d/%d: %s", attempt, DEFAULT_MAX_RETRIES, exc)
                if attempt < DEFAULT_MAX_RETRIES:
                    time.sleep(delay)
                    delay *= 2
                    continue
                logger.error("Network error after %d attempts: %s", DEFAULT_MAX_RETRIES, exc)
                raise APIError(f"Network error: {exc}") from exc

            if response.status_code == 200:
                logger.debug("Request successful (%s %s)", method.upper(), endpoint)
                return response.json()

            if response.status_code == 204:
                return {}

            if response.status_code == 401:
                logger.warning("Received HTTP 401 — refreshing token")
                try:
                    self._access_token = None
                    self._token_expires_at = 0.0
                    new_token = self._get_auth_token()
                    headers["Authorization"] = f"Bearer {new_token}"
                    continue
                except AuthError:
                    logger.error("Token refresh failed")
                    raise AuthError("Authentication failed after token refresh", status_code=401)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_time = float(retry_after) if retry_after else delay
                logger.warning("Rate limited (HTTP 429) — Retry-After=%s", retry_after)
                if attempt < DEFAULT_MAX_RETRIES:
                    time.sleep(wait_time)
                    delay *= 2
                    continue
                raise RateLimitError(
                    f"Rate limit exceeded after {DEFAULT_MAX_RETRIES} retries",
                    status_code=429,
                )

            body = response.text[:500]
            logger.error("HTTP %d on %s %s: %s", response.status_code, method.upper(), endpoint, body)
            raise APIError(f"HTTP {response.status_code}: {body}", status_code=response.status_code)

        raise APIError("Unexpected end of retry loop")
