"""Reusable helpers for Karbon job tracking."""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session


def update_job_status(
    db: Session,
    model_class,
    workitem_id: str,
    status: str,
    message: Optional[str] = None,
    client_id: Optional[str] = None,
) -> None:
    """
    Create or update a job record with status.
    Sets processed_at for terminal statuses (SUCCESS, FAIL, CLIENT_NOT_FOUND).
    """
    rec = db.query(model_class).filter(model_class.workitem_id == workitem_id).first()
    now = datetime.utcnow()
    # Efile: CLIENT_NOT_FOUND, MISSING_TAX_ID are terminal; FI: only SUCCESS, FAIL
    terminal_statuses = ("SUCCESS", "FAIL", "CLIENT_NOT_FOUND", "MISSING_TAX_ID")
    if status in ("ERROR", "FAILED"):
        status = "FAIL"

    if rec:
        rec.status = status
        rec.updated_at = now
        if message is not None:
            rec.message = message
        if client_id is not None:
            rec.client_id = client_id
        if status in terminal_statuses:
            rec.processed_at = now
    else:
        rec = model_class(
            workitem_id=workitem_id,
            client_id=client_id,
            status=status,
            message=message,
            processed_at=now if status in terminal_statuses else None,
        )
        db.add(rec)
    db.commit()
    db.refresh(rec)
