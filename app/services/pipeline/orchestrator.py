"""
Pipeline orchestrator for notice processing with performance monitoring
"""

import time
from typing import Optional, Dict, List
from uuid import UUID
from datetime import datetime
from dataclasses import dataclass, field
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


@dataclass
class StageMetrics:
    """Metrics for a single pipeline stage"""
    stage_name: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: int = 0
    success: bool = True
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def complete(self, success: bool = True, error: Optional[str] = None, **metadata):
        self.end_time = time.time()
        self.duration_ms = int((self.end_time - self.start_time) * 1000)
        self.success = success
        self.error = error
        self.metadata = metadata


@dataclass
class PipelineMetrics:
    """Aggregated metrics for the entire pipeline run"""
    notice_id: str
    organization_id: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    total_duration_ms: int = 0
    stages: List[StageMetrics] = field(default_factory=list)
    success: bool = True
    error_stage: Optional[str] = None
    error_message: Optional[str] = None

    def add_stage(self, name: str) -> StageMetrics:
        stage = StageMetrics(stage_name=name, start_time=time.time())
        self.stages.append(stage)
        return stage

    def complete(self, success: bool = True, error_stage: Optional[str] = None, error_message: Optional[str] = None):
        self.end_time = time.time()
        self.total_duration_ms = int((self.end_time - self.start_time) * 1000)
        self.success = success
        self.error_stage = error_stage
        self.error_message = error_message

    def to_dict(self) -> Dict:
        return {
            "notice_id": self.notice_id,
            "organization_id": self.organization_id,
            "total_duration_ms": self.total_duration_ms,
            "success": self.success,
            "error_stage": self.error_stage,
            "error_message": self.error_message,
            "stages": [
                {
                    "name": s.stage_name,
                    "duration_ms": s.duration_ms,
                    "success": s.success,
                    "error": s.error,
                    **s.metadata
                }
                for s in self.stages
            ],
            "stage_breakdown": {
                s.stage_name: s.duration_ms for s in self.stages
            }
        }


class MetricsCollector:
    """Collects and exports pipeline metrics"""

    def __init__(self):
        self._recent_metrics: List[PipelineMetrics] = []
        self._max_history = 100

    def record(self, metrics: PipelineMetrics):
        """Record completed pipeline metrics"""
        self._recent_metrics.append(metrics)
        if len(self._recent_metrics) > self._max_history:
            self._recent_metrics = self._recent_metrics[-self._max_history:]

        # Log detailed metrics
        logger.info(
            "pipeline_metrics",
            notice_id=metrics.notice_id,
            total_duration_ms=metrics.total_duration_ms,
            success=metrics.success,
            stages=metrics.to_dict()["stage_breakdown"]
        )

    def get_recent_metrics(self, limit: int = 10) -> List[Dict]:
        """Get recent pipeline metrics"""
        return [m.to_dict() for m in self._recent_metrics[-limit:]]

    def get_average_stage_times(self) -> Dict[str, float]:
        """Calculate average time per stage across recent runs"""
        stage_times: Dict[str, List[int]] = {}
        for metrics in self._recent_metrics:
            for stage in metrics.stages:
                if stage.stage_name not in stage_times:
                    stage_times[stage.stage_name] = []
                stage_times[stage.stage_name].append(stage.duration_ms)

        return {
            name: sum(times) / len(times) if times else 0
            for name, times in stage_times.items()
        }

    def get_success_rate(self) -> float:
        """Calculate overall success rate"""
        if not self._recent_metrics:
            return 1.0
        successful = sum(1 for m in self._recent_metrics if m.success)
        return successful / len(self._recent_metrics)


