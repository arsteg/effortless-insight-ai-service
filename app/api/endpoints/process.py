"""
Notice processing endpoints - matching .NET IAiServiceClient interface
"""

import time
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.schemas.requests import (
    ProcessNoticeRequest,
    GenerateResponseRequest,
    SimilarNoticesRequest,
)
from app.schemas.responses import (
    AiProcessingResult,
    GenerateResponseResponse,
    SimilarNoticesResponse,
    SimilarNotice,
)
from app.services.pipeline.orchestrator import PipelineOrchestrator
from app.services.rag.vector_store import VectorStore
from app.services.llm.analyzer import NoticeAnalyzer
from app.api.middleware.metrics import (
    record_processing_complete,
    record_risk_score,
    increment_active_jobs,
    decrement_active_jobs,
)

router = APIRouter()
logger = structlog.get_logger()


@router.post("/notice", response_model=AiProcessingResult)
async def process_notice(
    request: ProcessNoticeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Process a GST notice through the AI pipeline.

    This endpoint is called by the .NET API after receiving a notice upload.
    It runs the full 8-stage pipeline:
    1. Preprocessing - Download and quality check
    2. OCR - Extract text using Google Document AI / Azure
    3. Entity Extraction - GSTIN, dates, amounts
    4. Classification - Notice type and category
    5. RAG Retrieval - Fetch relevant context
    6. LLM Analysis - Comprehensive analysis
    7. Verification - Fact check and hallucination detection
    8. Report Generation - Assemble final report

    Request body:
    - noticeId: UUID of the notice
    - fileUrl: Presigned S3 URL (30-min validity)
    - organizationId: Optional organization scope
    - priority: Processing priority (low, normal, high)

    Returns:
    - success: Whether processing succeeded
    - error: Error message if failed
    - report: Full AI analysis report
    """
    logger.info(
        "Processing notice request",
        notice_id=str(request.notice_id),
        priority=request.priority
    )

    increment_active_jobs()

    try:
        # Initialize pipeline
        pipeline = PipelineOrchestrator()

        # Run pipeline
        result = await pipeline.process(
            notice_id=request.notice_id,
            file_url=request.file_url,
            organization_id=request.organization_id,
            priority=request.priority or "normal",
        )

        # Record metrics
        record_processing_complete(result.success)
        if result.success and result.report:
            record_risk_score(result.report.risk_score)

        logger.info(
            "Notice processing complete",
            notice_id=str(request.notice_id),
            success=result.success,
            risk_score=result.report.risk_score if result.report else None
        )

        return result

    except Exception as e:
        logger.error(
            "Notice processing failed",
            notice_id=str(request.notice_id),
            error=str(e)
        )
        record_processing_complete(False)
        return AiProcessingResult(
            success=False,
            error=str(e)
        )

    finally:
        decrement_active_jobs()


@router.post("/generate-response", response_model=GenerateResponseResponse)
async def generate_response(
    request: GenerateResponseRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a draft response for a GST notice.

    This endpoint generates a professional draft response that can be
    used as a starting point for responding to the tax authority.

    Request body:
    - noticeId: UUID of the notice
    - context: Additional context for response generation
    - tone: Response tone (formal, conciliatory, assertive)
    - includeCaseLaw: Whether to include case law citations

    Returns:
    - success: Whether generation succeeded
    - draft: Generated draft response text
    """
    logger.info(
        "Generating response draft",
        notice_id=str(request.notice_id)
    )

    try:
        analyzer = NoticeAnalyzer()

        # Fetch notice details from database
        notice_data = await _fetch_notice_details(db, request.notice_id)

        # Build context from database and request
        context_parts = []
        if request.context:
            context_parts.append(str(request.context))

        # Use notice data from database if available
        notice_summary = "Notice requiring response"
        notice_type = request.context.get("notice_type") if request.context else None
        deadline = request.context.get("deadline") if request.context else None
        key_issues = request.context.get("issues") if request.context else None

        if notice_data:
            if notice_data.get("summary"):
                notice_summary = notice_data["summary"]
            if notice_data.get("notice_type") and not notice_type:
                notice_type = notice_data["notice_type"]
            if notice_data.get("response_deadline") and not deadline:
                deadline = notice_data["response_deadline"]
            if notice_data.get("key_issues"):
                context_parts.append(f"Key Issues: {notice_data['key_issues']}")
            if notice_data.get("ai_report_summary"):
                context_parts.append(f"AI Analysis: {notice_data['ai_report_summary']}")

        context_str = "\n".join(context_parts) if context_parts else ""

        draft = await analyzer.generate_response_draft(
            notice_summary=notice_summary,
            notice_type=notice_type,
            deadline=deadline,
            key_issues=key_issues,
            context=context_str,
        )

        return GenerateResponseResponse(
            success=True,
            draft=draft
        )

    except Exception as e:
        logger.error(
            "Response generation failed",
            notice_id=str(request.notice_id),
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


async def _fetch_notice_details(db: AsyncSession, notice_id: UUID) -> dict | None:
    """
    Fetch notice details from database for response generation.

    Returns notice summary, type, deadline, and AI report details.
    """
    try:
        from sqlalchemy import text

        query = text("""
            SELECT
                n.notice_number,
                n.notice_type,
                n.notice_category,
                n.status,
                n.response_deadline,
                n.total_demand,
                n.gstin,
                ar.summary_en as ai_report_summary,
                ar.plain_english,
                ar.risk_level
            FROM notices n
            LEFT JOIN ai_reports ar ON ar.notice_id = n.id
            WHERE n.id = :notice_id
            LIMIT 1
        """)

        result = await db.execute(query, {"notice_id": str(notice_id)})
        row = result.fetchone()

        if not row:
            logger.warning("Notice not found in database", notice_id=str(notice_id))
            return None

        return {
            "notice_number": row.notice_number,
            "notice_type": row.notice_type,
            "notice_category": row.notice_category,
            "status": row.status,
            "response_deadline": str(row.response_deadline) if row.response_deadline else None,
            "total_demand": float(row.total_demand) if row.total_demand else None,
            "gstin": row.gstin,
            "summary": row.ai_report_summary or row.plain_english,
            "ai_report_summary": row.ai_report_summary,
            "risk_level": row.risk_level,
        }

    except Exception as e:
        logger.warning(
            "Failed to fetch notice details from database",
            notice_id=str(notice_id),
            error=str(e)
        )
        return None


@router.post("/similar", response_model=SimilarNoticesResponse)
async def find_similar_notices(
    request: SimilarNoticesRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Find notices similar to a given notice using vector similarity search.

    Uses pgvector to find semantically similar notices based on their
    embedded content. Useful for finding precedents and similar cases.

    Request body:
    - noticeId: UUID of the notice to find similar to
    - organizationId: Optional scope to organization's notices
    - limit: Number of similar notices to return (1-20)

    Returns:
    - success: Whether search succeeded
    - noticeId: Original notice ID
    - similarNotices: List of similar notices with scores
    """
    logger.info(
        "Finding similar notices",
        notice_id=str(request.notice_id),
        limit=request.limit
    )

    try:
        vector_store = VectorStore()

        results = await vector_store.find_similar_notices(
            notice_id=request.notice_id,
            organization_id=request.organization_id,
            limit=request.limit,
        )

        similar_notices = [
            SimilarNotice(
                notice_id=UUID(r["source_id"]),
                similarity_score=r["similarity"],
                notice_type=r.get("metadata", {}).get("notice_type"),
                summary=r.get("content", "")[:200] + "..." if len(r.get("content", "")) > 200 else r.get("content", "")
            )
            for r in results
        ]

        return SimilarNoticesResponse(
            success=True,
            notice_id=request.notice_id,
            similar_notices=similar_notices
        )

    except Exception as e:
        logger.error(
            "Similar notice search failed",
            notice_id=str(request.notice_id),
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))
