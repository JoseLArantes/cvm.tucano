"""add_updates_service_tables

Revision ID: f0be02acfa0a
Revises: 20260616_003
Create Date: 2026-06-19 19:57:22.702445
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f0be02acfa0a'
down_revision: str | None = '20260616_003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('update_sessions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('session_key', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_update_sessions_session_key'), 'update_sessions', ['session_key'], unique=True)
    
    op.create_table('pending_updates',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('fonte', sa.String(length=50), nullable=False),
    sa.Column('ano', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('detection_timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_probe_timestamp', sa.DateTime(timezone=True), nullable=True),
    sa.Column('analysis_timestamp', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolved_timestamp', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolved_by', sa.String(length=64), nullable=True),
    sa.Column('probe_etag', sa.String(length=255), nullable=True),
    sa.Column('probe_last_modified', sa.String(length=255), nullable=True),
    sa.Column('probe_content_length', sa.BigInteger(), nullable=True),
    sa.Column('artifact_url', sa.String(length=1000), nullable=False),
    sa.Column('change_type', sa.String(length=32), nullable=True),
    sa.Column('change_summary', sa.JSON(), nullable=True),
    sa.Column('last_successful_run_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['last_successful_run_id'], ['ingestion_runs.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pending_updates_ano'), 'pending_updates', ['ano'], unique=False)
    op.create_index(op.f('ix_pending_updates_fonte'), 'pending_updates', ['fonte'], unique=False)
    op.create_index(op.f('ix_pending_updates_status'), 'pending_updates', ['status'], unique=False)
    
    op.create_table('pending_update_members',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('pending_update_id', sa.Uuid(), nullable=False),
    sa.Column('member_name', sa.String(length=255), nullable=False),
    sa.Column('member_role', sa.String(length=50), nullable=True),
    sa.Column('previous_member_sha256', sa.String(length=64), nullable=True),
    sa.Column('current_member_sha256', sa.String(length=64), nullable=True),
    sa.Column('previous_row_count', sa.Integer(), nullable=True),
    sa.Column('current_row_count', sa.Integer(), nullable=True),
    sa.Column('previous_header_hash', sa.String(length=64), nullable=True),
    sa.Column('current_header_hash', sa.String(length=64), nullable=True),
    sa.Column('change_category', sa.String(length=32), nullable=False),
    sa.Column('change_details', sa.JSON(), nullable=True),
    sa.Column('row_kind', sa.String(length=50), nullable=True),
    sa.Column('is_required', sa.Boolean(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['pending_update_id'], ['pending_updates.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pending_update_members_member_name'), 'pending_update_members', ['member_name'], unique=False)
    op.create_index(op.f('ix_pending_update_members_pending_update_id'), 'pending_update_members', ['pending_update_id'], unique=False)
    
    op.create_table('update_session_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('pending_update_id', sa.Uuid(), nullable=False),
    sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('action', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['pending_update_id'], ['pending_updates.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['session_id'], ['update_sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_update_session_items_pending_update_id'), 'update_session_items', ['pending_update_id'], unique=False)
    op.create_index(op.f('ix_update_session_items_session_id'), 'update_session_items', ['session_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_update_session_items_session_id'), table_name='update_session_items')
    op.drop_index(op.f('ix_update_session_items_pending_update_id'), table_name='update_session_items')
    op.drop_table('update_session_items')
    
    op.drop_index(op.f('ix_pending_update_members_pending_update_id'), table_name='pending_update_members')
    op.drop_index(op.f('ix_pending_update_members_member_name'), table_name='pending_update_members')
    op.drop_table('pending_update_members')
    
    op.drop_index(op.f('ix_pending_updates_status'), table_name='pending_updates')
    op.drop_index(op.f('ix_pending_updates_fonte'), table_name='pending_updates')
    op.drop_index(op.f('ix_pending_updates_ano'), table_name='pending_updates')
    op.drop_table('pending_updates')
    
    op.drop_index(op.f('ix_update_sessions_session_key'), table_name='update_sessions')
    op.drop_table('update_sessions')
