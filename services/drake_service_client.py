"""
HTTP client to call Drake Automation Service (Service B).
Service A uses this to proxy automation requests.
"""
import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional, List

import httpx

logger = logging.getLogger(__name__)

SERVICE_B_URL = os.getenv("SERVICE_B_BASE") or os.getenv("SERVICE_B_URL", "http://localhost:8001")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "15"))
# Ensure launch/poll waits long enough for Drake automation to finish.
# Minimum enforced at 15 minutes to avoid false failures on long runs.
POLL_TIMEOUT = max(int(os.getenv("POLL_TIMEOUT", "900")), 900)
POLL_REQUEST_TIMEOUT = float(os.getenv("POLL_REQUEST_TIMEOUT", "60"))
STATUS_QUERY_TIMEOUT = float(os.getenv("STATUS_QUERY_TIMEOUT", "30"))
STATUS_QUERY_CHUNK_SIZE = int(os.getenv("STATUS_QUERY_CHUNK_SIZE", "100"))

# Required when Service B is behind ngrok - bypasses HTML interstitial for API requests
_HEADERS = {"ngrok-skip-browser-warning": "1"} if "ngrok" in SERVICE_B_URL.lower() else {}


def _parse_json(resp: httpx.Response) -> Dict[str, Any]:
    """Parse response as JSON, with clear error if body is HTML or empty."""
    try:
        return resp.json()
    except json.JSONDecodeError as e:
        text = resp.text[:500] if resp.text else "(empty)"
        logger.error("Service B returned non-JSON response (status=%s): %s", resp.status_code, text)
        raise RuntimeError(
            f"Service B returned invalid response. If using ngrok, ensure ngrok-skip-browser-warning header is sent. "
            f"Raw: {text[:200]}..."
        ) from e


async def _poll_task(task_id: str) -> Dict[str, Any]:
    """Poll Service B for task result until done."""
    deadline = time.monotonic() + POLL_TIMEOUT
    async with httpx.AsyncClient(timeout=POLL_REQUEST_TIMEOUT) as client:
        while time.monotonic() < deadline:
            try:
                resp = await client.get(f"{SERVICE_B_URL}/api/tasks/{task_id}", headers=_HEADERS)
                resp.raise_for_status()
                data = _parse_json(resp)
            except (httpx.HTTPError, RuntimeError) as exc:
                # Polling can be transiently unavailable while long automation is still running.
                logger.warning("Task status poll failed for %s: %r", task_id, exc)
                await asyncio.sleep(POLL_INTERVAL)
                continue

            status = str(data.get("status", "")).lower()
            if status == "success":
                return data.get("result")
            if status == "failure":
                err_msg = data.get("error") or "Task failed"
                raise RuntimeError(str(err_msg))
            await asyncio.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Task {task_id} did not complete within {POLL_TIMEOUT}s")


