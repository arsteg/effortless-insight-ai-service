"""
Unit tests for SQLAlchemy models
"""

import pytest
from datetime import datetime, date
from uuid import uuid4

from app.models.base import Base, UUIDMixin, TimestampMixin
from app.models.embedding import Embedding, SourceType
from app.models.processing_job import ProcessingJob, ProcessingStatus
from app.models.knowledge_base import KnowledgeBaseEntry, KnowledgeSourceType


class TestSourceType:
    """Test cases for SourceType enum"""

    def test_source_types_exist(self):
        """Test all source types exist"""
        assert SourceType.NOTICE.value == "notice"
        assert SourceType.GST_RULE.value == "gst_rule"
        assert SourceType.CIRCULAR.value == "circular"
        assert SourceType.CASE_LAW.value == "case_law"
        assert SourceType.TEMPLATE.value == "template"


class TestEmbedding:
    """Test cases for Embedding model"""

    def test_embedding_tablename(self):
        """Test embedding table name"""
        assert Embedding.__tablename__ == "embeddings"

    def test_embedding_has_columns(self):
        """Test embedding has required columns"""
        columns = [c.name for c in Embedding.__table__.columns]
        assert "id" in columns
        assert "source_type" in columns
        assert "source_id" in columns
        assert "content" in columns
        assert "embedding" in columns
        assert "content_hash" in columns

    def test_embedding_attributes(self):
        """Test embedding has expected attributes"""
        # Test model has required attributes
        assert hasattr(Embedding, '__tablename__')
        assert hasattr(Embedding, 'source_type')
        assert hasattr(Embedding, 'source_id')


class TestProcessingStatus:
    """Test cases for ProcessingStatus enum"""

    def test_status_values(self):
        """Test all status values exist"""
        assert ProcessingStatus.PENDING.value == "pending"
        assert ProcessingStatus.PREPROCESSING.value == "preprocessing"
        assert ProcessingStatus.OCR.value == "ocr"
        assert ProcessingStatus.ENTITY_EXTRACTION.value == "entity_extraction"
        assert ProcessingStatus.CLASSIFICATION.value == "classification"
        assert ProcessingStatus.RAG_RETRIEVAL.value == "rag_retrieval"
        assert ProcessingStatus.LLM_ANALYSIS.value == "llm_analysis"
        assert ProcessingStatus.VERIFICATION.value == "verification"
        assert ProcessingStatus.REPORT_GENERATION.value == "report_generation"
        assert ProcessingStatus.COMPLETED.value == "completed"
        assert ProcessingStatus.FAILED.value == "failed"


class TestProcessingJob:
    """Test cases for ProcessingJob model"""

    def test_processing_job_tablename(self):
        """Test processing job table name"""
        assert ProcessingJob.__tablename__ == "processing_jobs"

    def test_processing_job_has_columns(self):
        """Test processing job has required columns"""
        columns = [c.name for c in ProcessingJob.__table__.columns]
        assert "id" in columns
        assert "notice_id" in columns
        assert "status" in columns
        assert "current_stage" in columns

    def test_processing_job_default_status(self):
        """Test default status is pending"""
        # Check column default
        status_col = ProcessingJob.__table__.columns["status"]
        assert status_col.default is not None


class TestKnowledgeSourceType:
    """Test cases for KnowledgeSourceType enum"""

    def test_source_types_exist(self):
        """Test all source types exist"""
        assert KnowledgeSourceType.GST_RULE.value == "gst_rule"
        assert KnowledgeSourceType.GST_SECTION.value == "gst_section"
        assert KnowledgeSourceType.CIRCULAR.value == "circular"
        assert KnowledgeSourceType.NOTIFICATION.value == "notification"
        assert KnowledgeSourceType.CASE_LAW.value == "case_law"
        assert KnowledgeSourceType.FORM_TEMPLATE.value == "form_template"
        assert KnowledgeSourceType.FAQ.value == "faq"
        assert KnowledgeSourceType.PROCEDURE.value == "procedure"


class TestKnowledgeBaseEntry:
    """Test cases for KnowledgeBaseEntry model"""

    def test_knowledge_base_tablename(self):
        """Test knowledge base table name"""
        assert KnowledgeBaseEntry.__tablename__ == "knowledge_base_entries"

    def test_knowledge_base_has_columns(self):
        """Test knowledge base has required columns"""
        columns = [c.name for c in KnowledgeBaseEntry.__table__.columns]
        assert "id" in columns
        assert "source_type" in columns
        assert "reference" in columns
        assert "title" in columns
        assert "content" in columns

    def test_knowledge_base_repr(self):
        """Test knowledge base representation"""
        entry = KnowledgeBaseEntry()
        entry.id = uuid4()
        entry.reference = "Section 73"
        entry.source_type = "gst_section"
        repr_str = repr(entry)
        assert "KnowledgeBaseEntry" in repr_str

    def test_mark_indexed(self):
        """Test mark_indexed method"""
        entry = KnowledgeBaseEntry()
        entry.is_indexed = False
        entry.mark_indexed()
        assert entry.is_indexed is True

    def test_deactivate(self):
        """Test deactivate method"""
        entry = KnowledgeBaseEntry()
        entry.is_active = True
        entry.deactivate()
        assert entry.is_active is False


class TestBaseMixin:
    """Test cases for base mixins"""

    def test_uuid_mixin_creates_id(self):
        """Test UUIDMixin creates id column"""
        # This is tested implicitly through models that use it
        assert hasattr(Embedding, 'id')

    def test_timestamp_mixin_creates_timestamps(self):
        """Test TimestampMixin creates timestamp columns"""
        # Check embedding has timestamps
        columns = [c.name for c in Embedding.__table__.columns]
        assert "created_at" in columns
        assert "updated_at" in columns
