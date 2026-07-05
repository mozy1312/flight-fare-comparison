"""Shared utilities -- logging, validation, formatting, and retry helpers.
"""

from __future__ import annotations

import functools
import logging
import re
import time
import uuid
from datetime import date, datetime
from typing import Any, Callable, TypeVar

_AIRPORT_RE = re.compile(r"^[A-Z]{3}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)

_F = TypeVar("_F", bound=Callable[..., Any])


class ValidationError(Exception):
    """Raised when an input fails validation."""


class FormatError(Exception):
    """Raised when a value cannot be formatted."""


def setup_logging(debug: bool = False, log_format: str | None = None) -> logging.Logger:
    """Configure structured logging for the application."""
    if log_format is None:
        log_format = "%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s"
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S"))
    root.addHandler(handler)
    if debug:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
    return root


def validate_airport_code(code: str) -> bool:
    """Validate a 3-letter IATA airport code."""
    return bool(_AIRPORT_RE.match(code)) if isinstance(code, str) else False


def validate_date(date_str: str) -> bool:
    """Validate a YYYY-MM-DD date that is not in the past."""
    if not isinstance(date_str, str) or not _DATE_RE.match(date_str):
        return False
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False
    return parsed >= date.today()


def format_duration(duration_iso: str) -> str:
    """Convert ISO-8601 duration (PT8H30M) to human-readable string."""
    match = _ISO_DURATION_RE.match(duration_iso)
    if not match:
        return duration_iso
    gd = match.groupdict(default="0")
    hours = int(gd["hours"]) + int(gd["days"]) * 24
    minutes = int(gd["minutes"])
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    return " ".join(parts) if parts else "0m"


def format_datetime(iso_datetime: str, fmt: str = "%d %b %Y, %H:%M") -> str:
    """Convert ISO-8601 datetime to readable string."""
    try:
        dt_str = iso_datetime.replace("Z", "+00:00")
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.strftime(fmt)
    except (ValueError, TypeError) as exc:
        raise FormatError(f"Invalid ISO datetime: {iso_datetime!r}") from exc


def sanitize_input(value: str) -> str:
    """Strip whitespace and remove dangerous characters."""
    value = str(value).strip()
    cleaned = re.sub(r"[^\w\s\-.,:/()@!?]", "", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[_F], _F]:
    """Decorator for retry with exponential backoff."""
    if max_retries < 1:
        raise ValueError("max_retries must be >= 1")

    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_retries:
                        break
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    time.sleep(delay + (uuid.uuid4().int % 100) / 100.0)
            raise last_exc  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator


def generate_search_id() -> str:
    """Generate a unique search session identifier."""
    return uuid.uuid4().hex
