"""Refactor to karbon_efile_status_jobs and add karbon_filing_instruction_jobs

Revision ID: 002
Revises: 001
Create Date: 2026-03-05

- Renames automation_workitems -> karbon_efile_status_jobs
- Renames permakey->workitem_id, completed_at->processed_at; adds client_id; drops triggered_by, started_at
- Creates karbon_filing_instruction_jobs table
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename table
    op.rename_table("automation_workitems", "karbon_efile_status_jobs")

    # 2. Rename columns
    op.alter_column(
        "karbon_efile_status_jobs",
        "permakey",
        new_column_name="workitem_id",
    )
    op.alter_column(
        "karbon_efile_status_jobs",
        "completed_at",
        new_column_name="processed_at",
    )

    # 3. Add client_id
    op.add_column(
        "karbon_efile_status_jobs",
        sa.Column("client_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_karbon_efile_status_jobs_client_id",
        "karbon_efile_status_jobs",
        ["client_id"],
        unique=False,
    )

    # 4. Drop old index and constraint, create new
    op.drop_index("ix_automation_workitems_permakey", table_name="karbon_efile_status_jobs")
    op.drop_constraint(
        "automation_workitems_permakey_key",
        "karbon_efile_status_jobs",
        type_="unique",
    )
    op.create_index(
        "ix_karbon_efile_status_jobs_workitem_id",
        "karbon_efile_status_jobs",
        ["workitem_id"],
        unique=True,
    )

    # 5. Drop old columns
    op.drop_column("karbon_efile_status_jobs", "triggered_by")
    op.drop_column("karbon_efile_status_jobs", "started_at")

    # 6. Create karbon_filing_instruction_jobs
    op.create_table(
        "karbon_filing_instruction_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workitem_id", sa.String(length=255), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workitem_id", name="karbon_filing_instruction_jobs_workitem_id_key"),
    )
    op.create_index(
        "ix_karbon_filing_instruction_jobs_workitem_id",
        "karbon_filing_instruction_jobs",
        ["workitem_id"],
        unique=True,
    )
    op.create_index(
        "ix_karbon_filing_instruction_jobs_client_id",
        "karbon_filing_instruction_jobs",
        ["client_id"],
        unique=False,
    )


def downgrade() -> None:
    # 1. Drop karbon_filing_instruction_jobs
    op.drop_index(
        "ix_karbon_filing_instruction_jobs_client_id",
        table_name="karbon_filing_instruction_jobs",
    )
    op.drop_index(
        "ix_karbon_filing_instruction_jobs_workitem_id",
        table_name="karbon_filing_instruction_jobs",
    )
    op.drop_table("karbon_filing_instruction_jobs")

    # 2. Restore karbon_efile_status_jobs columns
    op.add_column(
        "karbon_efile_status_jobs",
        sa.Column("triggered_by", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "karbon_efile_status_jobs",
        sa.Column("started_at", sa.DateTime(), nullable=True),
    )
    op.drop_index(
        "ix_karbon_efile_status_jobs_workitem_id",
        table_name="karbon_efile_status_jobs",
    )
    op.drop_index(
        "ix_karbon_efile_status_jobs_client_id",
        table_name="karbon_efile_status_jobs",
    )
    op.drop_column("karbon_efile_status_jobs", "client_id")
    op.alter_column(
        "karbon_efile_status_jobs",
        "workitem_id",
        new_column_name="permakey",
    )
    op.alter_column(
        "karbon_efile_status_jobs",
        "processed_at",
        new_column_name="completed_at",
    )
    op.create_unique_constraint(
        "automation_workitems_permakey_key",
        "karbon_efile_status_jobs",
        ["permakey"],
    )
    op.create_index(
        "ix_automation_workitems_permakey",
        "karbon_efile_status_jobs",
        ["permakey"],
        unique=True,
    )

    # 3. Rename table back
    op.rename_table("karbon_efile_status_jobs", "automation_workitems")
