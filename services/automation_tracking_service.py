"""Business logic for automation state tracking. Service A calls Service B for status."""
from typing import Callable, Dict, List, Optional  # noqa: F401

# Reusable: merge status map into workitems with configurable output field and status mapper
def merge_status_into_workitems(
    workitems: List[Dict],
    status_map: Dict[str, Dict],
    permakey_field: str = "workItemKey",
    output_status_field: str = "automationStatus",
    output_message_field: str = "automationMessage",
    output_started_field: str = "automationStartedAt",
    output_completed_field: str = "automationCompletedAt",
    status_to_ui: Optional[Callable[[str, Optional[str]], str]] = None,
) -> List[Dict]:
    """
    Merge automation status into workitem dicts.
    status_map: { workitem_id: { status, message, started_at, completed_at } }
    If status_to_ui is provided, it maps (db_status, message) -> UI display value.
    """
    for wi in workitems:
        key = wi.get(permakey_field)
        if key is None:
            continue
        key_str = str(key)
        st = status_map.get(key_str, {})
        db_status = st.get("status", "NOT_STARTED")
        message = st.get("message")
        wi[output_status_field] = db_status
        wi[output_message_field] = message
        wi[output_started_field] = st.get("started_at")
        wi[output_completed_field] = st.get("completed_at")
        if status_to_ui:
            wi["drake_fi_status"] = status_to_ui(db_status, message)
    return workitems


def merge_fi_status_into_workitems(
    workitems: List[Dict],
    status_map: Dict[str, Dict],
    permakey_field: str = "workItemKey",
) -> List[Dict]:
    """
    Merge FI status into workitems.
    - Adds DB-backed fields: automationStatus, automationMessage, automationStartedAt, automationCompletedAt
    - Adds drake_fi_status for legacy UI ("Success"|"Error"|"Not Processed")
    """
    merge_status_into_workitems(
        workitems,
        status_map,
        permakey_field=permakey_field,
        output_status_field="automationStatus",
        output_message_field="automationMessage",
        output_started_field="automationStartedAt",
        output_completed_field="automationCompletedAt",
    )

    for wi in workitems:
        s = StringOrEmpty(wi.get("automationStatus")).upper()
        if s == "SUCCESS":
            wi["drake_fi_status"] = "Success"
        elif s == "FAIL":
            wi["drake_fi_status"] = "Error"
        elif s in ("IN_QUEUE", "IN_PROGRESS"):
            wi["drake_fi_status"] = s
        else:
            wi["drake_fi_status"] = "Not Processed"
    return workitems


def StringOrEmpty(value) -> str:
    return "" if value is None else str(value)


def can_trigger_automation(status: Optional[str]) -> bool:
    """Return True if automation can be triggered."""
    if status is None:
        return True
    return status in ("FAIL", "FAILED", "ERROR", "NOT_STARTED")


def should_return_current_status(status: Optional[str]) -> bool:
    """Return True if we should not enqueue (IN_QUEUE or IN_PROCESSING)."""
    return status in ("IN_QUEUE", "PROCESSING", "IN_PROCESSING")
