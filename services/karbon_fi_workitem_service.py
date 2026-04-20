"""
Karbon FI workitem service - fetches FI workitems and merges drake_fi_status from Service B.
Always fetches database status on list load so the UI shows correct badges immediately.
"""
import logging
from typing import List, Dict, Any

from services.karbon_service import get_karbon_work_items_for_FI_status
from services.automation_tracking_service import merge_fi_status_into_workitems
from services.drake_service_client import get_fi_workitem_status

logger = logging.getLogger(__name__)


async def get_fi_workitems_enriched(
    top: int = 100,
    work_status_filter: str = "Return Assembly",
) -> List[Dict[str, Any]]:
    """
    Fetch Karbon FI workitems, then always fetch DB status from Service B and merge
    so the UI shows correct status badges on first load. On Karbon failure, log
    and return empty list (no 500).
    """
    try:
        items = await get_karbon_work_items_for_FI_status(
            top=top,
            work_status_filter=work_status_filter,
        )
    except Exception as e:
        logger.warning("Error fetching FI work items from Karbon. Returning empty list: %s", e)
        items = []

    if not items:
        return []

    perma_keys = [str(it["workItemKey"]) for it in items if it.get("workItemKey") is not None]
    if not perma_keys:
        return merge_fi_status_into_workitems(items, {}, permakey_field="workItemKey")
    try:
        payload = await get_fi_workitem_status(perma_keys)
        statuses = payload.get("statuses", {}) if isinstance(payload, dict) else {}
    except Exception as e:
        logger.warning("Failed to get FI workitem status from Service B: %s", e)
        statuses = {}

    return merge_fi_status_into_workitems(items, statuses, permakey_field="workItemKey")
