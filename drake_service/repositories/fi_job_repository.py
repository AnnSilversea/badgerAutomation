"""Repository for karbon_filing_instruction_jobs table."""
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from drake_service.database.models import KarbonFilingInstructionJob
from drake_service.repositories.job_helpers import update_job_status


def get_by_workitem_id(db: Session, workitem_id: str) -> Optional[KarbonFilingInstructionJob]:
    """Get FI job by workitem_id."""
    return db.query(KarbonFilingInstructionJob).filter(KarbonFilingInstructionJob.workitem_id == workitem_id).first()


def get_by_workitem_ids(db: Session, workitem_ids: List[str]) -> List[KarbonFilingInstructionJob]:
    """Get FI jobs for multiple workitem_ids."""
    if not workitem_ids:
        return []
    return db.query(KarbonFilingInstructionJob).filter(KarbonFilingInstructionJob.workitem_id.in_(workitem_ids)).all()


def enqueue_jobs(
    db: Session,
    jobs: Iterable[Dict[str, Optional[str]]],
) -> List[KarbonFilingInstructionJob]:
    """
    Insert/update FI job rows BEFORE automation begins.
    Sets status=IN_QUEUE and clears message/processed_at.

    Expected fields per job:
      - workitem_id (required)
      - tax_id (optional)
      - client_name (optional)
    """
    now = datetime.utcnow()
    created: List[KarbonFilingInstructionJob] = []

    for j in jobs:
        workitem_id = (j.get("workitem_id") or "").strip()
        if not workitem_id:
            continue
        tax_id = j.get("tax_id")
        client_name = j.get("client_name")

        rec = get_by_workitem_id(db, workitem_id)
        if rec:
            active_statuses = {"IN_QUEUE", "IN_PROGRESS", "IN_PROCESSING", "PROCESSING"}
            if (rec.status or "").upper() in active_statuses:
                # Already active: keep status as-is (idempotent enqueue)
                created.append(rec)
                continue
            rec.status = "IN_QUEUE"
            rec.message = None
            rec.updated_at = now
            rec.processed_at = None
            if tax_id is not None:
                rec.tax_id = tax_id
                rec.client_id = tax_id  # backward compatible
            if client_name is not None:
                rec.client_name = client_name
        else:
            rec = KarbonFilingInstructionJob(
                workitem_id=workitem_id,
                tax_id=tax_id,
                client_name=client_name,
                client_id=tax_id,
                status="IN_QUEUE",
                created_at=now,
                updated_at=now,
                processed_at=None,
            )
            db.add(rec)
        created.append(rec)

    db.commit()
    # Refresh the ones that have PKs now
    for rec in created:
        try:
            db.refresh(rec)
        except Exception:
            pass
    return created


def set_in_progress(
    db: Session,
    workitem_id: str,
    tax_id: Optional[str] = None,
    client_name: Optional[str] = None,
) -> KarbonFilingInstructionJob:
    """Mark one FI job as IN_PROGRESS (only the currently running record should be IN_PROGRESS)."""
    rec = get_by_workitem_id(db, workitem_id)
    now = datetime.utcnow()
    if rec:
        rec.status = "IN_PROGRESS"
        rec.message = None
        rec.updated_at = now
        rec.processed_at = None
        if tax_id is not None:
            rec.tax_id = tax_id
            rec.client_id = tax_id
        if client_name is not None:
            rec.client_name = client_name
    else:
        rec = KarbonFilingInstructionJob(
            workitem_id=workitem_id,
            tax_id=tax_id,
            client_name=client_name,
            client_id=tax_id,
            status="IN_PROGRESS",
            created_at=now,
            updated_at=now,
            processed_at=None,
        )
        db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def update_status(
    db: Session,
    workitem_id: str,
    status: str,
    message: Optional[str] = None,
    tax_id: Optional[str] = None,
    client_name: Optional[str] = None,
) -> KarbonFilingInstructionJob:
    """Update FI job status. SUCCESS or FAIL only. Stores error message on FAIL."""
    if status not in ("SUCCESS", "FAIL"):
        status = "FAIL"
    # update_job_status knows how to set processed_at for terminal statuses
    update_job_status(db, KarbonFilingInstructionJob, workitem_id, status, message, tax_id)
    # Persist FI-specific extra fields
    rec = get_by_workitem_id(db, workitem_id)
    if rec:
        if tax_id is not None:
            rec.tax_id = tax_id
            rec.client_id = tax_id
        if client_name is not None:
            rec.client_name = client_name
        db.commit()
    return get_by_workitem_id(db, workitem_id)


def clear_in_queue(db: Session) -> int:
    """
    Delete stale FI rows stuck in IN_QUEUE.
    Returns number of deleted rows.
    """
    deleted = (
        db.query(KarbonFilingInstructionJob)
        .filter(KarbonFilingInstructionJob.status == "IN_QUEUE")
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
