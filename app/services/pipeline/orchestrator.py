"""
Pipeline orchestrator for notice processing
"""

import time
from typing import Optional
from uuid import UUID
from datetime import datetime
import structlog

from app.schemas.internal import (
    PipelineContext, OCROutput, EntityExtractionOutput,
    ClassificationOutput, RAGContext, AnalysisOutput, VerificationOutput
)
from app.schemas.report import AIReport
from app.schemas.responses import AiProcessingResult, AiReportData

from app.services.pipeline.preprocessor import Preprocessor
from app.services.pipeline.report_generator import ReportGenerator
from app.services.ocr.ocr_service import OCRService
from app.services.extraction.entity_extractor import EntityExtractor
from app.services.llm.classifier import NoticeClassifier
from app.services.llm.analyzer import NoticeAnalyzer
from app.services.rag.retriever import RAGRetriever
from app.services.verification.verifier import Verifier
from app.services.scoring.risk_scorer import RiskScorer

logger = structlog.get_logger()


class PipelineOrchestrator:
    """
    8-Stage Pipeline Orchestrator for Notice Processing

    Stages:
    1. Preprocessor (~5s) - Download, detect format, assess quality
    2. OCRProcessor (~15s) - Google Document AI / Azure fallback
    3. EntityExtractor (~5s) - GSTIN, dates, amounts, sections
    4. NoticeClassifier (~3s) - LLM classification
    5. RAGRetriever (~5s) - Vector search, context retrieval
    6. LLMAnalyzer (~20s) - GPT-4 structured analysis
    7. Verifier (~5s) - Fact check, hallucination detection
    8. ReportGenerator (~2s) - Assemble final report

    Target: <60 seconds total
    """

    def __init__(self):
        self.preprocessor = Preprocessor()
        self.ocr_service = OCRService()
        self.entity_extractor = EntityExtractor()
        self.classifier = NoticeClassifier()
        self.rag_retriever = RAGRetriever()
        self.analyzer = NoticeAnalyzer()
        self.verifier = Verifier()
        self.risk_scorer = RiskScorer()
        self.report_generator = ReportGenerator()

    async def process(
        self,
        notice_id: UUID,
        file_url: str,
        organization_id: Optional[UUID] = None,
        priority: str = "normal",
    ) -> AiProcessingResult:
        """
        Run the full processing pipeline

        Args:
            notice_id: UUID of the notice
            file_url: Presigned S3 URL
            organization_id: Optional organization scope
            priority: Processing priority

        Returns:
            AiProcessingResult with success status and report
        """
        start_time = time.time()

        logger.info(
            "Starting pipeline processing",
            notice_id=str(notice_id),
            priority=priority
        )

        # Initialize context
        context = PipelineContext(
            notice_id=notice_id,
            organization_id=organization_id,
            file_url=file_url,
            priority=priority,
            start_time=datetime.utcnow(),
        )

        try:
            # Stage 1: Preprocessing
            context = await self._stage_preprocessing(context)
            if context.failed:
                return self._create_error_result(context)

            # Stage 2: OCR
            context = await self._stage_ocr(context)
            if context.failed:
                return self._create_error_result(context)

            # Stage 3: Entity Extraction
            context = await self._stage_entity_extraction(context)
            if context.failed:
                return self._create_error_result(context)

            # Stage 4: Classification
            context = await self._stage_classification(context)
            # Non-fatal - continue even if classification fails

            # Stage 5: RAG Retrieval
            context = await self._stage_rag_retrieval(context)
            # Non-fatal - continue even if RAG fails

            # Stage 6: LLM Analysis
            context = await self._stage_llm_analysis(context)
            if context.failed:
                return self._create_error_result(context)

            # Stage 7: Verification
            context = await self._stage_verification(context)
            # Non-fatal - continue even if verification has issues

            # Stage 8: Report Generation
            report = await self._stage_report_generation(context)

            # Calculate total time
            total_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "Pipeline processing complete",
                notice_id=str(notice_id),
                total_time_ms=total_time_ms,
                risk_score=report.risk_score
            )

            return AiProcessingResult(
                success=True,
                report=report.to_ai_report_data(),
            )

        except Exception as e:
            logger.error(
                "Pipeline processing failed",
                notice_id=str(notice_id),
                error=str(e),
                stage=context.current_stage
            )
            return AiProcessingResult(
                success=False,
                error=str(e),
            )

    async def _stage_preprocessing(self, context: PipelineContext) -> PipelineContext:
        """Stage 1: Preprocessing"""
        logger.info("Stage 1: Preprocessing", notice_id=str(context.notice_id))
        return await self.preprocessor.process(context)

    async def _stage_ocr(self, context: PipelineContext) -> PipelineContext:
        """Stage 2: OCR Processing"""
        logger.info("Stage 2: OCR", notice_id=str(context.notice_id))
        start_time = time.time()
        context.current_stage = "ocr"

        try:
            # Get document content from preprocessing
            content = getattr(context, '_document_content', None)
            mime_type = getattr(context, '_mime_type', 'application/pdf')

            if content is None:
                # Re-download if needed
                result = await self.ocr_service.extract_text(context.file_url)
            else:
                result = await self.ocr_service.extract_from_bytes(content, mime_type)

            if not result.success:
                context.mark_failed("ocr", result.error or "OCR failed")
                return context

            context.ocr_output = OCROutput(
                success=True,
                text=result.text,
                confidence=result.confidence,
                provider=result.provider,
                page_count=result.page_count,
                tables=result.tables,
                page_confidences=result.page_confidences,
                page_texts=result.page_texts,
            )
            context.raw_text = result.text

            duration_ms = int((time.time() - start_time) * 1000)
            context.record_stage_time("ocr", duration_ms)

            logger.info(
                "OCR complete",
                notice_id=str(context.notice_id),
                text_length=len(result.text),
                confidence=result.confidence,
                duration_ms=duration_ms
            )

            return context

        except Exception as e:
            context.mark_failed("ocr", str(e))
            return context

    async def _stage_entity_extraction(self, context: PipelineContext) -> PipelineContext:
        """Stage 3: Entity Extraction"""
        logger.info("Stage 3: Entity Extraction", notice_id=str(context.notice_id))
        start_time = time.time()
        context.current_stage = "entity_extraction"

        try:
            entities = await self.entity_extractor.extract(context.raw_text)

            context.entity_output = EntityExtractionOutput(
                success=True,
                entities=entities,
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

            duration_ms = int((time.time() - start_time) * 1000)
            context.record_stage_time("entity_extraction", duration_ms)

            logger.info(
                "Entity extraction complete",
                notice_id=str(context.notice_id),
                gstins=len(entities.gstins),
                dates=len(entities.dates),
                amounts=len(entities.amounts),
                duration_ms=duration_ms
            )

            return context

        except Exception as e:
            context.mark_failed("entity_extraction", str(e))
            return context

    async def _stage_classification(self, context: PipelineContext) -> PipelineContext:
        """Stage 4: Classification"""
        logger.info("Stage 4: Classification", notice_id=str(context.notice_id))
        start_time = time.time()
        context.current_stage = "classification"

        try:
            result = await self.classifier.classify(context.raw_text)

            context.classification_output = result

            duration_ms = int((time.time() - start_time) * 1000)
            context.record_stage_time("classification", duration_ms)

            logger.info(
                "Classification complete",
                notice_id=str(context.notice_id),
                type=result.notice_type,
                category=result.notice_category,
                duration_ms=duration_ms
            )

            return context

        except Exception as e:
            logger.warning("Classification failed", error=str(e))
            context.classification_output = ClassificationOutput(
                success=False,
                error=str(e)
            )
            return context

    async def _stage_rag_retrieval(self, context: PipelineContext) -> PipelineContext:
        """Stage 5: RAG Retrieval"""
        logger.info("Stage 5: RAG Retrieval", notice_id=str(context.notice_id))
        start_time = time.time()
        context.current_stage = "rag_retrieval"

        try:
            # Get notice type and sections for better retrieval
            notice_type = None
            sections = []

            if context.classification_output and context.classification_output.success:
                notice_type = context.classification_output.notice_type

            if context.entity_output and context.entity_output.entities:
                sections = [s.reference for s in context.entity_output.entities.sections]

            result = await self.rag_retriever.retrieve_for_notice(
                notice_text=context.raw_text,
                notice_type=notice_type,
                sections=sections,
                organization_id=context.organization_id,
            )

            context.rag_context = result

            duration_ms = int((time.time() - start_time) * 1000)
            context.record_stage_time("rag_retrieval", duration_ms)

            logger.info(
                "RAG retrieval complete",
                notice_id=str(context.notice_id),
                contexts_retrieved=result.total_retrieved,
                duration_ms=duration_ms
            )

            return context

        except Exception as e:
            logger.warning("RAG retrieval failed", error=str(e))
            context.rag_context = RAGContext(success=False, error=str(e))
            return context

    async def _stage_llm_analysis(self, context: PipelineContext) -> PipelineContext:
        """Stage 6: LLM Analysis"""
        logger.info("Stage 6: LLM Analysis", notice_id=str(context.notice_id))
        start_time = time.time()
        context.current_stage = "llm_analysis"

        try:
            result = await self.analyzer.analyze(
                notice_text=context.raw_text,
                rag_context=context.rag_context,
                include_hindi=True,
            )

            if not result.success:
                context.mark_failed("llm_analysis", result.error or "Analysis failed")
                return context

            # Adjust risk score using rule-based scorer for consistency
            entities = context.entity_output.entities if context.entity_output else None
            if entities:
                risk_assessment = self.risk_scorer.calculate_risk(
                    entities=entities,
                    notice_type=context.classification_output.notice_type if context.classification_output else None,
                    notice_category=context.classification_output.notice_category if context.classification_output else None,
                )
                # Use average of LLM and rule-based scores
                result.risk_score = (result.risk_score + risk_assessment.score) // 2
                result.risk_level = self.risk_scorer._score_to_level(result.risk_score)

            context.analysis_output = result

            duration_ms = int((time.time() - start_time) * 1000)
            context.record_stage_time("llm_analysis", duration_ms)

            logger.info(
                "LLM analysis complete",
                notice_id=str(context.notice_id),
                risk_score=result.risk_score,
                duration_ms=duration_ms
            )

            return context

        except Exception as e:
            context.mark_failed("llm_analysis", str(e))
            return context

    async def _stage_verification(self, context: PipelineContext) -> PipelineContext:
        """Stage 7: Verification"""
        logger.info("Stage 7: Verification", notice_id=str(context.notice_id))
        start_time = time.time()
        context.current_stage = "verification"

        try:
            # Build LLM output dict for verification
            llm_output = {
                "summary_en": context.analysis_output.summary_en,
                "metadata": {},  # Will be filled from analysis
                "action_items": context.analysis_output.action_items,
                "legal_references": context.analysis_output.legal_references,
                "confidence_scores": context.analysis_output.confidence_scores,
            }

            result = await self.verifier.verify(
                original_text=context.raw_text,
                entities=context.entity_output.entities if context.entity_output else None,
                llm_output=llm_output,
                ocr_confidence=context.ocr_output.confidence if context.ocr_output else 0.95,
            )

            context.verification_output = result

            duration_ms = int((time.time() - start_time) * 1000)
            context.record_stage_time("verification", duration_ms)

            logger.info(
                "Verification complete",
                notice_id=str(context.notice_id),
                verified=result.verification.is_verified if result.verification else False,
                issues=len(result.verification.issues) if result.verification else 0,
                duration_ms=duration_ms
            )

            return context

        except Exception as e:
            logger.warning("Verification failed", error=str(e))
            context.verification_output = VerificationOutput(
                success=False,
                error=str(e)
            )
            return context

    async def _stage_report_generation(self, context: PipelineContext) -> AIReport:
        """Stage 8: Report Generation"""
        logger.info("Stage 8: Report Generation", notice_id=str(context.notice_id))
        return await self.report_generator.generate(context)

    def _create_error_result(self, context: PipelineContext) -> AiProcessingResult:
        """Create error result from failed context"""
        return AiProcessingResult(
            success=False,
            error=f"Pipeline failed at {context.current_stage}: {context.error}",
        )
