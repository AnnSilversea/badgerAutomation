"""Workitems API - status query and update. Service B owns the database."""
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from drake_service.database.session import get_db
from drake_service.repositories.automation_repository import (
    get_by_permakey,
    get_by_permakeys,
    list_paginated,
    upsert_queued,
    upsert_status,
)
from drake_service.repositories.fi_job_repository import (
    get_by_workitem_id as fi_get_by_workitem_id,
    get_by_workitem_ids as fi_get_by_workitem_ids,
)
from drake_service.repositories.fi_job_repository import enqueue_jobs as fi_enqueue_jobs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workitems", tags=["Workitems"])

VALID_STATUSES = {"IN_QUEUE", "IN_PROCESSING", "SUCCESS", "FAIL", "ERROR", "CLIENT_NOT_FOUND", "MISSING_TAX_ID"}


class WorkitemStatusUpdate(BaseModel):
    perma_key: str
    status: str
    message: Optional[str] = None


class EnqueueRequest(BaseModel):
    perma_keys: List[str]
    triggered_by: Optional[str] = None


class FIEnqueueItem(BaseModel):
    workitem_id: str
    tax_id: Optional[str] = None
    client_name: Optional[str] = None


class FIEnqueueRequest(BaseModel):
    items: List[FIEnqueueItem]


def _get_queue_empty_metadata() -> bool:
    """
    Queue metadata for response compatibility.
    Broker inspection has been removed; keep this as non-blocking metadata only.
    """
    return False


@router.get("/status")
async def get_workitem_status(
    perma_keys: str = Query(..., description="Comma-separated perma_keys"),
    db: Session = Depends(get_db),
):
    """Get automation status for multiple perma_keys."""
    queue_empty = _get_queue_empty_metadata()
    keys = [k.strip() for k in perma_keys.split(",") if k.strip()]
    if not keys:
        return {"queue_empty": queue_empty, "statuses": {}}
    records = get_by_permakeys(db, keys)
    result = {}
    for r in records:
        result[r.workitem_id] = {
            "status": r.status,
            "message": r.message,
            "started_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.processed_at.isoformat() if r.processed_at else None,
        }
    return {"queue_empty": queue_empty, "statuses": result}


@router.post("/update-status")
async def update_workitem_status(
    payload: WorkitemStatusUpdate,
    db: Session = Depends(get_db),
):
    """Update workitem status. Called by Celery worker."""
    if payload.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {payload.status}. Must be one of {VALID_STATUSES}",
        )
    logger.info(
        "Updating workitem status",
        extra={"perma_key": payload.perma_key, "status": payload.status, "message": payload.message},
    )
    upsert_status(db, payload.perma_key, payload.status, payload.message)
    return {"status": "ok"}


@router.post("/enqueue")
async def enqueue_workitems(
    payload: EnqueueRequest,
    db: Session = Depends(get_db),
):
    """Mark workitems as IN_QUEUE. Called by Service A before sending to Celery."""
    items = []
    for key in payload.perma_keys:
        if not key:
            continue
        rec = upsert_queued(db, key)
        items.append(
            {
                "workitem_id": rec.workitem_id,
                "status": rec.status,
                "message": rec.message,
            }
        )
    return {"status": "ok", "count": len(items), "items": items}


@router.get("")
async def list_workitems(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    """List workitems with pagination."""
    items, total = list_paginated(db, limit=limit, offset=offset, status_filter=status)
    return {
        "items": [
            {
                "workitem_id": r.workitem_id,
                "client_id": r.client_id,
                "status": r.status,
                "message": r.message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
            }
            for r in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/fi/status")
async def get_fi_workitem_status(
    perma_keys: str = Query(..., description="Comma-separated workitem_ids"),
    db: Session = Depends(get_db),
):
    """Get Filing Instruction job status for multiple workitem_ids."""
    queue_empty = _get_queue_empty_metadata()
    keys = [k.strip() for k in perma_keys.split(",") if k.strip()]
    if not keys:
        return {"queue_empty": queue_empty, "statuses": {}}
    records = fi_get_by_workitem_ids(db, keys)
    result = {}
    for r in records:
        result[r.workitem_id] = {
            "status": r.status,
            "message": r.message,
            "started_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.processed_at.isoformat() if r.processed_at else None,
            "tax_id": getattr(r, "tax_id", None) or r.client_id,
            "client_name": getattr(r, "client_name", None),
        }
    return {"queue_empty": queue_empty, "statuses": result}


@router.post("/fi/enqueue")
async def enqueue_fi_workitems(
    payload: FIEnqueueRequest,
    db: Session = Depends(get_db),
):
    """
    Insert/update FI jobs BEFORE automation begins.
    Sets status=IN_QUEUE for all items.
    """
    items = payload.items or []
    jobs = [
        {"workitem_id": it.workitem_id, "tax_id": it.tax_id, "client_name": it.client_name}
        for it in items
        if it and it.workitem_id
    ]
    recs = fi_enqueue_jobs(db, jobs)
    return {
        "status": "ok",
        "count": len(recs),
        "items": [
            {
                "workitem_id": r.workitem_id,
                "status": r.status,
                "message": r.message,
                "tax_id": getattr(r, "tax_id", None) or r.client_id,
                "client_name": getattr(r, "client_name", None),
            }
            for r in recs
        ],
    }


@router.get("/check-trigger")
async def check_can_trigger(
    perma_key: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Check if workitem can be triggered (no active job exists).

    This is used to prevent duplicate submissions from enqueuing multiple Celery tasks.
    A workitem is considered "in progress" if either job table has an active status.
    """
    efile_rec = get_by_permakey(db, perma_key)
    fi_rec = fi_get_by_workitem_id(db, perma_key)

    efile_status = (efile_rec.status if efile_rec else None) or None
    fi_status = (fi_rec.status if fi_rec else None) or None

    active_statuses = {"IN_QUEUE", "IN_PROGRESS", "IN_PROCESSING", "PROCESSING"}
    in_progress = (str(efile_status or "").upper() in active_statuses) or (str(fi_status or "").upper() in active_statuses)

    # Allow triggers when there is no record, or when both are in terminal/idle states.
    terminal_or_idle = {"NOT_STARTED", "SUCCESS", "FAIL", "FAILED", "ERROR", "CLIENT_NOT_FOUND", "MISSING_TAX_ID"}
    can_trigger = (not in_progress) and (
        (efile_status is None or str(efile_status).upper() in terminal_or_idle)
        and (fi_status is None or str(fi_status).upper() in terminal_or_idle)
    )

    # Prefer reporting an active status if present, otherwise efile, otherwise fi.
    status = None
    if str(efile_status or "").upper() in active_statuses:
        status = efile_status
    elif str(fi_status or "").upper() in active_statuses:
        status = fi_status
    else:
        # Both inactive. Use the most recently updated meaningful status.
        ef_time = efile_rec.updated_at if efile_rec else datetime.min
        fi_time = fi_rec.updated_at if fi_rec else datetime.min
        
        ef_not_started = str(efile_status or "NOT_STARTED").upper() == "NOT_STARTED"
        fi_not_started = str(fi_status or "NOT_STARTED").upper() == "NOT_STARTED"

        if not fi_not_started and (ef_not_started or fi_time >= ef_time):
            status = fi_status
        else:
            status = efile_status or fi_status
    return {
        "perma_key": perma_key,
        "status": status or "NOT_STARTED",
        "can_trigger": can_trigger and not in_progress,
        "in_progress": in_progress,
    }
