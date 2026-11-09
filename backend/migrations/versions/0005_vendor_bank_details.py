"""vendor master bank details (for bank-account change fraud control)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-06 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('vendors', sa.Column('bank_account_number', sa.String(length=34), nullable=True))
    op.add_column('vendors', sa.Column('bank_ifsc', sa.String(length=11), nullable=True))


def downgrade() -> None:
    op.drop_column('vendors', 'bank_ifsc')
    op.drop_column('vendors', 'bank_account_number')
