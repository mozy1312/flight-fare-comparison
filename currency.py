"""Currency conversion and formatting utilities.

Exchange rates fetched from exchangerate-api.com free endpoint.
All conversions normalise to EUR as the comparison base.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict

import requests

logger = logging.getLogger(__name__)

_EXCHANGE_API_URL: str = "https://api.exchangerate-api.com/v4/latest/{base}"
_CACHE_TTL_SECONDS: int = 3600
_BASE_CURRENCY: str = "EUR"

_FALLBACK_RATES: Dict[str, float] = {
    "EUR": 1.0, "USD": 1.08, "TRY": 34.5, "INR": 90.2,
    "BRL": 5.35, "ARS": 890.0, "PLN": 4.32, "HUF": 395.0,
    "RON": 4.97, "BGN": 1.96, "MYR": 5.12, "THB": 39.4,
    "IDR": 17250.0, "PHP": 60.8, "EGP": 51.2, "AED": 3.97,
    "GBP": 0.85, "CHF": 0.94, "CAD": 1.47, "AUD": 1.65,
    "JPY": 162.0, "CNY": 7.85, "SEK": 11.5, "NOK": 11.8,
    "DKK": 7.46, "SGD": 1.46, "NZD": 1.78, "KRW": 1440.0,
    "MXN": 18.2, "ZAR": 20.1,
}

_cache: Dict[str, float] = {}
_cache_timestamp: float = 0.0
_lock = threading.Lock()


class CurrencyError(Exception):
    """Raised when a currency operation cannot be completed."""


def _is_cache_fresh() -> bool:
    return (time.time() - _cache_timestamp) < _CACHE_TTL_SECONDS


def _fetch_from_api(base: str = "EUR") -> Dict[str, float]:
    url = _EXCHANGE_API_URL.format(base=base.upper())
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        rates = data.get("rates", {})
        if not rates:
            raise CurrencyError("API response contained no rates")
        return rates
    except requests.RequestException as exc:
        raise CurrencyError(f"Failed to fetch exchange rates: {exc}") from exc


def load_exchange_rates(force_refresh: bool = False) -> Dict[str, float]:
    """Return cached exchange rates, refreshing from API if stale."""
    global _cache, _cache_timestamp
    with _lock:
        if not force_refresh and _cache and _is_cache_fresh():
            return dict(_cache)
    try:
        rates = _fetch_from_api(_BASE_CURRENCY)
        logger.info("Loaded fresh exchange rates from API (%d currencies)", len(rates))
    except CurrencyError as exc:
        logger.warning("Exchange-rate API failed (%s); using fallback rates", exc)
        rates = dict(_FALLBACK_RATES)
    with _lock:
        _cache = rates
        _cache_timestamp = time.time()
        return dict(_cache)


def get_exchange_rate(from_currency: str, to_currency: str = _BASE_CURRENCY) -> float:
    """Get exchange rate from one currency to another."""
    from_upper = from_currency.upper()
    to_upper = to_currency.upper()
    rates = load_exchange_rates()
    if from_upper == to_upper:
        return 1.0
    if from_upper not in rates:
        raise CurrencyError(f"Unknown currency: {from_upper}")
    if to_upper not in rates:
        raise CurrencyError(f"Unknown currency: {to_upper}")
    return rates[to_upper] / rates[from_upper]


def convert_to_eur(amount: float, from_currency: str) -> float:
    """Convert amount from a currency to EUR."""
    if amount < 0:
        raise ValueError(f"Amount cannot be negative: {amount}")
    if from_currency.upper() == _BASE_CURRENCY:
        return round(amount, 2)
    rate = get_exchange_rate(from_currency, _BASE_CURRENCY)
    return round(amount * rate, 2)


def format_currency(amount: float, currency: str = _BASE_CURRENCY) -> str:
    """Format amount as a human-readable currency string."""
    code = currency.upper()
    _SYMBOLS: Dict[str, str] = {
        "EUR": "\u20ac", "USD": "$", "GBP": "\u00a3", "TRY": "\u20ba",
        "INR": "\u20b9", "BRL": "R$", "PLN": "z\u0142", "HUF": "Ft",
        "RON": "lei", "THB": "\u0e3f", "IDR": "Rp", "PHP": "\u20b1",
        "EGP": "\u00a3", "AED": "dh", "MYR": "RM",
    }
    try:
        from babel.numbers import format_currency as _babel_format
        for locale in ("en_US", "en_GB", "de_DE", "en"):
            try:
                return str(_babel_format(amount, code, locale=locale))
            except Exception:
                continue
    except ImportError:
        pass
    symbol = _SYMBOLS.get(code, code)
    return f"{symbol}{amount:,.2f}"
