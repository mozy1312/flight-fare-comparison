"""Multi-POS flight search orchestration and result aggregation.

This module implements the core search engine that queries the Amadeus
API across multiple Point-of-Sale countries, converts all prices to EUR,
and aggregates the results into a unified, sorted response.

Example::

    from config import load_config
    from search_engine import FlightSearchEngine

    config = load_config()
    engine = FlightSearchEngine(config)
    result = engine.search_multi_pos(
        SearchQuery(origin="HEL", destination="LHR", departure_date="2025-07-15")
    )
    for offer in result.offers[:5]:
        print(f"{offer.price_eur:.2f} EUR  {offer.airline_name}")
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from api_client import AmadeusClient, APIError, TimeoutError
from config import AppConfig
from currency import convert_to_eur
from models import FlightOffer, FlightSegment, SearchQuery, SearchResult
from proxy_manager import CountryConfig, get_enabled_countries
from utils import format_duration, generate_search_id

logger = logging.getLogger(__name__)


class FlightSearchEngine:
    """Orchestrate multi-POS flight searches and aggregate results.

    Parameters
    ----------
    config:
        Application configuration (API keys, timeouts, etc.).
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client = AmadeusClient(
            api_key=config.amadeus_key,
            api_secret=config.amadeus_secret,
            test_mode=config.debug,
        )
        logger.debug(
            "FlightSearchEngine initialised (timeout=%ds, debug=%s)",
            config.api_timeout,
            config.debug,
        )

    def search_multi_pos(
        self,
        query: SearchQuery,
        countries: list[CountryConfig] | None = None,
        progress_callback: Callable | None = None,
    ) -> SearchResult:
        """Search flights across multiple POS countries.

        For each enabled country the engine:

        1. Calls Amadeus with the country's local currency.
        2. Parses raw offers into :class:`FlightOffer` objects.
        3. Converts prices to EUR.
        4. Aggregates all offers and sorts by ``price_eur`` ascending.

        If a single-country search fails the error is logged and the
        engine continues with the remaining countries.

        Parameters
        ----------
        query:
            Validated search parameters.
        countries:
            Explicit list of countries to search.  When *None* all
            enabled countries from the proxy manager are used.
        progress_callback:
            Optional callable invoked after each country search completes.

        Returns
        -------
        SearchResult
            Aggregated, sorted search results with price statistics.
        """
        start_time = time.perf_counter()

        if countries is None:
            countries = get_enabled_countries()

        total_countries = len(countries)
        logger.info(
            "Starting multi-POS search: %s -> %s on %s across %d countries",
            query.origin, query.destination, query.departure_date, total_countries,
        )

        all_offers: list[FlightOffer] = []
        countries_searched = 0

        for idx, country in enumerate(countries, start=1):
            logger.info(
                "[%d/%d] Searching POS: %s (%s, currency=%s)",
                idx, total_countries, country.name, country.code, country.currency,
            )

            try:
                country_offers = self._search_single_pos(query, country)
                all_offers.extend(country_offers)
                countries_searched += 1
                logger.info("[%d/%d] %s returned %d offers", idx, total_countries, country.name, len(country_offers))
            except APIError as exc:
                logger.error("[%d/%d] Search failed for %s: %s", idx, total_countries, country.name, exc)
            except Exception as exc:
                logger.exception("[%d/%d] Unexpected error for %s: %s", idx, total_countries, country.name, exc)

            if progress_callback is not None:
                try:
                    progress_callback(idx, total_countries, country.name)
                except Exception:
                    logger.debug("Progress callback raised an exception", exc_info=True)

        duration = time.perf_counter() - start_time
        logger.info(
            "Multi-POS search complete: %d offers from %d/%d countries in %.2fs",
            len(all_offers), countries_searched, total_countries, duration,
        )

        return self._aggregate_results(
            all_offers=all_offers, query=query, duration=duration,
            countries_searched=countries_searched,
        )

    def _search_single_pos(
        self,
        query: SearchQuery,
        country: CountryConfig,
    ) -> list[FlightOffer]:
        """Execute a flight search for a single POS country."""
        logger.debug("Searching single POS: country=%s, currency=%s", country.name, country.currency)

        raw_offers = self._client.search_flights(
            origin=query.origin,
            destination=query.destination,
            departure_date=query.departure_date,
            return_date=query.return_date,
            adults=query.adults,
            children=query.children,
            cabin_class=query.cabin_class,
            currency=country.currency,
            pos_code=country.pos_code,
            max_results=query.max_results,
        )

        offers: list[FlightOffer] = []
        for raw in raw_offers:
            parsed = self._parse_amadeus_offer(raw, country)
            if parsed is not None:
                offers.append(parsed)

        logger.debug("Parsed %d/%d valid offers for %s", len(offers), len(raw_offers), country.name)
        return offers

    def _parse_amadeus_offer(
        self,
        raw_offer: dict[str, Any],
        country: CountryConfig,
    ) -> FlightOffer | None:
        """Convert a raw Amadeus offer dictionary into a :class:`FlightOffer`."""
        try:
            offer_id = raw_offer.get("id", "unknown")

            price_data = raw_offer.get("price", {})
            original_price_str = price_data.get("total", "0")
            original_currency = price_data.get("currency", country.currency)
            original_price = float(original_price_str)
            price_eur = convert_to_eur(original_price, original_currency)

            itineraries = raw_offer.get("itineraries", [])
            segments: list[FlightSegment] = []
            total_stops = 0
            total_duration_iso = ""

            for itinerary in itineraries:
                total_duration_iso = itinerary.get("duration", "")
                raw_segments = itinerary.get("segments", [])

                for seg in raw_segments:
                    departure = seg.get("departure", {})
                    arrival = seg.get("arrival", {})
                    carrier = seg.get("carrierCode", "")
                    seg_duration_iso = seg.get("duration", "")

                    segment = FlightSegment(
                        departure_airport=departure.get("iataCode", ""),
                        departure_time=departure.get("at", ""),
                        arrival_airport=arrival.get("iataCode", ""),
                        arrival_time=arrival.get("at", ""),
                        airline=carrier,
                        airline_name=self._resolve_airline_name(carrier),
                        flight_number=f"{carrier}{seg.get('number', '')}",
                        duration=format_duration(seg_duration_iso),
                        aircraft=seg.get("aircraft", {}).get("code"),
                    )
                    segments.append(segment)

                if len(raw_segments) > 1:
                    total_stops += len(raw_segments) - 1

            if len(itineraries) > 1:
                total_stops = sum(max(0, len(itin.get("segments", [])) - 1) for itin in itineraries)

            validating_airlines = raw_offer.get("validatingAirlineCodes", [])
            primary_airline = validating_airlines[0] if validating_airlines else ""
            if not primary_airline and segments:
                primary_airline = segments[0].airline

            total_duration_human = format_duration(total_duration_iso)
            if not total_duration_human and segments:
                durations = [format_duration(itin.get("duration", "")) for itin in itineraries]
                total_duration_human = " / ".join(d for d in durations if d)

            traveler_pricings = raw_offer.get("travelerPricings", [{}])
            fare_details = traveler_pricings[0].get("fareDetailsBySegment", [{}]) if traveler_pricings else [{}]
            cabin = fare_details[0].get("cabin", "ECONOMY") if fare_details else "ECONOMY"

            return FlightOffer(
                id=offer_id,
                price_eur=price_eur,
                price_original=original_price,
                original_currency=original_currency,
                airline=primary_airline,
                airline_name=self._resolve_airline_name(primary_airline),
                segments=segments,
                total_duration=total_duration_human,
                stops=total_stops,
                cabin_class=cabin,
                pos_country=country.name,
                pos_code=country.code,
                source="amadeus",
                last_ticketing_date=raw_offer.get("lastTicketingDate"),
                bookable_seats=raw_offer.get("numberOfBookableSeats"),
            )

        except Exception as exc:
            offer_id = raw_offer.get("id", "unknown") if isinstance(raw_offer, dict) else "unknown"
            logger.warning("Failed to parse offer %s for %s: %s", offer_id, country.name, exc)
            return None

    def _aggregate_results(
        self,
        all_offers: list[FlightOffer],
        query: SearchQuery,
        duration: float,
        countries_searched: int,
    ) -> SearchResult:
        """Aggregate offers, compute price statistics, and build a :class:`SearchResult`."""
        if not all_offers:
            return SearchResult(
                search_id=generate_search_id(), query=query, offers=[],
                countries_searched=countries_searched, total_offers=0,
                cheapest_price=0.0, average_price=0.0, most_expensive_price=0.0,
                search_duration_seconds=round(duration, 2),
                generated_at=datetime.now(timezone.utc).isoformat(),
            )

        sorted_offers = sorted(all_offers, key=lambda o: o.price_eur)
        prices = [o.price_eur for o in sorted_offers]
        cheapest = prices[0]
        most_expensive = prices[-1]
        average = round(sum(prices) / len(prices), 2)

        return SearchResult(
            search_id=generate_search_id(), query=query, offers=sorted_offers,
            countries_searched=countries_searched, total_offers=len(sorted_offers),
            cheapest_price=cheapest, average_price=average,
            most_expensive_price=most_expensive,
            search_duration_seconds=round(duration, 2),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _resolve_airline_name(carrier_code: str) -> str:
        """Resolve a carrier code to a human-readable airline name."""
        AIRLINE_NAMES: dict[str, str] = {
            "AY": "Finnair", "BA": "British Airways", "AF": "Air France",
            "LH": "Lufthansa", "KL": "KLM", "TK": "Turkish Airlines",
            "EK": "Emirates", "QR": "Qatar Airways", "AA": "American Airlines",
            "DL": "Delta Air Lines", "UA": "United Airlines", "VS": "Virgin Atlantic",
            "EI": "Aer Lingus", "IB": "Iberia", "TP": "TAP Air Portugal",
            "AZ": "ITA Airways", "OS": "Austrian Airlines", "SK": "SAS",
            "DY": "Norwegian", "FR": "Ryanair", "U2": "easyJet",
            "LX": "SWISS", "SN": "Brussels Airlines", "LO": "LOT Polish Airlines",
            "RO": "TAROM", "A3": "Aegean Airlines", "PC": "Pegasus Airlines",
            "6E": "IndiGo", "AI": "Air India", "EY": "Etihad Airways",
            "SQ": "Singapore Airlines", "CX": "Cathay Pacific", "QF": "Qantas",
            "NH": "ANA", "JL": "Japan Airlines", "KE": "Korean Air",
            "OZ": "Asiana Airlines", "HU": "Hainan Airlines", "CA": "Air China",
            "CZ": "China Southern", "MU": "China Eastern",
        }
        return AIRLINE_NAMES.get(carrier_code, carrier_code)
