"""add status to integrations

Revision ID: b1c2d3e4f5a6
Revises: a3055c0686f2
Create Date: 2026-03-02 20:37:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a3055c0686f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('integrations', sa.Column('status', sa.String(length=20), nullable=False, server_default='stable'))


def downgrade() -> None:
    op.drop_column('integrations', 'status')
