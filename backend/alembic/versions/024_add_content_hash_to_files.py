"""add content_hash to files

Revision ID: 024_add_content_hash
Revises: 023_add_test_results
Create Date: 2026-10-25

Phase 24: Repository Intelligence Quality & Analysis Reliability

Add content_hash column to files table for change detection.
This enables incremental analysis by detecting which files have actually changed.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '024_add_content_hash'
down_revision = 'e8a3f9d2b1c7'
branch_labels = None
depends_on = None


def upgrade():
    """Add content_hash column to files table."""
    op.add_column('files', sa.Column('content_hash', sa.String(length=64), nullable=True))
    
    # Add index for lookups
    op.create_index(op.f('idx_files_content_hash'), 'files', ['content_hash'], unique=False)


def downgrade():
    """Remove content_hash column from files table."""
    op.drop_index(op.f('idx_files_content_hash'), table_name='files')
    op.drop_column('files', 'content_hash')
