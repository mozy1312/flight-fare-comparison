"""Pydantic v2 data models for the Flight Fare Comparison application.

Provides strict, validated models for flight segments, offers, search queries
and aggregated results.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_AIRPORT_RE = re.compile(r"^[A-Z]{3}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FlightSegment(BaseModel):
    """A single flight segment (one leg of a journey)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    departure_airport: str = Field(..., min_length=3, max_length=3)
    departure_time: str
    arrival_airport: str = Field(..., min_length=3, max_length=3)
    arrival_time: str
    airline: str = Field(..., min_length=2, max_length=3)
    airline_name: str
    flight_number: str
    duration: str
    aircraft: str | None = None

    @field_validator("departure_airport", "arrival_airport")
    @classmethod
    def _validate_airport(cls, value: str) -> str:
        if not _AIRPORT_RE.match(value):
            raise ValueError(f"Airport code must be 3 uppercase letters, got: {value!r}")
        return value


class FlightOffer(BaseModel):
    """A single flight offer returned by the search pipeline."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    price_eur: float = Field(..., ge=0)
    price_original: float = Field(..., ge=0)
    original_currency: str
    airline: str
    airline_name: str
    segments: list[FlightSegment]
    total_duration: str
    stops: int = Field(..., ge=0)
    cabin_class: str
    pos_country: str
    pos_code: str
    source: str
    last_ticketing_date: str | None = None
    bookable_seats: int | None = Field(None, ge=0)

    @field_validator("cabin_class")
    @classmethod
    def _validate_cabin(cls, value: str) -> str:
        allowed = {"ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"}
        if value.upper() not in allowed:
            raise ValueError(f"cabin_class must be one of {allowed}, got: {value!r}")
        return value.upper()


class SearchQuery(BaseModel):
    """User-supplied search parameters."""

    model_config = ConfigDict(str_strip_whitespace=True)

    origin: str = Field(..., min_length=3, max_length=3)
    destination: str = Field(..., min_length=3, max_length=3)
    departure_date: str
    return_date: str | None = None
    adults: int = Field(default=1, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=9)
    cabin_class: str = "ECONOMY"
    trip_type: str = "one_way"
    direct_only: bool = False
    max_results: int = Field(default=10, ge=5, le=50)

    @field_validator("origin", "destination")
    @classmethod
    def _validate_airport(cls, value: str) -> str:
        if not _AIRPORT_RE.match(value):
            raise ValueError(f"Airport code must be 3 uppercase letters, got: {value!r}")
        return value

    @field_validator("departure_date", "return_date")
    @classmethod
    def _validate_date(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not _DATE_RE.match(value):
            raise ValueError(f"Date must be in YYYY-MM-DD format, got: {value!r}")
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"Invalid calendar date: {value!r}") from exc
        if parsed < date.today():
            raise ValueError(f"Date must not be in the past: {value} (today: {date.today()})")
        return value

    @field_validator("cabin_class")
    @classmethod
    def _validate_cabin(cls, value: str) -> str:
        allowed = {"ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"}
        if value.upper() not in allowed:
            raise ValueError(f"cabin_class must be one of {allowed}, got: {value!r}")
        return value.upper()

    @field_validator("trip_type")
    @classmethod
    def _validate_trip_type(cls, value: str) -> str:
        normalised = value.lower().replace("-", "_").strip()
        if normalised not in {"one_way", "round_trip"}:
            raise ValueError(f"trip_type must be 'one_way' or 'round_trip', got: {value!r}")
        return normalised


class SearchResult(BaseModel):
    """Aggregated result of a multi-POS flight search."""

    model_config = ConfigDict(str_strip_whitespace=True)

    search_id: str
    query: SearchQuery
    offers: list[FlightOffer]
    countries_searched: int = Field(..., ge=0)
    total_offers: int = Field(..., ge=0)
    cheapest_price: float = Field(..., ge=0)
    average_price: float = Field(..., ge=0)
    most_expensive_price: float = Field(..., ge=0)
    search_duration_seconds: float = Field(..., ge=0)
    generated_at: str
