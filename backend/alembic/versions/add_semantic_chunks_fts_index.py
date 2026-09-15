"""add semantic chunks full-text search index

Revision ID: a7b3c9d2e5f1
Revises: ca1d0753db40
Create Date: 2026-09-15

Phase 10: Hybrid Retrieval

This migration adds PostgreSQL full-text search capabilities to semantic_chunks:
- Adds tsvector column for full-text indexing
- Creates GIN index for efficient text search
- Creates trigger to automatically update tsvector on content changes

Strategy:
- Index the 'content' field which contains code, documentation, and API details
- Use english text search configuration
- GIN index provides fast keyword matching
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b3c9d2e5f1'
down_revision: Union[str, None] = 'ca1d0753db40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add full-text search support to semantic_chunks table.
    """
    # Add tsvector column for full-text search
    # This column stores the pre-computed text search vector
    op.execute("""
        ALTER TABLE semantic_chunks
        ADD COLUMN content_tsv tsvector
    """)
    
    # Populate the tsvector column with existing data
    # We use 'english' text search configuration
    # The tsvector is generated from the 'content' column
    op.execute("""
        UPDATE semantic_chunks
        SET content_tsv = to_tsvector('english', content)
    """)
    
    # Create GIN index for fast full-text search
    # GIN (Generalized Inverted Index) is ideal for full-text search
    op.execute("""
        CREATE INDEX idx_semantic_chunks_content_tsv
        ON semantic_chunks
        USING GIN(content_tsv)
    """)
    
    # Create trigger function to auto-update tsvector when content changes
    # This ensures the index stays synchronized with content
    op.execute("""
        CREATE FUNCTION semantic_chunks_content_tsv_trigger() RETURNS trigger AS $$
        BEGIN
            NEW.content_tsv := to_tsvector('english', NEW.content);
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
    """)
    
    # Create trigger that fires on INSERT or UPDATE
    op.execute("""
        CREATE TRIGGER tsvector_update_trigger
        BEFORE INSERT OR UPDATE ON semantic_chunks
        FOR EACH ROW
        EXECUTE FUNCTION semantic_chunks_content_tsv_trigger()
    """)


def downgrade() -> None:
    """
    Remove full-text search support.
    """
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS tsvector_update_trigger ON semantic_chunks")
    
    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS semantic_chunks_content_tsv_trigger()")
    
    # Drop index
    op.execute("DROP INDEX IF EXISTS idx_semantic_chunks_content_tsv")
    
    # Drop column
    op.execute("ALTER TABLE semantic_chunks DROP COLUMN IF EXISTS content_tsv")
