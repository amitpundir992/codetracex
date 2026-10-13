"""Phase 20: Add test results tables (test_runs, test_cases)

Revision ID: e8a3f9d2b1c7
Revises: 4f6d82e5ebcc
Create Date: 2026-10-13 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = 'e8a3f9d2b1c7'
down_revision = '4f6d82e5ebcc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types for test results
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE testrunstatus AS ENUM ('imported', 'processing', 'completed', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE testoutcome AS ENUM ('passed', 'failed', 'skipped', 'error');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE failureclassification AS ENUM (
                'assertion', 'import_error', 'setup_error', 'timeout',
                'dependency_error', 'network_error', 'unknown'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create test_runs table
    op.create_table(
        'test_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('commit_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('analysis_run_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        sa.Column('source_format', sa.String(length=50), nullable=False),
        sa.Column('content_fingerprint', sa.String(length=64), nullable=False),
        
        sa.Column('status', postgresql.ENUM(
            'imported', 'processing', 'completed', 'failed',
            name='testrunstatus',
            create_type=False
        ), nullable=False),
        
        sa.Column('total_tests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('passed_tests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_tests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skipped_tests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_tests', sa.Integer(), nullable=False, server_default='0'),
        
        sa.Column('total_duration_ms', sa.BigInteger(), nullable=True),
        
        sa.Column('report_metadata', sa.Text(), nullable=True),
        
        sa.Column('imported_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['commit_id'], ['commits.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['analysis_run_id'], ['analysis_runs.id'], ondelete='SET NULL'),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_id', 'content_fingerprint', name='uq_test_runs_fingerprint')
    )
    
    # Create indexes for test_runs
    op.create_index('idx_test_runs_repository_id', 'test_runs', ['repository_id'])
    op.create_index('idx_test_runs_commit_id', 'test_runs', ['commit_id'])
    op.create_index('idx_test_runs_imported_at', 'test_runs', ['imported_at'])
    op.create_index('idx_test_runs_status', 'test_runs', ['status'])
    
    # Create test_cases table
    op.create_table(
        'test_cases',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('test_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        sa.Column('suite_name', sa.String(length=500), nullable=False),
        sa.Column('test_name', sa.String(length=500), nullable=False),
        sa.Column('class_name', sa.String(length=500), nullable=True),
        sa.Column('full_name', sa.String(length=1500), nullable=False),
        
        sa.Column('outcome', postgresql.ENUM(
            'passed', 'failed', 'skipped', 'error',
            name='testoutcome',
            create_type=False
        ), nullable=False),
        sa.Column('duration_ms', sa.BigInteger(), nullable=True),
        
        # Failure information
        sa.Column('failure_message', sa.Text(), nullable=True),
        sa.Column('failure_type', sa.String(length=500), nullable=True),
        sa.Column('failure_stacktrace', sa.Text(), nullable=True),
        
        # Classification
        sa.Column('failure_classification', postgresql.ENUM(
            'assertion', 'import_error', 'setup_error', 'timeout',
            'dependency_error', 'network_error', 'unknown',
            name='failureclassification',
            create_type=False
        ), nullable=True),
        sa.Column('classification_confidence', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('classification_evidence', sa.Text(), nullable=True),
        
        sa.Column('test_metadata', sa.Text(), nullable=True),
        
        sa.ForeignKeyConstraint(['test_run_id'], ['test_runs.id'], ondelete='CASCADE'),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('test_run_id', 'full_name', name='uq_test_cases_run_full_name')
    )
    
    # Create indexes for test_cases
    op.create_index('idx_test_cases_test_run_id', 'test_cases', ['test_run_id'])
    op.create_index('idx_test_cases_outcome', 'test_cases', ['outcome'])
    op.create_index('idx_test_cases_classification', 'test_cases', ['failure_classification'])
    op.create_index('idx_test_cases_full_name', 'test_cases', ['full_name'])


def downgrade() -> None:
    # Drop tables
    op.drop_table('test_cases')
    op.drop_table('test_runs')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS failureclassification')
    op.execute('DROP TYPE IF EXISTS testoutcome')
    op.execute('DROP TYPE IF EXISTS testrunstatus')
