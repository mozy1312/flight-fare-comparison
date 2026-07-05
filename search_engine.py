"""Multi-POS flight search orchestration using provider-agnostic architecture.

Queries any configured flight provider across multiple Point-of-Sale countries,
converts all prices to EUR, and aggregates results.

Example::

    from config import load_config
    from search_engine import FlightSearchEngine

    config = load_config()
    engine = FlightSearchEngine(config)
    result = engine.search_multi_pos(query=SearchQuery(...))
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from config import AppConfig, get_provider_config
from currency import convert_to_eur
from models import FlightOffer, FlightSegment, SearchQuery, SearchResult
from proxy_manager import CountryConfig, get_enabled_countries
from providers import FlightProvider, ProviderError, get_provider
from utils import format_duration, generate_search_id

logger = logging.getLogger(__name__)


class FlightSearchEngine:
    """Orchestrate multi-POS flight searches with any provider.

    Parameters
    ----------
    config: Application configuration.
    provider: Optional pre-configured provider instance.
    """

    def __init__(self, config: AppConfig, provider: FlightProvider | None = None) -> None:
        self._config = config

        if provider is not None:
            self._provider = provider
        elif config.has_any_credentials or config.provider != "mock":
            try:
                kwargs = get_provider_config(config)
                self._provider = get_provider(config.provider, **kwargs)
            except Exception as exc:
                logger.warning("Failed to initialize %s provider: %s. Using demo mode.", config.provider, exc)
                self._provider = get_provider("mock")
        else:
            logger.info("No credentials configured — using demo mode")
            self._provider = get_provider("mock")

        logger.debug("Search engine using provider: %s", self._provider.info.slug)

    @property
    def provider_info(self) -> dict[str, Any]:
        """Return info about the active provider."""
        info = self._provider.info
        return {
            "name": info.name, "slug": info.slug,
            "description": info.description, "status": info.status,
            "requires_api_key": info.requires_api_key,
            "supports_pos_comparison": info.supports_pos_comparison,
        }

    def search_multi_pos(
        self, query: SearchQuery,
        countries: list[CountryConfig] | None = None,
        progress_callback: Callable | None = None,
    ) -> SearchResult:
        """Search flights across multiple POS countries."""
        start = time.perf_counter()
        if countries is None:
            countries = get_enabled_countries()

        if not self._provider.info.supports_pos_comparison:
            logger.info("Provider %s doesn't support multi-POS; running single search", self._provider.info.slug)
            try:
                result = self._search_single(query)
            except Exception as exc:
                logger.error("Provider search failed: %s", exc)
                self._provider = get_provider("mock")
                result = self._search_single(query)
            if progress_callback:
                progress_callback(1, 1, self._provider.info.name)
            return result

        total = len(countries)
        logger.info("Multi-POS search: %s → %s across %d countries via %s", query.origin, query.destination, total, self._provider.info.slug)

        all_offers: list[FlightOffer] = []
        searched = 0
        for i, country in enumerate(countries, 1):
            logger.info("[%d/%d] Searching %s (%s)", i, total, country.name, country.currency)
            try:
                country_offers = self._search_single(query, country)
                all_offers.extend(country_offers)
                searched += 1
            except ProviderError as exc:
                logger.error("[%d/%d] %s failed: %s", i, total, country.name, exc)
            except Exception:
                logger.exception("[%d/%d] Unexpected error for %s", i, total, country.name)
            if progress_callback:
                try:
                    progress_callback(i, total, country.name)
                except Exception:
                    pass

        duration = time.perf_counter() - start
        return self._aggregate(all_offers, query, duration, searched)

    def _search_single(self, query: SearchQuery, country: CountryConfig | None = None) -> list[FlightOffer]:
        """Execute a single search, optionally with a specific POS country."""
        currency = country.currency if country else self._config.default_currency
        pos_label = country.name if country else "default"
        result = self._provider.search_flights(
            origin=query.origin, destination=query.destination,
            departure_date=query.departure_date, return_date=query.return_date,
            adults=query.adults, children=query.children,
            cabin_class=query.cabin_class, currency=currency,
            max_results=query.max_results,
        )
        offers = []
        for raw_offer in result.offers:
            parsed = self._normalize_offer(raw_offer, currency, pos_label, country.code if country else "")
            if parsed:
                offers.append(parsed)
        return offers

    def _normalize_offer(self, raw: Any, local_currency: str, pos_country: str, pos_code: str) -> FlightOffer | None:
        """Normalize a provider-specific offer to the unified FlightOffer model."""
        try:
            from providers.base import FlightOffer as POffer, FlightSegment as PSegment

            if isinstance(raw, FlightOffer):
                return raw

            if isinstance(raw, POffer):
                segments = []
                for seg in raw.segments:
                    if isinstance(seg, FlightSegment):
                        segments.append(seg)
                    elif isinstance(seg, PSegment):
                        segments.append(FlightSegment(
                            departure_airport=seg.departure_airport,
                            departure_time=seg.departure_time,
                            arrival_airport=seg.arrival_airport,
                            arrival_time=seg.arrival_time,
                            airline=seg.airline,
                            airline_name=seg.airline_name,
                            flight_number=seg.flight_number,
                            duration=seg.duration,
                            aircraft=seg.aircraft,
                        ))
                price_eur = convert_to_eur(raw.price, local_currency) if raw.currency != "EUR" else raw.price
                return FlightOffer(
                    id=raw.id, price_eur=price_eur, price_original=raw.price,
                    original_currency=raw.currency, airline=raw.airline,
                    airline_name=raw.airline_name, segments=segments,
                    total_duration=raw.total_duration, stops=raw.stops,
                    cabin_class=raw.cabin_class, pos_country=pos_country,
                    pos_code=pos_code, source=raw.source,
                    last_ticketing_date=raw.last_ticketing_date,
                    bookable_seats=raw.bookable_seats,
                )

            if isinstance(raw, dict):
                price = float(raw.get("price", 0))
                curr = raw.get("currency", local_currency)
                price_eur = convert_to_eur(price, curr) if curr != "EUR" else price
                return FlightOffer(
                    id=raw.get("id", ""), price_eur=price_eur,
                    price_original=price, original_currency=curr,
                    airline=raw.get("airline", ""),
                    airline_name=raw.get("airline_name", raw.get("airline", "")),
                    segments=[], total_duration=raw.get("duration", ""),
                    stops=raw.get("stops", 0),
                    cabin_class=raw.get("cabin_class", "ECONOMY"),
                    pos_country=pos_country, pos_code=pos_code,
                    source=raw.get("source", "unknown"),
                )
            return None
        except Exception as exc:
            logger.warning("Failed to normalize offer: %s", exc)
            return None

    def _aggregate(self, offers: list[FlightOffer], query: SearchQuery, duration: float, searched: int) -> SearchResult:
        """Aggregate and sort offers, compute statistics."""
        if not offers:
            return SearchResult(
                search_id=generate_search_id(), query=query, offers=[],
                countries_searched=searched, total_offers=0,
                cheapest_price=0.0, average_price=0.0, most_expensive_price=0.0,
                search_duration_seconds=round(duration, 2),
                generated_at=datetime.now(timezone.utc).isoformat(),
            )
        sorted_offers = sorted(offers, key=lambda o: o.price_eur)
        prices = [o.price_eur for o in sorted_offers]
        return SearchResult(
            search_id=generate_search_id(), query=query, offers=sorted_offers,
            countries_searched=searched, total_offers=len(sorted_offers),
            cheapest_price=prices[0],
            average_price=round(sum(prices) / len(prices), 2),
            most_expensive_price=prices[-1],
            search_duration_seconds=round(duration, 2),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
