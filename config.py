"""Central configuration hub for the Flight Fare Comparison application.

All application settings are loaded from environment variables via a ``.env`` file
and exposed through the :class:`AppConfig` dataclass.

Example::

    from config import load_config
    cfg = load_config()
    print(cfg.default_currency)   # -> "EUR"
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

DEFAULT_CURRENCY: str = "EUR"
DEFAULT_ADULTS: int = 1
DEFAULT_RESULTS_LIMIT: int = 10
API_TIMEOUT: int = 30
CACHE_TTL: int = 300
AMADEUS_BASE_URL: str = "https://api.amadeus.com"
AMADEUS_TEST_URL: str = "https://test.api.amadeus.com"

_ENV_PATH: Path = Path(__file__).resolve().parent / ".env"


class ConfigurationError(Exception):
    """Raised when a required configuration value is missing or invalid."""


@dataclass
class AppConfig:
    """Aggregated application configuration."""

    amadeus_key: str
    amadeus_secret: str
    default_currency: str = DEFAULT_CURRENCY
    api_timeout: int = API_TIMEOUT
    cache_ttl: int = CACHE_TTL
    debug: bool = False
    travelpayouts_token: str | None = None
    aviationstack_key: str | None = None

    def __post_init__(self) -> None:
        if not self.amadeus_key or not self.amadeus_key.strip():
            raise ConfigurationError("AMADEUS_API_KEY is required but missing or empty.")
        if not self.amadeus_secret or not self.amadeus_secret.strip():
            raise ConfigurationError("AMADEUS_API_SECRET is required but missing or empty.")


def load_config(env_path: str | Path | None = None) -> AppConfig:
    """Load and validate application configuration from environment variables."""
    path = Path(env_path) if env_path else _ENV_PATH
    if path.exists():
        load_dotenv(dotenv_path=str(path), override=True)
        logger.debug("Loaded environment variables from %s", path)
    else:
        logger.warning("No .env file found at %s; relying on system env", path)

    def _env(key: str, default: Any = None) -> str | None:
        value = os.getenv(key, default)
        if isinstance(value, str) and not value.strip():
            return None
        return value

    return AppConfig(
        amadeus_key=_env("AMADEUS_API_KEY", ""),
        amadeus_secret=_env("AMADEUS_API_SECRET", ""),
        default_currency=str(_env("DEFAULT_CURRENCY", DEFAULT_CURRENCY)),
        api_timeout=int(_env("API_TIMEOUT", API_TIMEOUT)),
        cache_ttl=int(_env("CACHE_TTL", CACHE_TTL)),
        debug=str(_env("DEBUG", "false")).lower() in ("1", "true", "yes"),
        travelpayouts_token=_env("TRAVELPAYOUTS_TOKEN"),
        aviationstack_key=_env("AVIATIONSTACK_API_KEY"),
    )


def get_amadeus_credentials(config: AppConfig | None = None) -> tuple[str, str]:
    """Return the Amadeus API key and secret as a 2-tuple."""
    cfg = config or load_config()
    return (cfg.amadeus_key, cfg.amadeus_secret)


def get_proxy_config(config: AppConfig | None = None) -> dict[str, Any]:
    """Return proxy-related settings."""
    cfg = config or load_config()
    return {"timeout": cfg.api_timeout, "verify": True, "proxies": {}}