async def call_drake_launch(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Proxy Drake launch to Service B, wait for result."""
    async with httpx.AsyncClient(timeout=POLL_TIMEOUT) as client:
        resp = await client.post(f"{SERVICE_B_URL}/api/drake/launch", json=payload, headers=_HEADERS)
        resp.raise_for_status()
        data = _parse_json(resp)
    task_id = data.get("task_id")
    if task_id:
        return await _poll_task(task_id)
    return data


async def start_drake_launch(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Start Drake launch task and return immediate task metadata."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{SERVICE_B_URL}/api/drake/launch", json=payload, headers=_HEADERS)
        resp.raise_for_status()
        return _parse_json(resp)


async def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get raw task status payload from Service B."""
    async with httpx.AsyncClient(timeout=POLL_REQUEST_TIMEOUT) as client:
        resp = await client.get(f"{SERVICE_B_URL}/api/tasks/{task_id}", headers=_HEADERS)
        resp.raise_for_status()
        return _parse_json(resp)


async def call_query_clients() -> list:
    """Proxy query clients to Service B, wait for result."""
    async with httpx.AsyncClient(timeout=POLL_TIMEOUT) as client:
        resp = await client.post(f"{SERVICE_B_URL}/api/drake/query-clients", headers=_HEADERS)
        resp.raise_for_status()
        data = _parse_json(resp)
    task_id = data.get("task_id")
    if task_id:
        return await _poll_task(task_id)
    return data


async def call_print_return(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Proxy print return to Service B, wait for result."""
    async with httpx.AsyncClient(timeout=POLL_TIMEOUT) as client:
        resp = await client.post(f"{SERVICE_B_URL}/api/drake/print-return", json=payload, headers=_HEADERS)
        resp.raise_for_status()
        data = _parse_json(resp)
    task_id = data.get("task_id")
    if not task_id:
        return data  # skipped
    return await _poll_task(task_id)


async def get_ocr_results(tax_ids: list) -> List[Dict[str, Any]]:
    """Query OCR results from Service B. Returns list of {tax_id, outputs_parent_folder, ocr_status, ...}."""
    if not tax_ids:
        return []
    keys_str = ",".join(str(k).strip() for k in tax_ids if str(k).strip())
    if not keys_str:
        return []
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{SERVICE_B_URL}/api/ocr-results",
            params={"tax_ids": keys_str},
            headers=_HEADERS,
        )
        resp.raise_for_status()
        data = _parse_json(resp)
        # Service B returns a list
        return data if isinstance(data, list) else []


async def upsert_ocr_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert OCR result row in Service B. Intended for Service A internal use."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{SERVICE_B_URL}/api/ocr-results/upsert",
            json=payload,
            headers=_HEADERS,
        )
        resp.raise_for_status()
        return _parse_json(resp)


async def call_efile_run_batch(client_ids: list, open: bool = True, close: bool = True) -> Dict[str, Any]:
    """Proxy efile run-batch to Service B, wait for result."""
    payload = {
        "client_ids": client_ids,
        "open": open,
        "close": close
    }
    async with httpx.AsyncClient(timeout=POLL_TIMEOUT) as client:
        resp = await client.post(f"{SERVICE_B_URL}/api/drake/efile/run-batch", json=payload, headers=_HEADERS)
        resp.raise_for_status()
        data = _parse_json(resp)
    task_id = data.get("task_id")
    if not task_id:
        return data  # skipped
    return await _poll_task(task_id)


async def call_process_efile_status(targets: list) -> Dict[str, Any]:
    """Proxy process-efile-status to Service B, wait for result."""
    async with httpx.AsyncClient(timeout=POLL_TIMEOUT) as client:
        resp = await client.post(f"{SERVICE_B_URL}/api/karbon/process-efile-status", json={"targets": targets}, headers=_HEADERS)
        resp.raise_for_status()
        data = _parse_json(resp)
    task_id = data.get("task_id")
    if not task_id:
        return {"updates": [], "details": []}
    result = await _poll_task(task_id)
    return result if isinstance(result, dict) else {"updates": [], "details": []}


async def call_process_fi(targets: list, close_drake: bool = True) -> Dict[str, Any]:
    """Proxy process-fi to Service B, wait for result."""
    async with httpx.AsyncClient(timeout=POLL_TIMEOUT) as client:
        resp = await client.post(
            f"{SERVICE_B_URL}/api/karbon/process-fi",
            json={"targets": targets, "close_drake": close_drake},
            headers=_HEADERS
        )
        resp.raise_for_status()
        data = _parse_json(resp)
    task_id = data.get("task_id")
    if not task_id:
        return data if isinstance(data, dict) else {"processed_count": 0, "totals": {}, "details": []}
    return await _poll_task(task_id)


async def get_workitem_status(perma_keys: list) -> Dict[str, Any]:
    """Get Efile automation status from Service B."""
    if not perma_keys:
        return {"queue_empty": False, "statuses": {}}
    keys = [str(k) for k in perma_keys if k]
    if not keys:
        return {"queue_empty": False, "statuses": {}}
    try:
        merged_statuses: Dict[str, Any] = {}
        queue_empty = False
        chunk_size = max(1, STATUS_QUERY_CHUNK_SIZE)

        async with httpx.AsyncClient(timeout=STATUS_QUERY_TIMEOUT) as client:
            for i in range(0, len(keys), chunk_size):
                chunk = keys[i : i + chunk_size]
                resp = await client.get(
                    f"{SERVICE_B_URL}/api/workitems/status",
                    params={"perma_keys": ",".join(chunk)},
                    headers=_HEADERS,
                )
                resp.raise_for_status()
                payload = _parse_json(resp)
                if isinstance(payload, dict):
                    queue_empty = bool(payload.get("queue_empty", queue_empty))
                    statuses = payload.get("statuses", {})
                    if isinstance(statuses, dict):
                        merged_statuses.update(statuses)
        return {"queue_empty": queue_empty, "statuses": merged_statuses}
    except Exception as e:
        logger.warning(
            "Service B unavailable for efile status (url=%s, keys=%s): %r",
            SERVICE_B_URL,
            len(keys),
            e,
        )
        return {"queue_empty": False, "statuses": {}}


async def get_fi_workitem_status(workitem_ids: list) -> Dict[str, Any]:
    """Get Filing Instruction job status from Service B."""
    if not workitem_ids:
        return {"queue_empty": False, "statuses": {}}
    keys = [str(k) for k in workitem_ids if k]
    if not keys:
        return {"queue_empty": False, "statuses": {}}
    try:
        merged_statuses: Dict[str, Any] = {}
        queue_empty = False
        chunk_size = max(1, STATUS_QUERY_CHUNK_SIZE)

        async with httpx.AsyncClient(timeout=STATUS_QUERY_TIMEOUT) as client:
            for i in range(0, len(keys), chunk_size):
                chunk = keys[i : i + chunk_size]
                resp = await client.get(
                    f"{SERVICE_B_URL}/api/workitems/fi/status",
                    params={"perma_keys": ",".join(chunk)},
                    headers=_HEADERS,
                )
                resp.raise_for_status()
                payload = _parse_json(resp)
                if isinstance(payload, dict):
                    queue_empty = bool(payload.get("queue_empty", queue_empty))
                    statuses = payload.get("statuses", {})
                    if isinstance(statuses, dict):
                        merged_statuses.update(statuses)
        return {"queue_empty": queue_empty, "statuses": merged_statuses}
    except Exception as e:
        logger.warning(
            "Service B unavailable for FI status (url=%s, keys=%s): %r",
            SERVICE_B_URL,
            len(keys),
            e,
        )
        return {"queue_empty": False, "statuses": {}}


async def enqueue_fi_workitems(items: list[Dict[str, Any]]) -> None:
    """
    Insert/update FI jobs as IN_QUEUE in Service B before triggering automation.
    items: [{ workitem_id, tax_id, client_name }]
    """
    if not items:
        return
    payload_items = []
    for it in items:
        workitem_id = it.get("workitem_id")
        if not workitem_id:
            continue
        payload_items.append(
            {
                "workitem_id": str(workitem_id),
                "tax_id": it.get("tax_id"),
                "client_name": it.get("client_name"),
            }
        )
    if not payload_items:
        return
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{SERVICE_B_URL}/api/workitems/fi/enqueue",
            json={"items": payload_items},
            headers=_HEADERS,
        )
        resp.raise_for_status()


async def trigger_process_fi(targets: list, close_drake: bool = True) -> Dict[str, Any]:
    """
    Trigger FI automation on Service B and return immediately with task_id.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{SERVICE_B_URL}/api/karbon/process-fi",
            json={"targets": targets, "close_drake": close_drake},
            headers=_HEADERS,
        )
        resp.raise_for_status()
        return _parse_json(resp)

async def enqueue_workitems(perma_keys: list, triggered_by: Optional[str] = None) -> None:
    """Mark workitems as IN_QUEUE in Service B before enqueueing Celery task."""
    if not perma_keys:
        return
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{SERVICE_B_URL}/api/workitems/enqueue",
            json={"perma_keys": list(perma_keys), "triggered_by": triggered_by},
            headers=_HEADERS,
        )
        resp.raise_for_status()


