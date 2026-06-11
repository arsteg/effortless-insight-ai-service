"""create processing_jobs table

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'processing_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('notice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('current_stage', sa.String(50), nullable=True),

        # Stage timings (milliseconds)
        sa.Column('preprocessing_time_ms', sa.Integer(), nullable=True),
        sa.Column('ocr_time_ms', sa.Integer(), nullable=True),
        sa.Column('entity_extraction_time_ms', sa.Integer(), nullable=True),
        sa.Column('classification_time_ms', sa.Integer(), nullable=True),
        sa.Column('rag_retrieval_time_ms', sa.Integer(), nullable=True),
        sa.Column('llm_analysis_time_ms', sa.Integer(), nullable=True),
        sa.Column('verification_time_ms', sa.Integer(), nullable=True),
        sa.Column('report_generation_time_ms', sa.Integer(), nullable=True),
        sa.Column('total_time_ms', sa.Integer(), nullable=True),

        # OCR details
        sa.Column('ocr_provider', sa.String(50), nullable=True),
        sa.Column('ocr_confidence', sa.Float(), nullable=True),
        sa.Column('ocr_page_count', sa.Integer(), nullable=True),
        sa.Column('ocr_text_length', sa.Integer(), nullable=True),

        # LLM details
        sa.Column('llm_model', sa.String(100), nullable=True),
        sa.Column('llm_input_tokens', sa.Integer(), nullable=True),
        sa.Column('llm_output_tokens', sa.Integer(), nullable=True),
        sa.Column('llm_total_cost', sa.Float(), nullable=True),

        # Result
        sa.Column('result', postgresql.JSONB(), nullable=True),

        # Error tracking
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('error_stage', sa.String(50), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),

        # Input data
        sa.Column('file_url', sa.Text(), nullable=True),
        sa.Column('file_type', sa.String(50), nullable=True),

        # Extracted raw text
        sa.Column('raw_text', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_processing_jobs_notice_id', 'processing_jobs', ['notice_id'], unique=True)
    op.create_index('ix_processing_jobs_organization_id', 'processing_jobs', ['organization_id'])
    op.create_index('ix_processing_jobs_status', 'processing_jobs', ['status'])


def downgrade() -> None:
    op.drop_table('processing_jobs')
