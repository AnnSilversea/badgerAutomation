"""Add FI queue status fields and metadata

Revision ID: 003
Revises: 002
Create Date: 2026-03-11

- Adds tax_id and client_name to karbon_filing_instruction_jobs
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "karbon_filing_instruction_jobs",
        sa.Column("tax_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "karbon_filing_instruction_jobs",
        sa.Column("client_name", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_karbon_filing_instruction_jobs_tax_id",
        "karbon_filing_instruction_jobs",
        ["tax_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_karbon_filing_instruction_jobs_tax_id",
        table_name="karbon_filing_instruction_jobs",
    )
    op.drop_column("karbon_filing_instruction_jobs", "client_name")
    op.drop_column("karbon_filing_instruction_jobs", "tax_id")

