"""
Knowledge base model for GST rules, circulars, and case law
"""

from enum import Enum
from sqlalchemy import Column, String, Text, Date, Boolean, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from app.models.base import Base, TimestampMixin, UUIDMixin


class KnowledgeSourceType(str, Enum):
    """Types of knowledge base entries"""
    GST_RULE = "gst_rule"
    GST_SECTION = "gst_section"
    CIRCULAR = "circular"
    NOTIFICATION = "notification"
    CASE_LAW = "case_law"
    FORM_TEMPLATE = "form_template"
    FAQ = "faq"
    PROCEDURE = "procedure"


class KnowledgeBaseEntry(Base, UUIDMixin, TimestampMixin):
    """
    Knowledge base entry for GST rules, circulars, case law, etc.

    This is used for RAG retrieval to provide context to the LLM
    during notice analysis.
    """
    __tablename__ = "knowledge_base_entries"

    # Type and identification
    source_type = Column(String(50), nullable=False, index=True)
    reference = Column(String(255), nullable=False, unique=True)  # e.g., "Section 73", "Circular 123/2024"

    # Content
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)

    # Metadata
    effective_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    authority = Column(String(255), nullable=True)  # Issuing authority

    # Categorization
    keywords = Column(ARRAY(String), default=list, nullable=False)
    categories = Column(ARRAY(String), default=list, nullable=False)

    # Related references
    related_sections = Column(ARRAY(String), default=list, nullable=False)
    related_rules = Column(ARRAY(String), default=list, nullable=False)
    supersedes = Column(String(255), nullable=True)  # Reference it supersedes

    # Additional metadata (named extra_data to avoid SQLAlchemy reserved name)
    extra_data = Column("metadata", JSONB, default=dict, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_indexed = Column(Boolean, default=False, nullable=False, index=True)

    # Version tracking
    version = Column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index('ix_kb_source_active', 'source_type', 'is_active'),
        Index('ix_kb_reference', 'reference'),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBaseEntry(id={self.id}, reference={self.reference}, type={self.source_type})>"

    def mark_indexed(self) -> None:
        """Mark the entry as indexed"""
        self.is_indexed = True

    def deactivate(self) -> None:
        """Deactivate the entry"""
        self.is_active = False
