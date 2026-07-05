"""Abstract base class for all flight data providers.

All flight search providers must implement the :class:`FlightProvider`
interface.  This ensures the rest of the application (search engine, UI)
works identically regardless of which provider is active.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """Base exception for all provider errors."""
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class AuthError(ProviderError):
    """Raised when authentication fails."""


class RateLimitError(ProviderError):
    """Raised when rate limit is exceeded."""


class NoResultsError(ProviderError):
    """Raised when no flights are found."""


class ValidationError(ProviderError):
    """Raised when parameters are invalid."""


class NetworkError(ProviderError):
    """Raised when a network request fails."""


@dataclass
class FlightSegment:
    """A single flight segment."""
    departure_airport: str
    departure_time: str
    arrival_airport: str
    arrival_time: str
    airline: str
    airline_name: str
    flight_number: str
    duration: str
    aircraft: str | None = None


@dataclass
class FlightOffer:
    """A single flight offer from any provider."""
    id: str
    price: float
    currency: str
    airline: str
    airline_name: str
    segments: list[FlightSegment]
    total_duration: str
    stops: int
    cabin_class: str
    source: str
    deep_link: str | None = None
    last_ticketing_date: str | None = None
    bookable_seats: int | None = None


@dataclass
class SearchResult:
    """Aggregated result from a provider search."""
    offers: list[FlightOffer]
    total_offers: int
    cheapest_price: float
    average_price: float
    most_expensive_price: float
    search_duration_seconds: float
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ProviderInfo:
    """Metadata about a flight provider."""
    name: str
    slug: str
    description: str
    requires_api_key: bool
    api_key_url: str
    free_tier: str
    rate_limit: str
    best_for: str
    supports_pos_comparison: bool
    status: str  # "active", "deprecated", "limited"


class FlightProvider(ABC):
    """Abstract base class that all flight providers must implement."""

    @property
    @abstractmethod
    def info(self) -> ProviderInfo:
        """Return metadata about this provider."""

    @abstractmethod
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
        max_results: int = 10,
    ) -> SearchResult:
        """Search for flights."""

    @abstractmethod
    def validate_credentials(self) -> bool:
        """Check if the provider's credentials/API key are valid."""

    def health_check(self) -> dict[str, Any]:
        """Return provider health status. Override if needed."""
        return {"provider": self.info.slug, "healthy": self.validate_credentials()}
