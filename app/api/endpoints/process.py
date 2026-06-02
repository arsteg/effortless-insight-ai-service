"""
Notice processing endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from uuid import UUID
import structlog

from app.core.database import get_db
from app.services.ocr_service import OCRService
from app.services.llm_service import LLMService
from app.services.embedding_service import EmbeddingService

router = APIRouter()
logger = structlog.get_logger()


class ProcessNoticeRequest(BaseModel):
    """Request model for notice processing"""
    notice_id: UUID
    file_url: str
    callback_url: str | None = None


class ProcessNoticeResponse(BaseModel):
    """Response model for notice processing"""
    success: bool
    notice_id: UUID
    risk_score: int | None = None
    risk_level: str | None = None
    summary_en: str | None = None
    summary_hi: str | None = None
    plain_english: str | None = None
    notice_metadata: dict | None = None
    action_items: list[dict] | None = None
    required_documents: list[dict] | None = None
    legal_references: list[dict] | None = None
    confidence_scores: dict | None = None
    processing_time_ms: int | None = None
    error: str | None = None


class GenerateResponseRequest(BaseModel):
    """Request model for response generation"""
    notice_id: UUID
    context: dict | None = None


class SimilarNoticesRequest(BaseModel):
    """Request model for finding similar notices"""
    notice_id: UUID
    limit: int = 5


@router.post("/notice", response_model=ProcessNoticeResponse)
async def process_notice(
    request: ProcessNoticeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Process a GST notice:
    1. OCR extraction
    2. Entity extraction
    3. Classification
    4. Risk assessment
    5. Summary generation
    6. Action item generation
    """
    import time
    start_time = time.time()

    logger.info("Processing notice", notice_id=str(request.notice_id))

    try:
        # Initialize services
        ocr_service = OCRService()
        llm_service = LLMService()
        embedding_service = EmbeddingService()

        # Step 1: OCR extraction
        logger.info("Starting OCR extraction", notice_id=str(request.notice_id))
        ocr_result = await ocr_service.extract_text(request.file_url)

        if not ocr_result.success:
            raise HTTPException(status_code=400, detail=f"OCR failed: {ocr_result.error}")

        # Step 2: LLM Analysis (entity extraction, classification, summary, etc.)
        logger.info("Starting LLM analysis", notice_id=str(request.notice_id))
        analysis_result = await llm_service.analyze_notice(
            text=ocr_result.text,
            notice_id=request.notice_id
        )

        # Step 3: Generate embeddings for RAG
        logger.info("Generating embeddings", notice_id=str(request.notice_id))
        await embedding_service.store_notice_embedding(
            notice_id=request.notice_id,
            text=ocr_result.text,
            metadata=analysis_result.metadata
        )

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(
            "Notice processing completed",
            notice_id=str(request.notice_id),
            processing_time_ms=processing_time,
            risk_score=analysis_result.risk_score
        )

        return ProcessNoticeResponse(
            success=True,
            notice_id=request.notice_id,
            risk_score=analysis_result.risk_score,
            risk_level=analysis_result.risk_level,
            summary_en=analysis_result.summary_en,
            summary_hi=analysis_result.summary_hi,
            plain_english=analysis_result.plain_english,
            notice_metadata=analysis_result.metadata,
            action_items=analysis_result.action_items,
            required_documents=analysis_result.required_documents,
            legal_references=analysis_result.legal_references,
            confidence_scores=analysis_result.confidence_scores,
            processing_time_ms=processing_time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Notice processing failed", notice_id=str(request.notice_id), error=str(e))
        return ProcessNoticeResponse(
            success=False,
            notice_id=request.notice_id,
            error=str(e)
        )


@router.post("/generate-response")
async def generate_response(
    request: GenerateResponseRequest,
    db: AsyncSession = Depends(get_db)
):
    """Generate a draft response for a notice"""
    logger.info("Generating response draft", notice_id=str(request.notice_id))

    try:
        llm_service = LLMService()
        response_draft = await llm_service.generate_response_draft(
            notice_id=request.notice_id,
            context=request.context
        )

        return {
            "success": True,
            "notice_id": request.notice_id,
            "draft": response_draft
        }

    except Exception as e:
        logger.error("Response generation failed", notice_id=str(request.notice_id), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/similar")
async def find_similar_notices(
    request: SimilarNoticesRequest,
    db: AsyncSession = Depends(get_db)
):
    """Find similar notices using vector similarity search"""
    logger.info("Finding similar notices", notice_id=str(request.notice_id), limit=request.limit)

    try:
        embedding_service = EmbeddingService()
        similar = await embedding_service.find_similar_notices(
            notice_id=request.notice_id,
            limit=request.limit
        )

        return {
            "success": True,
            "notice_id": request.notice_id,
            "similar_notices": similar
        }

    except Exception as e:
        logger.error("Similar notice search failed", notice_id=str(request.notice_id), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
