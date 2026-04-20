"""HTTP client for Karbon API v3.

Authentication headers required:
- Authorization: Bearer <token>
- AccessKey: <tenant access key>

Base URL (production): https://api.karbonhq.com"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from .exceptions import KarbonAPIError


DEFAULT_BASE_URL = "https://api.karbonhq.com"


@dataclass
class KarbonClient:
    """Minimal Karbon API client with retry/backoff and OData-friendly requests."""

    access_key: str
    bearer_token: str
    base_url: str = DEFAULT_BASE_URL
    timeout: int = 60
    max_retries: int = 3
    backoff_seconds: float = 1.0

    def headers(self) -> Dict[str, str]:
        """Return required headers for Karbon API."""
        return {
            "AccessKey": self.access_key,
            "Authorization": f"Bearer {self.bearer_token}",
            "Accept": "application/json",
        }

    def request(self, method: str, url: str, *, params: Optional[Dict[str, Any]] = None, json: Any = None) -> Dict[str, Any]:
        """Send an HTTP request and return parsed JSON.

        Retries on 429 and common transient 5xx responses.
        Raises KarbonAPIError for non-2xx responses.
        """
        for attempt in range(1, self.max_retries + 1):
            resp = requests.request(
                method,
                url,
                headers=self.headers(),
                params=params,
                json=json,
                timeout=self.timeout,
            )

            if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                time.sleep(self.backoff_seconds * attempt)
                continue

            if not resp.ok:
                msg = None
                try:
                    payload = resp.json()
                    msg = payload.get("message") or payload.get("error") or str(payload)
                except Exception:
                    pass
                raise KarbonAPIError(resp.status_code, msg or resp.reason, response_text=resp.text)

            # Some endpoints may return empty body (204).
            if resp.status_code == 204 or not resp.text.strip():
                return {}
            return resp.json()

        # Should never get here
        raise KarbonAPIError(0, "Request failed after retries")

    def url(self, path: str) -> str:
        """Join base_url and a path like '/v3/WorkItems'."""
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
