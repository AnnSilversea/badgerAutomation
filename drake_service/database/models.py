"""SQLAlchemy models for Service B database tables."""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID

from drake_service.database.session import Base

# Efile Status job statuses (CLIENT_NOT_FOUND is not a failure)
EFILE_STATUS_VALUES = (
    "NOT_STARTED",
    "IN_QUEUE",
    "IN_PROCESSING",
    "PROCESSING",
    "SUCCESS",
    "FAIL",
    "CLIENT_NOT_FOUND",
    "MISSING_TAX_ID",
    "AGENCY_ACCEPTED",
    "AGENCY_REJECTED",
)

# Filing Instruction job statuses
FI_STATUS_VALUES = ("IN_QUEUE", "IN_PROGRESS", "SUCCESS", "FAIL")

OCR_TAX_RETURN_STATUS_VALUES = ("EXTRACTED", "EXTRACTED_FAIL")


class KarbonEfileStatusJob(Base):
    """Tracks processing status of automation jobs that push Efile Status to Karbon."""

    __tablename__ = "karbon_efile_status_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workitem_id = Column(String(255), unique=True, nullable=False, index=True)
    client_id = Column(String(255), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="NOT_STARTED")
    message = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)


class KarbonFilingInstructionJob(Base):
    """Tracks processing status of automation jobs that push Filing Instruction to Karbon."""

    __tablename__ = "karbon_filing_instruction_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workitem_id = Column(String(255), unique=True, nullable=False, index=True)
    # tax_id is the Drake client identifier (often EIN/SSN) used to locate the client in Drake
    tax_id = Column(String(255), nullable=True, index=True)
    client_name = Column(String(255), nullable=True)
    # Backward compatible field (historically used to store tax id)
    client_id = Column(String(255), nullable=True, index=True)
    status = Column(String(50), nullable=False)
    message = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)


# Backward compatibility alias
AutomationWorkitem = KarbonEfileStatusJob


class OcrTaxReturnResult(Base):
    """Tracks final OCR tax return extraction result per tax_id."""

    __tablename__ = "ocr_tax_return_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tax_id = Column(String(255), unique=True, nullable=False, index=True)
    client_name = Column(String(255), nullable=True)
    # Relative path like: outputs/999999998_Ann_Test
    outputs_parent_folder = Column(String(500), nullable=False)
    # EXTRACTED | EXTRACTED_FAIL
    ocr_status = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
