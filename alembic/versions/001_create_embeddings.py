"""create embeddings table

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create embeddings table
    op.create_table(
        'embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False, default=0),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(3072), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, default=dict),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_embeddings_source_type', 'embeddings', ['source_type'])
    op.create_index('ix_embeddings_source_id', 'embeddings', ['source_id'])
    op.create_index('ix_embeddings_organization_id', 'embeddings', ['organization_id'])
    op.create_index('ix_embeddings_content_hash', 'embeddings', ['content_hash'])
    op.create_index('ix_embeddings_source', 'embeddings', ['source_type', 'source_id'])
    op.create_index('ix_embeddings_org_source', 'embeddings', ['organization_id', 'source_type'])

    # Create HNSW index for vector similarity search
    op.execute('''
        CREATE INDEX ix_embeddings_embedding_hnsw
        ON embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    ''')


def downgrade() -> None:
    op.drop_table('embeddings')