# Global metrics collector instance
metrics_collector = MetricsCollector()


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
        Run the full processing pipeline with performance monitoring

        Args:
            notice_id: UUID of the notice
            file_url: Presigned S3 URL
            organization_id: Optional organization scope
            priority: Processing priority

        Returns:
            AiProcessingResult with success status and report
        """
        # Initialize metrics
        pipeline_metrics = PipelineMetrics(
            notice_id=str(notice_id),
            organization_id=str(organization_id) if organization_id else None,
            start_time=time.time()
        )

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
            stage = pipeline_metrics.add_stage("preprocessing")
            context = await self._stage_preprocessing(context)
            stage.complete(success=not context.failed, error=context.error if context.failed else None)
            if context.failed:
                pipeline_metrics.complete(False, "preprocessing", context.error)
                metrics_collector.record(pipeline_metrics)
                return self._create_error_result(context)

            # Stage 2: OCR
            stage = pipeline_metrics.add_stage("ocr")
            context = await self._stage_ocr(context)
            stage.complete(
                success=not context.failed,
                error=context.error if context.failed else None,
                text_length=len(context.raw_text) if context.raw_text else 0
            )
            if context.failed:
                pipeline_metrics.complete(False, "ocr", context.error)
                metrics_collector.record(pipeline_metrics)
                return self._create_error_result(context)

            # Stage 3: Entity Extraction
            stage = pipeline_metrics.add_stage("entity_extraction")
            context = await self._stage_entity_extraction(context)
            stage.complete(success=not context.failed, error=context.error if context.failed else None)
            if context.failed:
                pipeline_metrics.complete(False, "entity_extraction", context.error)
                metrics_collector.record(pipeline_metrics)
                return self._create_error_result(context)

            # Stage 4: Classification
            stage = pipeline_metrics.add_stage("classification")
            context = await self._stage_classification(context)
            stage.complete(
                success=context.classification_output.success if context.classification_output else False,
                notice_type=context.classification_output.notice_type if context.classification_output else None
            )
            # Non-fatal - continue even if classification fails

            # Stage 5: RAG Retrieval
            stage = pipeline_metrics.add_stage("rag_retrieval")
            context = await self._stage_rag_retrieval(context)
            stage.complete(
                success=context.rag_context.success if context.rag_context else False,
                contexts_retrieved=context.rag_context.total_retrieved if context.rag_context else 0
            )
            # Non-fatal - continue even if RAG fails

            # Stage 6: LLM Analysis
            stage = pipeline_metrics.add_stage("llm_analysis")
            context = await self._stage_llm_analysis(context)
            stage.complete(success=not context.failed, error=context.error if context.failed else None)
            if context.failed:
                pipeline_metrics.complete(False, "llm_analysis", context.error)
                metrics_collector.record(pipeline_metrics)
                return self._create_error_result(context)

            # Stage 7: Verification
            stage = pipeline_metrics.add_stage("verification")
            context = await self._stage_verification(context)
            stage.complete(
                success=context.verification_output.success if context.verification_output else False,
                verified=context.verification_output.verification.is_verified if context.verification_output and context.verification_output.verification else False
            )
            # Non-fatal - continue even if verification has issues

            # Stage 8: Report Generation
            stage = pipeline_metrics.add_stage("report_generation")
            report = await self._stage_report_generation(context)
            stage.complete(success=True, risk_score=report.risk_score)

            # Complete metrics
            pipeline_metrics.complete(success=True)
            metrics_collector.record(pipeline_metrics)

            logger.info(
                "Pipeline processing complete",
                notice_id=str(notice_id),
                total_duration_ms=pipeline_metrics.total_duration_ms,
                risk_score=report.risk_score,
                stage_timings=pipeline_metrics.to_dict()["stage_breakdown"]
            )

            return AiProcessingResult(
                success=True,
                report=report.to_ai_report_data(),
            )

        except Exception as e:
            pipeline_metrics.complete(False, context.current_stage, str(e))
            metrics_collector.record(pipeline_metrics)

            logger.error(
                "Pipeline processing failed",
                notice_id=str(notice_id),
                error=str(e),
                stage=context.current_stage,
                metrics=pipeline_metrics.to_dict()
            )
            return AiProcessingResult(
                success=False,
                error=str(e),
            )

    def get_metrics(self, limit: int = 10) -> List[Dict]:
        """Get recent pipeline metrics"""
        return metrics_collector.get_recent_metrics(limit)

    def get_average_stage_times(self) -> Dict[str, float]:
        """Get average time per stage"""
        return metrics_collector.get_average_stage_times()

    def get_success_rate(self) -> float:
        """Get pipeline success rate"""
        return metrics_collector.get_success_rate()

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
