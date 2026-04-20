"""Pydantic schemas for Drake automation API endpoints."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class DrakeLaunchPayload(BaseModel):
    job_id: str
    client_id: str
    data: List[Dict[str, Any]]


class PrintReturnPayload(BaseModel):
    client_id: str
    return_type: str


class EfileBatchPayload(BaseModel):
    client_ids: List[str] = []
    open: bool = True
    close: bool = True


class EfileStatusBatchPayload(BaseModel):
    targets: List[Dict[str, Any]] = []


class FIBatchPayload(BaseModel):
    targets: List[Dict[str, Any]] = []
    close_drake: bool = True


class EfileStatusCheckPayload(BaseModel):
    client_id: str
    client_name: Optional[str] = None
    work_item_key: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    status: str
