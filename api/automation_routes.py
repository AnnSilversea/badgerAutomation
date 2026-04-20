"""
Automation routes - proxy to Service B for workitem status.
Service A does not own the database. All status queries go to Service B.
"""
import logging
from typing import List

from fastapi import APIRouter, Query

from services.drake_service_client import get_fi_workitem_status, get_workitem_status

logger = logging.getLogger(__name__)

workitems_router = APIRouter(prefix="/api/workitems", tags=["Workitems"])


@workitems_router.get("/status")
async def workitem_status_batch(
    perma_keys: str = Query(..., description="Comma-separated perma_keys"),
):
    """
    Get automation status. Proxies to Service B.
    Returns { queue_empty: bool, statuses: { perma_key: { status, message, ... } } }
    """
    keys = [k.strip() for k in perma_keys.split(",") if k.strip()]
    if not keys:
        return {"queue_empty": False, "statuses": {}}
    try:
        payload = await get_workitem_status(keys)
        # Service B returns the complete payload. Keep backward compatibility if
        # an older Service B returns only the status map.
        if isinstance(payload, dict) and "statuses" in payload:
            return {
                "queue_empty": bool(payload.get("queue_empty", False)),
                "statuses": payload.get("statuses", {}),
            }
        return {"queue_empty": False, "statuses": payload if isinstance(payload, dict) else {}}
    except Exception as e:
        logger.warning("Failed to get workitem status from Service B. Returning empty status payload: %s", e)
        return {"queue_empty": False, "statuses": {}}


@workitems_router.get("/fi/status")
async def fi_workitem_status_batch(
    perma_keys: str = Query(..., description="Comma-separated workitem_ids"),
):
    """
    Get FI automation status. Proxies to Service B.
    Returns { queue_empty: bool, statuses: { workitem_id: { status, message, ... } } }
    """
    keys = [k.strip() for k in perma_keys.split(",") if k.strip()]
    if not keys:
        return {"queue_empty": False, "statuses": {}}
    try:
        payload = await get_fi_workitem_status(keys)
        if isinstance(payload, dict) and "statuses" in payload:
            return {
                "queue_empty": bool(payload.get("queue_empty", False)),
                "statuses": payload.get("statuses", {}),
            }
        return {"queue_empty": False, "statuses": payload if isinstance(payload, dict) else {}}
    except Exception as e:
        logger.warning("Failed to get FI workitem status from Service B. Returning empty status payload: %s", e)
        return {"queue_empty": False, "statuses": {}}
