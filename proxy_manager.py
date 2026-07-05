"""Country / Point-of-Sale (POS) configuration manager.

Manages a registry of CountryConfig entries for 15 default countries.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Dict

logger = logging.getLogger(__name__)


@dataclass
class CountryConfig:
    """Configuration for a single POS country."""

    name: str
    code: str
    currency: str
    pos_code: str
    proxy_url: str | None
    language: str
    enabled: bool = True


_DEFAULT_COUNTRIES: list[CountryConfig] = [
    CountryConfig("Finland", "FI", "EUR", "FI", None, "en-GB"),
    CountryConfig("Turkey", "TR", "TRY", "TR", None, "tr-TR"),
    CountryConfig("India", "IN", "INR", "IN", None, "en-GB"),
    CountryConfig("Brazil", "BR", "BRL", "BR", None, "pt-BR"),
    CountryConfig("Argentina", "AR", "ARS", "AR", None, "es-AR"),
    CountryConfig("Poland", "PL", "PLN", "PL", None, "pl-PL"),
    CountryConfig("Hungary", "HU", "HUF", "HU", None, "hu-HU"),
    CountryConfig("Romania", "RO", "RON", "RO", None, "ro-RO"),
    CountryConfig("Bulgaria", "BG", "BGN", "BG", None, "bg-BG"),
    CountryConfig("Malaysia", "MY", "MYR", "MY", None, "en-GB"),
    CountryConfig("Thailand", "TH", "THB", "TH", None, "th-TH"),
    CountryConfig("Indonesia", "ID", "IDR", "ID", None, "id-ID"),
    CountryConfig("Philippines", "PH", "PHP", "PH", None, "en-GB"),
    CountryConfig("Egypt", "EG", "EGP", "EG", None, "ar-EG"),
    CountryConfig("UAE", "AE", "AED", "AE", None, "en-GB"),
]

_registry: Dict[str, CountryConfig] = {}
_lock = threading.Lock()


def _ensure_loaded() -> None:
    global _registry
    if not _registry:
        _registry = {c.code.upper(): c for c in _DEFAULT_COUNTRIES}


def get_all_countries() -> list[CountryConfig]:
    _ensure_loaded()
    return list(_registry.values())


def get_enabled_countries() -> list[CountryConfig]:
    _ensure_loaded()
    return [c for c in _registry.values() if c.enabled]


def get_country_by_code(code: str) -> CountryConfig | None:
    _ensure_loaded()
    return _registry.get(code.upper())


def toggle_country(code: str, enabled: bool) -> None:
    _ensure_loaded()
    key = code.upper()
    with _lock:
        if key not in _registry:
            raise KeyError(f"Country code not found: {code!r}")
        _registry[key].enabled = enabled
        logger.info("Country %s %s", key, "enabled" if enabled else "disabled")