async def update_workitem_status(perma_key: str, status: str, message: Optional[str] = None) -> None:
    """Update workitem status in Service B. Used when Service A detects failure before/during processing."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        payload = {"perma_key": perma_key, "status": status}
        if message is not None:
            payload["message"] = message
        resp = await client.post(
            f"{SERVICE_B_URL}/api/workitems/update-status",
            json=payload,
            headers=_HEADERS,
        )
        resp.raise_for_status()


async def check_can_trigger(perma_key: str) -> Dict[str, Any]:
    """Check if workitem can be triggered. Returns { can_trigger, in_progress, status }."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(
            f"{SERVICE_B_URL}/api/workitems/check-trigger",
            params={"perma_key": perma_key},
            headers=_HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


async def call_efile_status_check_client(
    client_id: str,
    client_name: Optional[str] = None,
    work_item_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Proxy efile-status check-client to Service B, wait for result."""
    payload = {"client_id": client_id, "client_name": client_name, "work_item_key": work_item_key}
    payload = {k: v for k, v in payload.items() if v is not None}
    async with httpx.AsyncClient(timeout=POLL_TIMEOUT) as client:
        resp = await client.post(
            f"{SERVICE_B_URL}/api/drake/efile-status/check-client",
            json=payload,
            headers=_HEADERS
        )
        resp.raise_for_status()
        data = _parse_json(resp)
    task_id = data.get("task_id")
    if not task_id:
        return data
    return await _poll_task(task_id)


async def call_efile_status_open_session() -> Dict[str, Any]:
    """Proxy efile-status open-session to Service B, wait for result."""
    async with httpx.AsyncClient(timeout=POLL_TIMEOUT) as client:
        resp = await client.post(f"{SERVICE_B_URL}/api/drake/efile-status/open", headers=_HEADERS)
        resp.raise_for_status()
        data = _parse_json(resp)
    task_id = data.get("task_id")
    if not task_id:
        return data
    return await _poll_task(task_id)


async def call_efile_status_close_session() -> Dict[str, Any]:
    """Proxy efile-status close-session to Service B, wait for result."""
    async with httpx.AsyncClient(timeout=POLL_TIMEOUT) as client:
        resp = await client.post(f"{SERVICE_B_URL}/api/drake/efile-status/close", headers=_HEADERS)
        resp.raise_for_status()
        data = _parse_json(resp)
    task_id = data.get("task_id")
    if not task_id:
        return data
    return await _poll_task(task_id)
