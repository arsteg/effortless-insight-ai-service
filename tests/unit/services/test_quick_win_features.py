"""Offline regression checks for the extraction/report/handover data flow."""
import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, create_autospec
from uuid import uuid4

from app.schemas.handover import HandoverRequest
from app.schemas.internal import PipelineContext, EntityExtractionOutput, ClassificationOutput, AnalysisOutput, VerificationOutput
from app.schemas.report import VerificationResult
from app.services.extraction.amount_extractor import AmountExtractor
from app.services.extraction.entity_extractor import EntityExtractor
from app.services.pipeline.report_generator import ReportGenerator
from app.services.verification.verifier import Verifier
from app.services.llm.client import LLMClient
from app.services.llm.handover_generator import HandoverGenerator


class QuickWinTests(unittest.TestCase):
    def test_sample_flows_from_extraction_to_report(self):
        text = (Path(__file__).parents[2] / 'fixtures/gst-quick-wins-notice.txt').read_text()
        entities = asyncio.run(EntityExtractor().extract(text))
        self.assertEqual((entities.tax_amount, entities.penalty_amount, entities.interest_amount,
                          entities.total_amount, entities.late_fee_amount, entities.cess_amount,
                          entities.other_charges_amount),
                         (1000000, 100000, 50000, 1500000, 2000, 3000, 1000))
        discrepancies = Verifier()._verify_calculations(entities)
        self.assertEqual(len(discrepancies), 1)
        self.assertEqual(discrepancies[0].expected, 1156000)
        self.assertEqual(discrepancies[0].difference, 344000)
        self.assertEqual(discrepancies[0].severity, 'error')
        context = PipelineContext(
            notice_id=uuid4(), file_url='https://example.invalid/test.pdf',
            entity_output=EntityExtractionOutput(success=True, entities=entities),
            classification_output=ClassificationOutput(success=True, notice_type='DRC-01', notice_category='demand'),
            analysis_output=AnalysisOutput(success=True, risk_score=1, risk_level='low'),
            verification_output=VerificationOutput(success=True, verification=VerificationResult(is_verified=False, calculation_discrepancies=discrepancies)),
        )
        report = asyncio.run(ReportGenerator().generate(context))
        response = report.to_ai_report_data()
        self.assertEqual(response.metadata.late_fee_amount, 2000)
        self.assertEqual(response.metadata.cess_amount, 3000)
        self.assertEqual(response.metadata.other_charges_amount, 1000)
        self.assertEqual(report.risk_score, report.risk_assessment.score)
        self.assertEqual(report.risk_level, report.risk_assessment.level)
        self.assertTrue(response.risk_factors)
        self.assertEqual(response.calculation_discrepancies[0].actual, 1500000)
        self.assertTrue(any(i.category == 'calculations' and i.status == 'fail' for i in response.prefiling_checklist))
        self.assertTrue(any(i.category == 'limitation' and i.status == 'unknown' for i in response.prefiling_checklist))
        self.assertTrue(any(i.item == 'Appeal deadline verification' and i.status == 'unknown' for i in response.prefiling_checklist))
        entities.total_amount = 1156000
        self.assertEqual(Verifier()._verify_calculations(entities), [])

    def test_unlabelled_amounts_are_not_other_charges(self):
        extractor = AmountExtractor()
        amounts = extractor.extract_amounts('Turnover: Rs. 90,00,000\nOther charges: Rs. 1,000')
        self.assertEqual(extractor.identify_primary_amounts(amounts)[-1], 1000)

    def test_handover_uses_supported_llm_interface(self):
        generator = HandoverGenerator.__new__(HandoverGenerator)
        generator.llm_client = create_autospec(LLMClient, instance=True)
        generator.llm_client.complete = AsyncMock(return_value={'content': json.dumps({
            'background': 'Test case', 'work_completed': ['Reconciliation reviewed'],
            'pending_items': ['Reply'], 'next_steps': ['Draft reply'],
            'key_deadlines': [{'date': '2026-10-22', 'description': 'Reply'}],
            'key_contacts': ['Test Officer'], 'risk_summary': 'Urgent response',
        })})
        result = asyncio.run(generator.generate(HandoverRequest(notice_id=str(uuid4()), additional_context='Reconciliation reviewed')))
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.summary.work_completed, ['Reconciliation reviewed'])
        generator.llm_client.complete.assert_awaited_once()
        self.assertIn('Reconciliation reviewed', generator.llm_client.complete.call_args.kwargs['messages'][1]['content'])


if __name__ == '__main__':
    unittest.main()
