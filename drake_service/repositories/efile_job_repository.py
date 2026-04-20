"""Repository for karbon_efile_status_jobs table."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from drake_service.database.models import KarbonEfileStatusJob
from drake_service.repositories.job_helpers import update_job_status


def get_by_workitem_id(db: Session, workitem_id: str) -> Optional[KarbonEfileStatusJob]:
    """Get efile job by workitem_id (Karbon workItemKey)."""
    return db.query(KarbonEfileStatusJob).filter(KarbonEfileStatusJob.workitem_id == workitem_id).first()


def get_by_workitem_ids(db: Session, workitem_ids: List[str]) -> List[KarbonEfileStatusJob]:
    """Get efile jobs for multiple workitem_ids."""
    if not workitem_ids:
        return []
    return db.query(KarbonEfileStatusJob).filter(KarbonEfileStatusJob.workitem_id.in_(workitem_ids)).all()


def list_paginated(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
) -> tuple[List[KarbonEfileStatusJob], int]:
    """List efile jobs with pagination."""
    q = db.query(KarbonEfileStatusJob)
    if status_filter:
        q = q.filter(KarbonEfileStatusJob.status == status_filter)
    total = q.count()
    items = q.order_by(KarbonEfileStatusJob.updated_at.desc()).offset(offset).limit(limit).all()
    return items, total


def upsert_queued(
    db: Session,
    workitem_id: str,
    client_id: Optional[str] = None,
    triggered_by: Optional[str] = None,
) -> KarbonEfileStatusJob:
    """
    Create or update record to IN_QUEUE status.

    Idempotency: if an active job already exists (IN_QUEUE / IN_PROCESSING / PROCESSING),
    do not create a duplicate and do not regress status.
    """
    rec = get_by_workitem_id(db, workitem_id)
    now = datetime.utcnow()
    if rec:
        active_statuses = {"IN_QUEUE", "IN_PROCESSING", "PROCESSING"}
        if (rec.status or "").upper() in active_statuses:
            # Already active: return as-is (idempotent enqueue)
            return rec
        rec.status = "IN_QUEUE"
        rec.message = None
        rec.updated_at = now
        rec.processed_at = None
        if client_id is not None:
            rec.client_id = client_id
    else:
        rec = KarbonEfileStatusJob(
            workitem_id=workitem_id,
            client_id=client_id,
            status="IN_QUEUE",
        )
        db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def upsert_status(
    db: Session,
    workitem_id: str,
    status: str,
    message: Optional[str] = None,
    client_id: Optional[str] = None,
) -> KarbonEfileStatusJob:
    """Create or update efile job status. Used by Celery worker."""
    update_job_status(db, KarbonEfileStatusJob, workitem_id, status, message, client_id)
    return get_by_workitem_id(db, workitem_id)


def clear_in_queue(db: Session) -> int:
    """
    Delete stale rows stuck in IN_QUEUE.
    Returns number of deleted rows.
    """
    deleted = (
        db.query(KarbonEfileStatusJob)
        .filter(KarbonEfileStatusJob.status == "IN_QUEUE")
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


# Backward compatibility: permakey = workitem_id
def get_by_permakey(db: Session, permakey: str) -> Optional[KarbonEfileStatusJob]:
    """Alias for get_by_workitem_id."""
    return get_by_workitem_id(db, permakey)


def get_by_permakeys(db: Session, permakeys: List[str]) -> List[KarbonEfileStatusJob]:
    """Alias for get_by_workitem_ids."""
    return get_by_workitem_ids(db, permakeys)
