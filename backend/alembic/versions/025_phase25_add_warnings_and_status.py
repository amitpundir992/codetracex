"""Phase 25: Add warnings column and completed_with_warnings status

Revision ID: 025_phase25_warnings
Revises: 024_add_content_hash
Create Date: 2026-11-07

Phase 25: Operational Reliability & Automated Recovery

Changes:
1. Add 'warnings' TEXT column to analysis_runs for tracking partial failures
2. Add 'completed_with_warnings' to AnalysisStatus enum

Migration Strategy:
- warnings column is nullable for backward compatibility
- New enum value added (PostgreSQL supports ALTER TYPE ... ADD VALUE)
- Existing completed_with_warnings data handled gracefully

Backward Compatibility:
- Old analysis runs: warnings = NULL (no warnings)
- New analysis runs: warnings = NULL or JSON list of warnings
- Status completed_with_warnings is new, old clients may not recognize it
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '025_phase25_warnings'
down_revision = '024_add_content_hash'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add warnings tracking and new status for partial failures.
    """
    # Add warnings column to analysis_runs
    op.add_column(
        'analysis_runs',
        sa.Column('warnings', sa.Text(), nullable=True)
    )
    
    # Add new enum value 'completed_with_warnings' to analysisstatus
    # PostgreSQL requires a raw SQL command for ALTER TYPE ... ADD VALUE
    # This is safe and backward-compatible
    op.execute(
        "ALTER TYPE analysisstatus ADD VALUE IF NOT EXISTS 'completed_with_warnings'"
    )


def downgrade():
    """
    Remove warnings column and status (dangerous, data loss).
    
    WARNING: This will:
    1. Drop the warnings column (data loss)
    2. Analysis runs with status=completed_with_warnings will become invalid
    
    Recommended approach before downgrade:
    1. Ensure no analysis runs have status=completed_with_warnings
    2. Or migrate them to status=completed
    """
    # Drop warnings column
    op.drop_column('analysis_runs', 'warnings')
    
    # Note: Cannot safely remove enum value from PostgreSQL
    # Removing an enum value requires recreating the entire type
    # This would require:
    # 1. Create new enum without the value
    # 2. Alter column to use new enum
    # 3. Drop old enum
    # This is complex and risky, so we leave the enum value in place
    # 
    # If absolutely necessary, manually run:
    # ALTER TYPE analysisstatus RENAME TO analysisstatus_old;
    # CREATE TYPE analysisstatus AS ENUM ('queued', 'pending', 'running', 'completed', 'failed', 'cancelled');
    # ALTER TABLE analysis_runs ALTER COLUMN status TYPE analysisstatus USING status::text::analysisstatus;
    # DROP TYPE analysisstatus_old;
