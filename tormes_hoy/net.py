"""Minimal HTTP helpers on top of the standard library."""

import json
import urllib.request
from typing import Any

USER_AGENT = "tormes-hoy/0.1 (+https://github.com/)"
DEFAULT_TIMEOUT_S = 20


class HttpError(RuntimeError):
    """Raised when a request fails or returns an unusable body."""


def get_bytes(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> tuple[bytes, str | None]:
    """Fetch ``url`` and return its body and declared charset."""
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, **(headers or {})}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset()
            return response.read(), charset
    except OSError as exc:  # URLError, HTTPError and timeouts
        raise HttpError(f"GET {_redact(url)} failed: {exc}") from exc


def get_json(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> Any:
    """Fetch ``url`` and decode it as JSON.

    AEMET serves some payloads as ISO-8859-15 without always declaring it,
    so UTF-8 is tried first and Latin-9 is used as a fallback.
    """
    body, charset = get_bytes(url, headers, timeout)
    for encoding in (charset, "utf-8", "iso-8859-15"):
        if not encoding:
            continue
        try:
            return json.loads(body.decode(encoding))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise HttpError(f"GET {_redact(url)} returned invalid JSON")


def _redact(url: str) -> str:
    """Hide API keys passed as query parameters in error messages."""
    if "apikey=" not in url:
        return url
    head, _, tail = url.partition("apikey=")
    rest = tail.split("&", 1)
    return f"{head}apikey=***" + (f"&{rest[1]}" if len(rest) > 1 else "")
