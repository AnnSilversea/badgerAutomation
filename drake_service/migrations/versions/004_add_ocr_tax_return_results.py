"""Add OCR tax return results table

Revision ID: 004
Revises: 003
Create Date: 2026-03-11

- Creates ocr_tax_return_results for persisted OCR status per tax_id
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ocr_tax_return_results",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tax_id", sa.String(length=255), nullable=False),
        sa.Column("client_name", sa.String(length=255), nullable=True),
        sa.Column("outputs_parent_folder", sa.String(length=500), nullable=False),
        sa.Column("ocr_status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tax_id", name="uq_ocr_tax_return_results_tax_id"),
    )
    op.create_index(
        "ix_ocr_tax_return_results_tax_id",
        "ocr_tax_return_results",
        ["tax_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ocr_tax_return_results_tax_id", table_name="ocr_tax_return_results")
    op.drop_table("ocr_tax_return_results")

