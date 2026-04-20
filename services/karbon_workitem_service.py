"""
Karbon workitem service - fetches Karbon workitems for UI list views.
Always fetches database status from Service B and merges into items so the UI
shows correct badges on first load. Polling is used afterward for live updates.
"""
import logging
from typing import List, Dict, Any

from services.karbon_service import get_karbon_work_items_for_efile_status_paginated
from services.automation_tracking_service import merge_status_into_workitems
from services.drake_service_client import get_workitem_status

logger = logging.getLogger(__name__)


async def enrich_efile_items_with_status(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fetch database status for the given work items and merge into each item.
    Uses workItemKey as the key. Safe to call with empty list (returns []).
    """
    if not items:
        return []
    perma_keys = [str(it["workItemKey"]) for it in items if it.get("workItemKey") is not None]
    if not perma_keys:
        return merge_status_into_workitems(items, {}, permakey_field="workItemKey")
    try:
        payload = await get_workitem_status(perma_keys)
        statuses = payload.get("statuses", {}) if isinstance(payload, dict) else {}
    except Exception as e:
        logger.warning("Failed to get workitem status from Service B: %s", e)
        statuses = {}
    return merge_status_into_workitems(items, statuses, permakey_field="workItemKey")


async def get_efile_status_workitems_enriched(
    top: int = 100,
    skip: int = 0,
    work_status_filter: str = "Waiting for IRS/Agency",
) -> List[Dict[str, Any]]:
    """
    Fetch Karbon workitems, then always fetch DB status from Service B and merge
    so the UI shows correct status badges on first load. On Karbon failure, log
    and return empty list (no 500).
    """
    try:
        items = get_karbon_work_items_for_efile_status_paginated(
            top=top, skip=skip, work_status_filter=work_status_filter
        )
    except Exception as e:
        logger.warning("Error fetching efile work items from Karbon. Returning empty list: %s", e)
        items = []

    return await enrich_efile_items_with_status(items)
