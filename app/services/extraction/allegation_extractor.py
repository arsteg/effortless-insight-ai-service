"""
Allegation extractor service for point-wise notice analysis

Extracts individual allegations from GST notices using LLM analysis.
"""

import json
import time
from typing import Optional, Dict, Any, List
import structlog

from app.services.llm.client import LLMClient
from app.services.llm.prompts_allegations import AllegationPromptTemplates
from app.services.security.prompt_sanitizer import PromptSanitizer, sanitize_user_input
from app.schemas.allegations import (
    Allegation,
    AllegationResponse,
    AllegationExtractionResult,
    AllegationWiseDraftResponse,
    SupportingDocument,
    CaseLawReference,
)
from app.schemas.responses import GenerateResponseMetadata
from app.core.config import settings

logger = structlog.get_logger()

# Initialize sanitizer for this module
_sanitizer = PromptSanitizer(strict_mode=True)


class AllegationExtractor:
    """
    Extracts and processes allegations from GST notices.

    Provides:
    - Allegation extraction from notice text
    - Per-allegation response generation
    - Combined draft document creation
    """

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()

    async def extract_allegations(
        self,
        notice_text: str,
    ) -> AllegationExtractionResult:
        """
        Extract all allegations from a GST notice.

        Args:
            notice_text: Full OCR text of the notice

        Returns:
            AllegationExtractionResult with list of extracted allegations
        """
        logger.info("Extracting allegations from notice", text_length=len(notice_text))
        start_time = time.time()

        try:
            if not notice_text.strip() or len(notice_text) > settings.analysis_max_chars:
                raise ValueError("Notice text is empty or exceeds the supported extraction length. Please reprocess or split the notice.")

            # Sanitize notice text
            sanitization_result = _sanitizer.sanitize(notice_text, content_type="notice_text")
            if sanitization_result.injection_attempts_detected > 0:
                logger.warning(
                    "Potential prompt injection in notice text during allegation extraction",
                    patterns=sanitization_result.patterns_matched,
                )

            # Never silently drop allegations at the end of a long notice.
            max_chars = settings.analysis_max_chars
            sanitized_text = sanitization_result.sanitized_text
            if len(sanitization_result.sanitized_text) > max_chars:
                raise ValueError("Notice exceeds the supported extraction length; split it into smaller notices before drafting.")

            # Wrap with XML delimiters
            wrapped_text = _sanitizer.wrap_user_content(sanitized_text, label="NOTICE_CONTENT")

            messages = [
                {"role": "system", "content": AllegationPromptTemplates.ALLEGATION_EXTRACTION_SYSTEM},
                {"role": "user", "content": AllegationPromptTemplates.ALLEGATION_EXTRACTION_USER.format(
                    notice_text=wrapped_text,
                )}
            ]

            response = await self.client.complete(
                messages=messages,
                temperature=0.2,
                max_tokens=4000,
                json_mode=True,
            )

            # Parse response
            result = json.loads(response["content"])

            elapsed_ms = int((time.time() - start_time) * 1000)

            # Convert raw allegations to Allegation objects
            allegations = []
            for i, alg_data in enumerate(result.get("allegations", [])):
                try:
                    allegation = Allegation(
                        id=alg_data.get("id", f"ALG-{i+1:03d}"),
                        serial_number=alg_data.get("serial_number", i + 1),
                        description=alg_data.get("description", ""),
                        category=alg_data.get("category", "Other"),
                        legal_provision=alg_data.get("legal_provision"),
                        amount_involved=alg_data.get("amount_involved"),
                        period=alg_data.get("period"),
                        evidence_cited=alg_data.get("evidence_cited", []),
                        page_reference=alg_data.get("page_reference"),
                    )
                    allegations.append(allegation)
                except Exception as e:
                    logger.warning(
                        "Failed to parse allegation",
                        index=i,
                        error=str(e),
                        data=alg_data,
                    )

            if not allegations or len(allegations) != len(result.get("allegations", [])):
                raise ValueError("Could not extract every allegation. Please retry.")
            if len({a.id for a in allegations}) != len(allegations) or any(not a.description.strip() for a in allegations):
                raise ValueError("Extracted allegations have duplicate IDs or empty descriptions.")

            logger.info(
                "Allegation extraction complete",
                count=len(allegations),
                elapsed_ms=elapsed_ms,
                input_tokens=response["input_tokens"],
                output_tokens=response["output_tokens"],
            )

            return AllegationExtractionResult(
                success=True,
                allegations=allegations,
                total_amount=sum(a.amount_involved or 0 for a in allegations),
                metadata=GenerateResponseMetadata(
                    model=response.get("model", "unknown"),
                    input_tokens=response.get("input_tokens", 0),
                    output_tokens=response.get("output_tokens", 0),
                    processing_time_ms=elapsed_ms,
                ),
            )

        except json.JSONDecodeError as e:
            logger.error("Failed to parse allegation extraction response", error=str(e))
            return AllegationExtractionResult(
                success=False,
                error=f"Invalid JSON response: {str(e)}",
            )

        except Exception as e:
            logger.error("Allegation extraction failed", error=str(e))
            return AllegationExtractionResult(
                success=False,
                error=str(e),
            )

    async def generate_allegation_responses(
        self,
        allegations: List[Allegation],
        notice_summary: str,
        notice_type: Optional[str] = None,
        deadline: Optional[str] = None,
        tone: str = "formal",
        language: str = "en",
        taxpayer_context: Optional[Dict[str, Any]] = None,
        allegation_overrides: Optional[Dict[str, str]] = None,
        include_case_law: bool = True,
    ) -> AllegationWiseDraftResponse:
        """
        Generate responses for each allegation.

        Args:
            allegations: List of extracted allegations
            notice_summary: Summary of the notice
            notice_type: Type of notice
            deadline: Response deadline
            tone: Response tone (formal, conciliatory, defensive)
            language: Response language (en, hi)
            taxpayer_context: Additional context about taxpayer's situation
            allegation_overrides: Custom instructions per allegation ID
            include_case_law: Whether to include case law references

        Returns:
            AllegationWiseDraftResponse with per-allegation responses
        """
        logger.info(
            "Generating allegation-wise responses",
            count=len(allegations),
            tone=tone,
            language=language,
        )
        start_time = time.time()

        try:
            # Sanitize inputs
            sanitized_summary = sanitize_user_input(notice_summary or "", content_type="summary")

            # Build taxpayer context string
            taxpayer_context_str = "Not provided"
            if taxpayer_context:
                context_parts = []
                for key, value in taxpayer_context.items():
                    sanitized_value = sanitize_user_input(str(value), content_type="context")
                    context_parts.append(f"- {key}: {sanitized_value}")
                taxpayer_context_str = "\n".join(context_parts)

            # Get tone and language instructions
            tone_instruction = AllegationPromptTemplates.get_tone_instruction(tone)
            language_instruction = AllegationPromptTemplates.get_language_instruction(language)

            # Build allegations JSON for prompt
            allegations_json = json.dumps([
                {
                    "id": alg.id,
                    "serial_number": alg.serial_number,
                    "description": alg.description,
                    "category": alg.category,
                    "legal_provision": alg.legal_provision,
                    "amount_involved": alg.amount_involved,
                    "period": alg.period,
                    "evidence_cited": alg.evidence_cited,
                }
                for alg in allegations
            ], indent=2)

            # Build additional instructions
            additional_instructions = ""
            if not include_case_law:
                additional_instructions += "\nDo NOT include case law references in responses.\n"
            if allegation_overrides:
                additional_instructions += "\nALLEGATION-SPECIFIC INSTRUCTIONS:\n"
                for alg_id, instruction in allegation_overrides.items():
                    sanitized_instruction = sanitize_user_input(instruction, content_type="instructions")
                    additional_instructions += f"- {alg_id}: {sanitized_instruction}\n"

            messages = [
                {"role": "system", "content": AllegationPromptTemplates.ALLEGATION_RESPONSE_SYSTEM},
                {"role": "user", "content": AllegationPromptTemplates.ALLEGATION_RESPONSE_USER.format(
                    notice_summary=sanitized_summary,
                    notice_type=notice_type or "Unknown",
                    deadline=deadline or "Not specified",
                    allegations_json=allegations_json,
                    taxpayer_context=taxpayer_context_str,
                    tone=tone_instruction,
                    language_instruction=language_instruction,
                    additional_instructions=additional_instructions,
                )}
            ]

            response = await self.client.complete(
                messages=messages,
                temperature=0.3,
                max_tokens=8000,  # Larger limit for multiple responses
                json_mode=True,
            )

            # Parse response
            result = json.loads(response["content"])

            elapsed_ms = int((time.time() - start_time) * 1000)

            # Parse allegation responses
            responses = []
            missing_info_summary = []

            for resp_data in result.get("responses", []):
                try:
                    # Parse supporting evidence
                    supporting_evidence = []
                    for doc in resp_data.get("supporting_evidence", []):
                        supporting_evidence.append(SupportingDocument(
                            document_name=doc.get("document_name", ""),
                            document_type=doc.get("document_type", ""),
                            relevance=doc.get("relevance", ""),
                            available=bool(taxpayer_context) and doc.get("available", False),
                        ))

                    # Parse case law references
                    case_law_refs = []
                    for cl in resp_data.get("case_law_references", []):
                        case_law_refs.append(CaseLawReference(
                            citation=cl.get("citation", ""),
                            court=cl.get("court", ""),
                            principle=cl.get("principle", ""),
                            relevance=cl.get("relevance", ""),
                        ))

                    allegation_response = AllegationResponse(
                        allegation_id=resp_data.get("allegation_id", ""),
                        response_text=resp_data.get("response_text", ""),
                        legal_basis=resp_data.get("legal_basis", []),
                        supporting_evidence=supporting_evidence,
                        missing_information=resp_data.get("missing_information", []),
                        case_law_references=case_law_refs if include_case_law else [],
                        confidence=resp_data.get("confidence", 0.5),
                        status=resp_data.get("status", "needs_review"),
                    )
                    responses.append(allegation_response)

                    # Collect missing information
                    for item in allegation_response.missing_information:
                        if item not in missing_info_summary:
                            missing_info_summary.append(
                                f"{item} (Allegation {allegation_response.allegation_id})"
                            )

                except Exception as e:
                    logger.warning(
                        "Failed to parse allegation response",
                        allegation_id=resp_data.get("allegation_id"),
                        error=str(e),
                    )

            expected_ids = {a.id for a in allegations}
            if (len(expected_ids) != len(allegations) or len(responses) != len(allegations)
                    or {r.allegation_id for r in responses} != expected_ids
                    or any(not r.response_text.strip() for r in responses)):
                raise ValueError("AI did not return exactly one non-empty response for every allegation. Please retry.")

            logger.info(
                "Allegation-wise response generation complete",
                response_count=len(responses),
                missing_items=len(missing_info_summary),
                elapsed_ms=elapsed_ms,
            )

            return AllegationWiseDraftResponse(
                success=True,
                allegations=allegations,
                responses=responses,
                combined_draft=result.get("combined_draft"),
                missing_info_summary=missing_info_summary,
                metadata=GenerateResponseMetadata(
                    model=response.get("model", "unknown"),
                    input_tokens=response.get("input_tokens", 0),
                    output_tokens=response.get("output_tokens", 0),
                    processing_time_ms=elapsed_ms,
                ),
            )

        except json.JSONDecodeError as e:
            logger.error("Failed to parse allegation response generation", error=str(e))
            return AllegationWiseDraftResponse(
                success=False,
                error=f"Invalid JSON response: {str(e)}",
                allegations=allegations,
            )

        except Exception as e:
            logger.error("Allegation response generation failed", error=str(e))
            return AllegationWiseDraftResponse(
                success=False,
                error=str(e),
                allegations=allegations,
            )

    async def regenerate_single_response(
        self,
        allegation: Allegation,
        notice_type: Optional[str] = None,
        tone: str = "formal",
        language: str = "en",
        taxpayer_context: Optional[Dict[str, Any]] = None,
        custom_instructions: Optional[str] = None,
    ) -> AllegationResponse:
        """
        Regenerate response for a single allegation.

        Args:
            allegation: The allegation to respond to
            notice_type: Type of notice
            tone: Response tone
            language: Response language
            taxpayer_context: Additional context
            custom_instructions: Specific instructions for this allegation

        Returns:
            AllegationResponse for this allegation
        """
        logger.info(
            "Regenerating single allegation response",
            allegation_id=allegation.id,
            tone=tone,
        )

        try:
            # Build system prompt with optional custom instructions
            custom_section = ""
            if custom_instructions:
                sanitized_instructions = sanitize_user_input(custom_instructions, content_type="instructions")
                custom_section = f"\nADDITIONAL INSTRUCTIONS: {sanitized_instructions}"

            system_prompt = AllegationPromptTemplates.SINGLE_ALLEGATION_RESPONSE_SYSTEM.replace(
                "{custom_instructions}", custom_section
            )

            # Get tone and language instructions
            tone_instruction = AllegationPromptTemplates.get_tone_instruction(tone)
            language_instruction = AllegationPromptTemplates.get_language_instruction(language)

            # Build taxpayer context string
            taxpayer_context_str = "Not provided"
            if taxpayer_context:
                context_parts = []
                for key, value in taxpayer_context.items():
                    sanitized_value = sanitize_user_input(str(value), content_type="context")
                    context_parts.append(f"- {key}: {sanitized_value}")
                taxpayer_context_str = "\n".join(context_parts)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": AllegationPromptTemplates.SINGLE_ALLEGATION_RESPONSE_USER.format(
                    allegation_id=allegation.id,
                    allegation_description=allegation.description,
                    allegation_category=allegation.category,
                    legal_provision=allegation.legal_provision or "Not specified",
                    amount=allegation.amount_involved or "Not specified",
                    period=allegation.period or "Not specified",
                    notice_type=notice_type or "Unknown",
                    taxpayer_context=taxpayer_context_str,
                    tone=tone_instruction,
                    language_instruction=language_instruction,
                    additional_instructions=custom_section,
                )}
            ]

            response = await self.client.complete(
                messages=messages,
                temperature=0.3,
                max_tokens=2000,
                json_mode=True,
            )

            result = json.loads(response["content"])
            if not str(result.get("response_text") or "").strip():
                raise ValueError("AI returned an empty response")

            # Parse supporting evidence
            supporting_evidence = []
            for doc in result.get("supporting_evidence", []):
                supporting_evidence.append(SupportingDocument(
                    document_name=doc.get("document_name", ""),
                    document_type=doc.get("document_type", ""),
                    relevance=doc.get("relevance", ""),
                    available=bool(taxpayer_context) and doc.get("available", False),
                ))

            # Parse case law references
            case_law_refs = []
            for cl in result.get("case_law_references", []):
                case_law_refs.append(CaseLawReference(
                    citation=cl.get("citation", ""),
                    court=cl.get("court", ""),
                    principle=cl.get("principle", ""),
                    relevance=cl.get("relevance", ""),
                ))

            return AllegationResponse(
                allegation_id=allegation.id,
                response_text=result.get("response_text", ""),
                legal_basis=result.get("legal_basis", []),
                supporting_evidence=supporting_evidence,
                missing_information=result.get("missing_information", []),
                case_law_references=case_law_refs,
                confidence=result.get("confidence", 0.5),
                status=result.get("status", "needs_review"),
            )

        except Exception as e:
            logger.error(
                "Single allegation response regeneration failed",
                allegation_id=allegation.id,
                error=str(e),
            )
            raise ValueError("Unable to regenerate this allegation response. Please retry.") from e

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get LLM usage statistics"""
        return self.client.get_usage_stats()
