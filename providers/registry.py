"""Provider registry — factory for creating flight provider instances.

Maps provider slugs to their concrete implementations and handles
instantiation with the correct credentials from the environment.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from providers.amadeus_provider import AmadeusProvider
from providers.base import FlightProvider, ProviderInfo
from providers.duffel_provider import DuffelProvider
from providers.flightapi_provider import FlightAPIProvider
from providers.mock_provider import MockProvider
from providers.travelpayouts_provider import TravelpayoutsProvider

logger = logging.getLogger(__name__)

_PROVIDER_MAP: dict[str, type[FlightProvider]] = {
    "duffel": DuffelProvider,
    "amadeus": AmadeusProvider,
    "flightapi": FlightAPIProvider,
    "travelpayouts": TravelpayoutsProvider,
    "mock": MockProvider,
}

_PROVIDER_KEYS: dict[str, dict[str, str]] = {
    "duffel": {"env": "DUFFEL_API_KEY", "extra_envs": {"DUFFEL_TEST_MODE": "test_mode"}},
    "amadeus": {"env": "AMADEUS_API_KEY", "extra_envs": {"AMADEUS_API_SECRET": "api_secret", "AMADEUS_TEST_MODE": "test_mode"}},
    "flightapi": {"env": "FLIGHTAPI_KEY"},
    "travelpayouts": {"env": "TRAVELPAYOUTS_TOKEN"},
    "mock": {"env": ""},
}


def get_provider(slug: str | None = None, **overrides: Any) -> FlightProvider:
    """Create a provider instance by slug.

    Parameters
    ----------
    slug: Provider slug (e.g. ``"duffel"``, ``"mock"``).
        When *None*, reads ``FLIGHT_PROVIDER`` env var or defaults to ``"duffel"``.
    **overrides: Override credential values (e.g. ``api_key="..."``).

    Returns
    -------
    FlightProvider — configured and ready to use.

    Raises
    ------
    KeyError — if slug is unknown.
    ValueError — if required credentials are missing.
    """
    if slug is None:
        slug = os.getenv("FLIGHT_PROVIDER", "duffel").lower().strip()

    if slug not in _PROVIDER_MAP:
        available = ", ".join(sorted(_PROVIDER_MAP.keys()))
        raise KeyError(f"Unknown provider '{slug}'. Available: {available}")

    cls = _PROVIDER_MAP[slug]
    key_config = _PROVIDER_KEYS[slug]

    kwargs: dict[str, Any] = dict(overrides)

    # Read credentials from environment
    env_key = key_config.get("env", "")
    if env_key:
        value = os.getenv(env_key, "").strip()
        if not value and slug != "mock":
            alt_envs = [f"{slug.upper()}_API_KEY", f"{slug.upper()}_TOKEN", f"{slug.upper()}_KEY"]
            for alt in alt_envs:
                value = os.getenv(alt, "").strip()
                if value:
                    break
        if value:
            param_name = "api_key" if "api_key" in cls.__init__.__code__.co_varnames else "token"
            if param_name in cls.__init__.__code__.co_varnames:
                kwargs.setdefault(param_name, value)
            elif "api_key" in cls.__init__.__code__.co_varnames:
                kwargs.setdefault("api_key", value)

    # Read extra envs
    for env_var, param in key_config.get("extra_envs", {}).items():
        env_value = os.getenv(env_var, "").strip()
        if env_value:
            if param == "test_mode":
                kwargs.setdefault(param, env_value.lower() in ("1", "true", "yes"))
            elif param == "api_secret":
                kwargs.setdefault(param, env_value)

    try:
        instance = cls(**kwargs)
    except TypeError as exc:
        if "missing" in str(exc).lower():
            raise ValueError(
                f"Provider '{slug}' requires credentials that were not provided. "
                f"Set the environment variables listed in .env.example or pass them as kwargs."
            ) from exc
        raise

    logger.info("Flight provider initialized: %s", slug)
    return instance


def list_providers() -> list[ProviderInfo]:
    """Return metadata for all available providers (without instantiating)."""
    infos: list[ProviderInfo] = []
    for slug, cls in _PROVIDER_MAP.items():
        try:
            if slug == "mock":
                info = cls().info
            else:
                sig = cls.__init__.__code__.co_varnames
                if "api_key" in sig:
                    info = cls(api_key="").info
                elif "token" in sig:
                    info = cls(token="").info
                else:
                    info = cls().info
            infos.append(info)
        except Exception:
            infos.append(ProviderInfo(
                name=slug.title(), slug=slug, description="",
                requires_api_key=True, api_key_url="",
                free_tier="", rate_limit="", best_for="",
                supports_pos_comparison=False, status="unknown",
            ))
    return infos


def get_provider_info(slug: str) -> ProviderInfo:
    """Return metadata for a specific provider."""
    providers = list_providers()
    for p in providers:
        if p.slug == slug:
            return p
    raise KeyError(f"Unknown provider: {slug}")


def auto_select_provider() -> FlightProvider:
    """Auto-select the best available provider based on configured credentials."""
    explicit = os.getenv("FLIGHT_PROVIDER", "").strip().lower()
    if explicit:
        try:
            return get_provider(explicit)
        except (KeyError, ValueError):
            pass

    for slug in ["duffel", "amadeus", "flightapi", "travelpayouts"]:
        try:
            provider = get_provider(slug)
            if provider.validate_credentials():
                logger.info("Auto-selected provider: %s", slug)
                return provider
        except Exception:
            continue

    logger.info("No real provider credentials found — using demo mode")
    return get_provider("mock")
