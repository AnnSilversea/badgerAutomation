"""create automation_workitems table

Revision ID: 001
Revises: 
Create Date: 2026-03-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'automation_workitems',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('permakey', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('message', sa.String(length=1000), nullable=True),
        sa.Column('triggered_by', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('permakey')
    )
    op.create_index('ix_automation_workitems_permakey', 'automation_workitems', ['permakey'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_automation_workitems_permakey', table_name='automation_workitems')
    op.drop_table('automation_workitems')
