# services/karbon_service.py
import os
import logging
from typing import Optional, List, Dict, Any, Tuple

from fastapi import HTTPException

from karbon_api.client import KarbonClient
from karbon_api.workitems import (
    list_workitems,
    get_workitem,
    update_workitem_full,
    iter_workitems,
)
from karbon_api.organizations import get_organization
from karbon_api.contacts import get_contact

from DrakeAutomation.ocr_normalization import normalize_id


logger = logging.getLogger(__name__)


def env(name: str) -> str:
    """Read an environment variable or raise an HTTP 500 configuration error."""
    v = os.getenv(name)
    if not v:
        raise HTTPException(
            status_code=500,
            detail=f"Server configuration error: Missing environment variable {name}"
        )
    return v


def pick_registration_number(accounting: dict, desired_type: str) -> Optional[str]:
    """Extract a registration number by 'Type' from Karbon accounting details."""
    accounting = accounting or {}
    reg_numbers = accounting.get("RegistrationNumbers") or []

    if not isinstance(reg_numbers, list) or not reg_numbers:
        return None

    for rn in reg_numbers:
        if not isinstance(rn, dict):
            continue
        if (rn.get("Type") or "").strip() == desired_type:
            value = rn.get("RegistrationNumber")
            return value.strip() if isinstance(value, str) else value

    return None


def _build_contact_drake_name(contact: Dict[str, Any]) -> str:
    """Build a Drake-friendly contact name in the format: 'Last, First Middle'."""
    last_name = (contact.get("LastName") or "").strip()
    first_name = (contact.get("FirstName") or "").strip()
    middle_name = (contact.get("MiddleName") or "").strip()

    first_middle = " ".join(x for x in [first_name, middle_name] if x).strip()
    if last_name and first_middle:
        return f"{last_name}, {first_middle}"
    return last_name or first_middle or ""


