"""
Files endpoint helpers.

Implements:
- POST /v3/Files (upload and link a file to an entity)

Notes:
- This endpoint uses multipart/form-data and requires:
  - FileName (string)
  - MimeType (string)
  - file (binary)
  - plus at least one association key:
    contact_keys, organization_keys, client_group_keys, workitem_keys, integration_task_key

- We cannot use KarbonClient.request() directly because it currently supports JSON bodies
  (params/json) but not multipart uploads. This module sends the request using requests.post
  while still using KarbonClient.headers() for authentication headers.

Docs base URL (production): https://api.karbonhq.com
"""

from __future__ import annotations

import mimetypes
import os
import time
from typing import Any, Dict, Optional

import requests

from .client import KarbonClient
from .exceptions import KarbonAPIError


_ASSOC_FIELDS = (
    "contact_keys",
    "organization_keys",
    "client_group_keys",
    "workitem_keys",
    "integration_task_key",
)


def upload_file(
    client: KarbonClient,
    file_path: str,
    *,
    file_name: Optional[str] = None,
    mime_type: Optional[str] = None,
    contact_keys: Optional[str] = None,
    organization_keys: Optional[str] = None,
    client_group_keys: Optional[str] = None,
    workitem_keys: Optional[str] = None,
    integration_task_key: Optional[str] = None,
    # allow overriding retry behavior per call (defaults align with KarbonClient semantics)
    max_retries: Optional[int] = None,
    backoff_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """
    POST /v3/Files - Upload and link a file to an entity.

    Parameters
    ----------
    client : KarbonClient
        Authenticated Karbon client (provides headers/base_url/timeout).
    file_path : str
        Local file path to upload.
    file_name : Optional[str]
        Name to store in Karbon (defaults to basename of file_path).
    mime_type : Optional[str]
        MIME type (defaults to mimetypes.guess_type or application/octet-stream).
    contact_keys / organization_keys / client_group_keys / workitem_keys / integration_task_key : Optional[str]
        At least one must be provided to associate the uploaded file.

    Returns
    -------
    Dict[str, Any]
        Parsed JSON response (or {} if empty body).
    """
    if not any([contact_keys, organization_keys, client_group_keys, workitem_keys, integration_task_key]):
        raise ValueError(
            "At least one association key is required: "
            + ", ".join(_ASSOC_FIELDS)
        )

    if file_name is None:
        file_name = os.path.basename(file_path)

    if mime_type is None:
        guessed, _ = mimetypes.guess_type(file_path)
        mime_type = guessed or "application/octet-stream"

    url = client.url("/v3/Files")

    # multipart text fields
    data: Dict[str, Any] = {
        "FileName": file_name,
        "MimeType": mime_type,
    }
    if contact_keys:
        data["contact_keys"] = contact_keys
    if organization_keys:
        data["organization_keys"] = organization_keys
    if client_group_keys:
        data["client_group_keys"] = client_group_keys
    if workitem_keys:
        data["workitem_keys"] = workitem_keys
    if integration_task_key:
        data["integration_task_key"] = integration_task_key

    # default retry/backoff from client if not provided
    _max_retries = client.max_retries if max_retries is None else int(max_retries)
    _backoff = client.backoff_seconds if backoff_seconds is None else float(backoff_seconds)

    last_resp: Optional[requests.Response] = None

    for attempt in range(1, _max_retries + 1):
        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_name, f, mime_type)}
                resp = requests.post(
                    url,
                    headers=client.headers(),
                    data=data,
                    files=files,
                    timeout=client.timeout,
                )
                last_resp = resp

            # Retry on common transient statuses (similar to client.request())
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < _max_retries:
                time.sleep(_backoff * attempt)
                continue

            if not resp.ok:
                _raise_karbon_error(resp)

            if resp.status_code == 204 or not resp.text.strip():
                return {}

            return resp.json()

        except requests.RequestException as e:
            # Network-level errors: retry if attempts remain
            if attempt < _max_retries:
                time.sleep(_backoff * attempt)
                continue
            # If we have a response, raise a KarbonAPIError; otherwise raise as KarbonAPIError(0,...)
            if last_resp is not None:
                _raise_karbon_error(last_resp)
            raise KarbonAPIError(0, f"Request failed: {e}")

    # Should never reach here
    raise KarbonAPIError(0, "Request failed after retries")


def _raise_karbon_error(resp: requests.Response) -> None:
    """Convert a non-2xx HTTP response into KarbonAPIError."""
    msg = None
    try:
        payload = resp.json()
        msg = payload.get("message") or payload.get("error") or str(payload)
    except Exception:
        msg = resp.reason
    raise KarbonAPIError(resp.status_code, msg or resp.reason, response_text=resp.text)