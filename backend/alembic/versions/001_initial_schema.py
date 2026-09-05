"""Initial schema with repositories, analysis_runs, files, symbols, imports, calls, relationships

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-04 20:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types (only if they don't exist)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE analysisstatus AS ENUM ('pending', 'running', 'completed', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE symboltype AS ENUM ('function', 'class', 'method', 'arrow_function', 'interface');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE relationshiptype AS ENUM ('contains', 'imports', 'calls');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create repositories table
    op.create_table('repositories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('owner', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=511), nullable=False),
        sa.Column('github_url', sa.String(length=1024), nullable=False),
        sa.Column('default_branch', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('language', sa.String(length=100), nullable=True),
        sa.Column('stars', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('full_name')
    )
    op.create_index('idx_repositories_full_name', 'repositories', ['full_name'])
    op.create_index('idx_repositories_owner', 'repositories', ['owner'])
    
    # Create analysis_runs table
    op.create_table('analysis_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'completed', 'failed', name='analysisstatus', create_type=False), nullable=False),
        sa.Column('total_files', sa.Integer(), nullable=True),
        sa.Column('analyzed_files', sa.Integer(), nullable=True),
        sa.Column('total_symbols', sa.Integer(), nullable=True),
        sa.Column('total_imports', sa.Integer(), nullable=True),
        sa.Column('total_calls', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_analysis_runs_repository_id', 'analysis_runs', ['repository_id'])
    op.create_index('idx_analysis_runs_status', 'analysis_runs', ['status'])
    op.create_index('idx_analysis_runs_started_at', 'analysis_runs', ['started_at'])
    
    # Create files table
    op.create_table('files',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('analysis_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('path', sa.String(length=1024), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('extension', sa.String(length=50), nullable=True),
        sa.Column('language', sa.String(length=100), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('line_count', sa.Integer(), nullable=True),
        sa.Column('is_sensitive', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['analysis_run_id'], ['analysis_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('analysis_run_id', 'path', name='uq_files_analysis_run_path')
    )
    op.create_index('idx_files_repository_id', 'files', ['repository_id'])
    op.create_index('idx_files_analysis_run_id', 'files', ['analysis_run_id'])
    op.create_index('idx_files_path', 'files', ['path'])
    op.create_index('idx_files_language', 'files', ['language'])
    
    # Create symbols table
    op.create_table('symbols',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('analysis_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('symbol_type', postgresql.ENUM('function', 'class', 'method', 'arrow_function', 'interface', name='symboltype', create_type=False), nullable=False),
        sa.Column('language', sa.String(length=100), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('parent_symbol_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['analysis_run_id'], ['analysis_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_symbol_id'], ['symbols.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_symbols_file_id', 'symbols', ['file_id'])
    op.create_index('idx_symbols_analysis_run_id', 'symbols', ['analysis_run_id'])
    op.create_index('idx_symbols_name', 'symbols', ['name'])
    op.create_index('idx_symbols_type', 'symbols', ['symbol_type'])
    op.create_index('idx_symbols_parent_symbol_id', 'symbols', ['parent_symbol_id'])
    
    # Create imports table
    op.create_table('imports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('analysis_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(length=1024), nullable=False),
        sa.Column('imported_names', sa.Text(), nullable=True),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['analysis_run_id'], ['analysis_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_imports_file_id', 'imports', ['file_id'])
    op.create_index('idx_imports_analysis_run_id', 'imports', ['analysis_run_id'])
    op.create_index('idx_imports_source', 'imports', ['source'])
    
    # Create calls table
    op.create_table('calls',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('analysis_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('caller_name', sa.String(length=255), nullable=False),
        sa.Column('callee_name', sa.String(length=255), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['analysis_run_id'], ['analysis_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_calls_file_id', 'calls', ['file_id'])
    op.create_index('idx_calls_analysis_run_id', 'calls', ['analysis_run_id'])
    op.create_index('idx_calls_caller_name', 'calls', ['caller_name'])
    op.create_index('idx_calls_callee_name', 'calls', ['callee_name'])
    
    # Create relationships table
    op.create_table('relationships',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('analysis_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('relationship_type', postgresql.ENUM('contains', 'imports', 'calls', name='relationshiptype', create_type=False), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('target_name', sa.String(length=1024), nullable=True),
        sa.ForeignKeyConstraint(['analysis_run_id'], ['analysis_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_relationships_analysis_run_id', 'relationships', ['analysis_run_id'])
    op.create_index('idx_relationships_type', 'relationships', ['relationship_type'])
    op.create_index('idx_relationships_source', 'relationships', ['source_type', 'source_id'])
    op.create_index('idx_relationships_target', 'relationships', ['target_type', 'target_id'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('relationships')
    op.drop_table('calls')
    op.drop_table('imports')
    op.drop_table('symbols')
    op.drop_table('files')
    op.drop_table('analysis_runs')
    op.drop_table('repositories')
    
    # Drop enum types
    op.execute('DROP TYPE relationshiptype')
    op.execute('DROP TYPE symboltype')
    op.execute('DROP TYPE analysisstatus')
