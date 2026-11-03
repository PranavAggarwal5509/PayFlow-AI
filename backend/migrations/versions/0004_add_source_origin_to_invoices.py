"""add source_origin to invoices (LIVE_UPLOAD vs SEED_HISTORY)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-01 16:32:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add source_origin column with default 'LIVE_UPLOAD'
    op.add_column(
        'invoices',
        sa.Column('source_origin', sa.String(length=32), nullable=False, server_default='LIVE_UPLOAD')
    )
    op.create_index('ix_invoices_source_origin', 'invoices', ['source_origin'])


def downgrade() -> None:
    op.drop_index('ix_invoices_source_origin', table_name='invoices')
    op.drop_column('invoices', 'source_origin')
