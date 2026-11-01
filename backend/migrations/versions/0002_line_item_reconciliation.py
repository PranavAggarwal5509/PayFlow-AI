"""add po_line_allocations and line_item_reconciliations

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-01 13:18:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'po_line_allocations',
        sa.Column('purchase_order_id', sa.Uuid(), nullable=False),
        sa.Column('purchase_order_item_id', sa.Uuid(), nullable=False),
        sa.Column('invoice_id', sa.Uuid(), nullable=False),
        sa.Column('invoice_line_item_id', sa.Uuid(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='ACTIVE'),
        sa.Column('allocated_by', sa.String(length=100), nullable=False, server_default='system'),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_line_item_id'], ['invoice_line_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['purchase_order_item_id'], ['purchase_order_items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invoice_line_item_id', name='uq_po_line_alloc_invoice_line'),
    )
    op.create_index(op.f('ix_po_line_allocations_purchase_order_id'), 'po_line_allocations', ['purchase_order_id'], unique=False)
    op.create_index(op.f('ix_po_line_allocations_purchase_order_item_id'), 'po_line_allocations', ['purchase_order_item_id'], unique=False)
    op.create_index(op.f('ix_po_line_allocations_invoice_id'), 'po_line_allocations', ['invoice_id'], unique=False)
    op.create_index(op.f('ix_po_line_allocations_invoice_line_item_id'), 'po_line_allocations', ['invoice_line_item_id'], unique=False)
    op.create_index('ix_po_line_alloc_item_status', 'po_line_allocations', ['purchase_order_item_id', 'status'], unique=False)
    op.create_index('ix_po_line_alloc_invoice', 'po_line_allocations', ['invoice_id'], unique=False)

    op.create_table(
        'line_item_reconciliations',
        sa.Column('invoice_id', sa.Uuid(), nullable=False),
        sa.Column('invoice_line_item_id', sa.Uuid(), nullable=False),
        sa.Column('purchase_order_item_id', sa.Uuid(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('matching_method', sa.String(length=32), nullable=False),
        sa.Column('matched_description', sa.String(length=500), nullable=True),
        sa.Column('invoice_quantity', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('ordered_quantity', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('allocated_quantity', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('remaining_quantity', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('unit_of_measure', sa.String(length=32), nullable=True),
        sa.Column('invoice_unit_price', sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column('po_unit_price', sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column('price_variance', sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column('expected_line_amount', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('actual_line_amount', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_line_item_id'], ['invoice_line_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['purchase_order_item_id'], ['purchase_order_items.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invoice_line_item_id', name='uq_line_item_recon_invoice_line'),
    )
    op.create_index(op.f('ix_line_item_reconciliations_invoice_id'), 'line_item_reconciliations', ['invoice_id'], unique=False)
    op.create_index(op.f('ix_line_item_reconciliations_invoice_line_item_id'), 'line_item_reconciliations', ['invoice_line_item_id'], unique=False)
    op.create_index(op.f('ix_line_item_reconciliations_purchase_order_item_id'), 'line_item_reconciliations', ['purchase_order_item_id'], unique=False)
    op.create_index('ix_line_recon_invoice', 'line_item_reconciliations', ['invoice_id'], unique=False)
    op.create_index('ix_line_recon_po_item', 'line_item_reconciliations', ['purchase_order_item_id'], unique=False)


def downgrade() -> None:
    op.drop_table('line_item_reconciliations')
    op.drop_table('po_line_allocations')

