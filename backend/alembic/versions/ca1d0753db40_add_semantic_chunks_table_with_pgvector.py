"""add_semantic_chunks_table_with_pgvector

Revision ID: ca1d0753db40
Revises: f07849e7f461
Create Date: 2026-09-13 20:11:19.986700

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


# revision identifiers, used by Alembic.
revision: str = 'ca1d0753db40'
down_revision: Union[str, None] = 'f07849e7f461'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create ChunkType enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE chunktype AS ENUM ('symbol', 'api_endpoint', 'documentation', 'file');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create semantic_chunks table
    op.create_table('semantic_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('analysis_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('symbol_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('api_endpoint_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('chunk_type', postgresql.ENUM('symbol', 'api_endpoint', 'documentation', 'file', name='chunktype', create_type=False), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('language', sa.String(length=100), nullable=True),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['analysis_run_id'], ['analysis_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['symbol_id'], ['symbols.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['api_endpoint_id'], ['api_endpoints.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('analysis_run_id', 'content_hash', 'chunk_index', name='uq_semantic_chunks_analysis_run_hash_index')
    )
    
    # Add vector column with dimension 384 (default for all-MiniLM-L6-v2)
    # Using raw SQL to add pgvector column type
    op.execute('ALTER TABLE semantic_chunks ADD COLUMN embedding vector(384)')
    
    # Create indexes
    op.create_index('idx_semantic_chunks_repository_id', 'semantic_chunks', ['repository_id'])
    op.create_index('idx_semantic_chunks_analysis_run_id', 'semantic_chunks', ['analysis_run_id'])
    op.create_index('idx_semantic_chunks_file_id', 'semantic_chunks', ['file_id'])
    op.create_index('idx_semantic_chunks_symbol_id', 'semantic_chunks', ['symbol_id'])
    op.create_index('idx_semantic_chunks_api_endpoint_id', 'semantic_chunks', ['api_endpoint_id'])
    op.create_index('idx_semantic_chunks_chunk_type', 'semantic_chunks', ['chunk_type'])
    op.create_index('idx_semantic_chunks_content_hash', 'semantic_chunks', ['content_hash'])
    
    # Create vector index for similarity search using HNSW (Hierarchical Navigable Small World)
    # This is an approximate nearest neighbor index for efficient similarity search
    # cosine distance is used as the distance metric
    op.execute(
        'CREATE INDEX idx_semantic_chunks_embedding ON semantic_chunks '
        'USING hnsw (embedding vector_cosine_ops)'
    )


def downgrade() -> None:
    # Drop table and indexes (indexes will be dropped automatically with table)
    op.drop_table('semantic_chunks')
    
    # Drop ChunkType enum
    op.execute('DROP TYPE IF EXISTS chunktype')
    
    # Note: We don't drop the vector extension as other tables might use it
    # If you want to drop it, uncomment the following line:
    # op.execute('DROP EXTENSION IF EXISTS vector')
