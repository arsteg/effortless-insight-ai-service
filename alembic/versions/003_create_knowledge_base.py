"""create knowledge_base_entries table

Revision ID: 003
Revises: 002
Create Date: 2024-01-01 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'knowledge_base_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('reference', sa.String(255), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('effective_date', sa.Date(), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('authority', sa.String(255), nullable=True),
        sa.Column('keywords', postgresql.ARRAY(sa.String()), nullable=False, default=[]),
        sa.Column('categories', postgresql.ARRAY(sa.String()), nullable=False, default=[]),
        sa.Column('related_sections', postgresql.ARRAY(sa.String()), nullable=False, default=[]),
        sa.Column('related_rules', postgresql.ARRAY(sa.String()), nullable=False, default=[]),
        sa.Column('supersedes', sa.String(255), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, default=dict),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_indexed', sa.Boolean(), nullable=False, default=False),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_kb_source_type', 'knowledge_base_entries', ['source_type'])
    op.create_index('ix_kb_reference', 'knowledge_base_entries', ['reference'], unique=True)
    op.create_index('ix_kb_is_active', 'knowledge_base_entries', ['is_active'])
    op.create_index('ix_kb_is_indexed', 'knowledge_base_entries', ['is_indexed'])
    op.create_index('ix_kb_source_active', 'knowledge_base_entries', ['source_type', 'is_active'])


def downgrade() -> None:
    op.drop_table('knowledge_base_entries')
