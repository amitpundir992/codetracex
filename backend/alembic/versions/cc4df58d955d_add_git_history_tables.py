"""add_git_history_tables

Revision ID: cc4df58d955d
Revises: 001_initial_schema
Create Date: 2026-09-07 20:08:21.161530

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc4df58d955d'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ChangeType enum
    op.execute("CREATE TYPE changetype AS ENUM ('added', 'modified', 'deleted', 'renamed')")
    
    # Create commits table
    op.create_table(
        'commits',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=False),
        sa.Column('commit_hash', sa.String(length=40), nullable=False),
        sa.Column('author_name', sa.String(length=255), nullable=False),
        sa.Column('author_email', sa.String(length=255), nullable=False),
        sa.Column('commit_message', sa.Text(), nullable=False),
        sa.Column('committed_at', sa.DateTime(), nullable=False),
        sa.Column('parent_hashes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_id', 'commit_hash', name='uq_commits_repository_hash')
    )
    
    # Create indexes for commits table
    op.create_index('idx_commits_repository_id', 'commits', ['repository_id'])
    op.create_index('idx_commits_commit_hash', 'commits', ['commit_hash'])
    op.create_index('idx_commits_committed_at', 'commits', ['committed_at'])
    op.create_index('idx_commits_author_email', 'commits', ['author_email'])
    
    # Create commit_file_changes table (using the existing changetype enum)
    op.execute("""
        CREATE TABLE commit_file_changes (
            id UUID NOT NULL PRIMARY KEY,
            commit_id UUID NOT NULL REFERENCES commits(id) ON DELETE CASCADE,
            file_id UUID REFERENCES files(id) ON DELETE SET NULL,
            path VARCHAR(1024) NOT NULL,
            change_type changetype NOT NULL,
            additions INTEGER,
            deletions INTEGER,
            old_path VARCHAR(1024),
            new_path VARCHAR(1024),
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        )
    """)
    
    # Create indexes for commit_file_changes table
    op.create_index('idx_commit_file_changes_commit_id', 'commit_file_changes', ['commit_id'])
    op.create_index('idx_commit_file_changes_file_id', 'commit_file_changes', ['file_id'])
    op.create_index('idx_commit_file_changes_path', 'commit_file_changes', ['path'])


def downgrade() -> None:
    # Drop commit_file_changes table and indexes
    op.drop_index('idx_commit_file_changes_path', table_name='commit_file_changes')
    op.drop_index('idx_commit_file_changes_file_id', table_name='commit_file_changes')
    op.drop_index('idx_commit_file_changes_commit_id', table_name='commit_file_changes')
    op.execute("DROP TABLE commit_file_changes")
    
    # Drop commits table and indexes
    op.drop_index('idx_commits_author_email', table_name='commits')
    op.drop_index('idx_commits_committed_at', table_name='commits')
    op.drop_index('idx_commits_commit_hash', table_name='commits')
    op.drop_index('idx_commits_repository_id', table_name='commits')
    op.drop_table('commits')
    
    # Drop ChangeType enum
    op.execute("DROP TYPE changetype")
