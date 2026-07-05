"""Multi-provider flight search interface.

This package implements a provider-agnostic architecture that allows
the application to switch between multiple flight data sources at runtime.

Supported providers:
    - ``duffel`` — Recommended replacement for Amadeus. Free test mode, 300+ airlines.
    - ``amadeus`` — Legacy provider (decommissioning July 17, 2026).
    - ``flightapi`` — Budget-friendly option (20-100 free calls).
    - ``travelpayouts`` — Free affiliate data API.
    - ``mock`` — Synthetic demo data (always works, no API key).

Usage::

    from providers import get_provider, FlightProvider

    provider: FlightProvider = get_provider("duffel")
    offers = provider.search_flights(origin="HEL", destination="LHR", ...)
"""

from __future__ import annotations

from providers.base import FlightProvider, FlightOffer, SearchResult, ProviderError
from providers.registry import get_provider, list_providers, get_provider_info

__all__ = [
    "FlightProvider",
    "FlightOffer",
    "SearchResult",
    "ProviderError",
    "get_provider",
    "list_providers",
    "get_provider_info",
]
