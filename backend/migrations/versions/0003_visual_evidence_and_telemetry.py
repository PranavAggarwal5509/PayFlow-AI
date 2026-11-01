"""add visual_evidence to invoices and token telemetry to processing_runs

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-01 14:24:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add visual_evidence JSON column to invoices
    op.add_column('invoices', sa.Column('visual_evidence', sa.JSON(), nullable=True))

    # 2. Add AI telemetry columns to processing_runs
    op.add_column('processing_runs', sa.Column('llm_model', sa.String(length=64), nullable=True))
    op.add_column('processing_runs', sa.Column('prompt_tokens', sa.Integer(), nullable=True))
    op.add_column('processing_runs', sa.Column('completion_tokens', sa.Integer(), nullable=True))
    op.add_column('processing_runs', sa.Column('total_tokens', sa.Integer(), nullable=True))
    op.add_column('processing_runs', sa.Column('extraction_duration_ms', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('processing_runs', 'extraction_duration_ms')
    op.drop_column('processing_runs', 'total_tokens')
    op.drop_column('processing_runs', 'completion_tokens')
    op.drop_column('processing_runs', 'prompt_tokens')
    op.drop_column('processing_runs', 'llm_model')
    op.drop_column('invoices', 'visual_evidence')