def _get_client_details(client: KarbonClient, wi: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Resolve client details needed for Drake verification."""
    client_type = wi.get("ClientType")
    client_key = wi.get("ClientKey")
    fallback_name = (wi.get("ClientName") or "").strip()

    if not client_type or not client_key:
        return fallback_name, None

    try:
        if client_type == "Contact":
            contact = get_contact(client, client_key)
            drake_name = _build_contact_drake_name(contact) or fallback_name
            accounting = contact.get("AccountingDetail") or contact.get("AccountingDetails") or {}
            reg = pick_registration_number(accounting, "Social Security Number (SSN)")
            return drake_name, reg

        if client_type == "Organization":
            org = get_organization(client, client_key)
            drake_name = (org.get("FullName") or "").strip() or fallback_name
            accounting = org.get("AccountingDetail") or org.get("AccountingDetails") or {}
            reg = pick_registration_number(accounting, "Tax ID")
            return drake_name, reg

        return fallback_name, None

    except Exception as e:
        logger.warning(
            f"Could not resolve client details for WorkItem {wi.get('WorkItemKey')}: {e}",
            exc_info=True
        )
        return fallback_name, None


def _transform_efile_workitems(
    items: List[Dict[str, Any]],
    client: KarbonClient,
    work_status_filter: str,
) -> List[Dict[str, Any]]:
    """
    Fetch Karbon work items for the E-file Status module.
    """
    # client = KarbonClient(
    #     access_key=env("KARBON_ACCESS_KEY"),
    #     bearer_token=env("KARBON_BEARER_TOKEN"),
    # )

    # items = []
    # for item in iter_workitems(client, filter_=f"WorkStatus eq '{work_status_filter}'", top=min(top, 100)):
    #     items.append(item)
    #     if len(items) >= top:
    #         break

    # if not items:
    #     return []

    results: List[Dict[str, Any]] = []
    for wi in items:
        display_name = (wi.get("ClientName") or "").strip()
        drake_name, registration_number = _get_client_details(client, wi)
        normalized_reg = normalize_id(registration_number) if registration_number else None
        work_status_val = (wi.get("WorkStatus") or work_status_filter or "").strip()
        reason = None
        if not normalized_reg:
            derived_efile = "Missing SSN/EIN"
            reason = "missing_registration_number"
        elif work_status_val in ("Agency Accepted", "Agency Rejected"):
            derived_efile = work_status_val.replace("Drake ", "")
            reason = "already_processed"
        else:
            derived_efile = "Not Checked"
        processable = bool(normalized_reg) and work_status_val not in (
            "Agency Accepted",
            "Agency Rejected",
        )
        results.append({
            "clientName": display_name,
            "clientDrakeName": drake_name,
            "assigneeName": wi.get("AssigneeName"),
            "clientType": wi.get("ClientType"),
            "workStatus": work_status_val,
            "efileStatus": derived_efile,
            "registrationNumber": normalized_reg,
            "workItemKey": wi.get("WorkItemKey"),
            "processable": processable,
            "reason": reason,
        })
    return results


def get_karbon_work_items_for_efile_status_paginated(
    top: int = 100,
    skip: int = 0,
    work_status_filter: str = "Waiting for IRS/Agency",
) -> List[Dict[str, Any]]:
    """Fetch Karbon work items with pagination ($top, $skip)."""
    client = KarbonClient(
        access_key=env("KARBON_ACCESS_KEY"),
        bearer_token=env("KARBON_BEARER_TOKEN"),
    )
    resp = list_workitems(
        client,
        top=min(top, 100),
        skip=skip,
        filter_=f"WorkStatus eq '{work_status_filter}'",
    )
    items = resp.get("value") or resp.get("values") or []
    return _transform_efile_workitems(items, client, work_status_filter)


async def get_karbon_work_items_for_efile_status(
    top: int = 100,
    work_status_filter: str = "Waiting for IRS/Agency",
) -> List[Dict[str, Any]]:
    """Fetch Karbon work items for the E-file Status module (no pagination)."""
    client = KarbonClient(
        access_key=env("KARBON_ACCESS_KEY"),
        bearer_token=env("KARBON_BEARER_TOKEN"),
    )
    items = []
    for item in iter_workitems(client, filter_=f"WorkStatus eq '{work_status_filter}'", top=min(top, 100)):
        items.append(item)
        if len(items) >= top:
            break
    if not items:
        return []
    return _transform_efile_workitems(items, client, work_status_filter)


# -----------------------------
# Update work items for e-file status
# -----------------------------
def _map_efile_to_karbon_work_status(efile_status: str) -> Optional[str]:
    """Map Drake e-file status to Karbon WorkStatus values."""
    mapping = {
        "EF Accepted": "Agency Accepted",
        "EF Rejected": "Agency Rejected",
    }
    return mapping.get((efile_status or "").strip())


def _clean_workitem_payload(work_item: Dict[str, Any]) -> Dict[str, Any]:
    """Remove OData/system keys that should not be included in update payloads."""
    work_item.pop("@odata.context", None)
    work_item.pop("@odata.type", None)
    work_item.pop("WorkItemKey", None)
    return work_item


async def update_work_items_for_efile_status(
    updates: List[Dict[str, Any]],
    *,
    set_primary_status: str = "In Progress",
    update_secondary: bool = True,
) -> Dict[str, Any]:
    """Bulk update Karbon work items based on Drake e-file results."""
    karbon = KarbonClient(
        access_key=env("KARBON_ACCESS_KEY"),
        bearer_token=env("KARBON_BEARER_TOKEN"),
    )

    total = len(updates)
    updated = skipped = failed = 0
    details: List[Dict[str, Any]] = []

    for item in updates:
        workitem_key = item.get("workItemKey")
        efile_status = item.get("efileStatus")

        if not workitem_key:
            skipped += 1
            details.append({"workItemKey": None, "status": "skipped", "reason": "Missing workItemKey"})
            continue

        new_work_status = _map_efile_to_karbon_work_status(efile_status)
        if not new_work_status:
            skipped += 1
            details.append({
                "workItemKey": workitem_key,
                "status": "skipped",
                "reason": f"Unmapped efileStatus: {efile_status}"
            })
            continue

        try:
            work_item = get_workitem(karbon, workitem_key)
            work_item = _clean_workitem_payload(work_item)

            work_item["WorkStatus"] = new_work_status
            work_item["PrimaryStatus"] = set_primary_status
            if update_secondary:
                work_item["SecondaryStatus"] = new_work_status

            update_workitem_full(
                client=karbon,
                workitem_key=workitem_key,
                payload=work_item
            )
            
            work_item = get_workitem(karbon, workitem_key)
            if work_item.get("SecondaryStatus") != new_work_status:
                actual = work_item.get("SecondaryStatus")
                raise Exception(f"Status verification failed. Expected '{new_work_status}', got '{actual}'")

            updated += 1
            details.append({
                "workItemKey": workitem_key,
                "status": "updated",
                "workStatus": new_work_status
            })

        except Exception as e:
            failed += 1
            logger.warning(f"Update failed for WorkItem {workitem_key}: {e}", exc_info=True)
            details.append({
                "workItemKey": workitem_key,
                "status": "failed",
                "reason": "Update failed"
            })
    return {
        "total": total,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "details": details,
    }
    
    
async def get_karbon_work_items_for_FI_status(
    top: int = 100,
    work_status_filter: str = "Return Assembly",
) -> List[Dict[str, Any]]:
    """
    Fetch Karbon work items for the E-file Status module.
    """
    client = KarbonClient(
        access_key=env("KARBON_ACCESS_KEY"),
        bearer_token=env("KARBON_BEARER_TOKEN"),
    )

    items = []
    for item in iter_workitems(client, filter_=f"WorkStatus eq '{work_status_filter}'", top=min(top, 100)):
        items.append(item)
        if len(items) >= top:
            break

    if not items:
        return []

    results: List[Dict[str, Any]] = []

    for wi in items:
        display_name = (wi.get("ClientName") or "").strip()
        drake_name, registration_number = _get_client_details(client, wi)

        normalized_reg = normalize_id(registration_number) if registration_number else None
        work_status_val = (wi.get("WorkStatus") or work_status_filter or "").strip()

        # -------- derive efileStatus + reason --------
        reason = None
        if not normalized_reg:
            derived_efile = "Missing SSN/EIN"
            reason = "missing_registration_number"
        else:
            derived_efile = "Not Checked"

        processable = bool(normalized_reg) and work_status_val not in (
            "Agency Accepted",
            "Agency Rejected",
        )

        results.append({
            "clientName": display_name,
            "clientDrakeName": drake_name,
            "assigneeName": wi.get("AssigneeName"),
            "clientType": wi.get("ClientType"),
            "workStatus": work_status_val,
            "efileStatus": derived_efile,
            "registrationNumber": normalized_reg,
            "workItemKey": wi.get("WorkItemKey"),
            "processable": processable,
            "reason": reason,
        })

    return results
