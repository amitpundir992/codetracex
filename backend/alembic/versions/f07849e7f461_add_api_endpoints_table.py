"""add_api_endpoints_table

Revision ID: f07849e7f461
Revises: cc4df58d955d
Create Date: 2026-09-10 11:18:27.813457

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f07849e7f461'
down_revision: Union[str, None] = 'cc4df58d955d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create HTTP method enum type (only if it doesn't exist)
    http_method_enum = sa.Enum(
        'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD',
        name='httpmethod'
    )
    
    # Create api_endpoints table
    op.create_table(
        'api_endpoints',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=False),
        sa.Column('analysis_run_id', sa.UUID(), nullable=False),
        sa.Column('file_id', sa.UUID(), nullable=False),
        sa.Column('symbol_id', sa.UUID(), nullable=True),
        sa.Column('method', http_method_enum, nullable=False),
        sa.Column('path', sa.String(length=1024), nullable=False),
        sa.Column('framework', sa.String(length=50), nullable=False),
        sa.Column('handler_name', sa.String(length=255), nullable=True),
        sa.Column('start_line', sa.Integer(), nullable=True),
        sa.Column('end_line', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['analysis_run_id'], ['analysis_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['symbol_id'], ['symbols.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('analysis_run_id', 'method', 'path', name='uq_api_endpoints_analysis_run_method_path')
    )
    
    # Create indexes
    op.create_index('idx_api_endpoints_repository_id', 'api_endpoints', ['repository_id'])
    op.create_index('idx_api_endpoints_analysis_run_id', 'api_endpoints', ['analysis_run_id'])
    op.create_index('idx_api_endpoints_file_id', 'api_endpoints', ['file_id'])
    op.create_index('idx_api_endpoints_symbol_id', 'api_endpoints', ['symbol_id'])
    op.create_index('idx_api_endpoints_method', 'api_endpoints', ['method'])
    op.create_index('idx_api_endpoints_framework', 'api_endpoints', ['framework'])
    op.create_index('idx_api_endpoints_path', 'api_endpoints', ['path'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_api_endpoints_path', 'api_endpoints')
    op.drop_index('idx_api_endpoints_framework', 'api_endpoints')
    op.drop_index('idx_api_endpoints_method', 'api_endpoints')
    op.drop_index('idx_api_endpoints_symbol_id', 'api_endpoints')
    op.drop_index('idx_api_endpoints_file_id', 'api_endpoints')
    op.drop_index('idx_api_endpoints_analysis_run_id', 'api_endpoints')
    op.drop_index('idx_api_endpoints_repository_id', 'api_endpoints')
    
    # Drop table
    op.drop_table('api_endpoints')
    
    # Note: We don't drop the httpmethod enum type as it may be used by other tables
