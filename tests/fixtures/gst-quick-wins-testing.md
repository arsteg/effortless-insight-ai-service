# Five-feature manual test

Use `gst-quick-wins-notice.txt` as fictional test input. Copy it into Word and
export as a text PDF, or use another PDF editor. Before exporting:

1. Replace the GSTIN placeholder with a GSTIN registered in your test organization.
   An arbitrary GSTIN can fail organization validation before analysis is saved.
2. Give every new upload a unique notice number (0001, 0002, etc.) to avoid
   duplicate-notice rejection.
3. For an urgent-deadline test after October 2026, update the issue date to today,
   response deadline to three days later, and hearing date to four days later.

Apply the existing AddNoticeAiReportAnalysisFields migration if it is pending:

```powershell
dotnet ef database update --project src/EffortlessInsight.Api
```

Restart the API and AI service to load the fixes. Upload a NEW notice, or explicitly
reprocess an existing one. Refreshing the page or applying a migration cannot
populate analysis fields that were previously discarded.

## Expected results

| Check | Expected |
| --- | --- |
| Tax | 1,000,000 |
| Penalty | 100,000 |
| Interest | 50,000 |
| Late fee | 2,000 |
| Cess | 3,000 |
| Other charges | 1,000 |
| Sum of components in header | 1,156,000 |
| Total stated in document | 1,500,000 |
| Discrepancy | 344,000; severity error |
| Risk | Nonempty reasons; displayed score/level agrees with detailed assessment |
| Checklist | Calculations fail; limitation and appeal deadline require manual review |
| Deadline | Urgent warning when the response is due within three days |

The exact risk score and document recommendations can vary with extraction and
the test date.
Checklist categories depend on available input; every category need not appear.

In AI Analysis, click Generate Summary. Use this optional context:

> Test handover context: purchase register reviewed; supplier reconciliation still
> pending. Priya is taking over preparation of the draft reply. No reply has been
> filed and no final order has been received. Contact: Test Officer.

Expect structured background, completed work, pending items, next steps, deadlines
and contacts. Actual generation requires working AI-service LLM credentials.
The UI currently retains the generated summary only for the mounted page; it is
not saved as a permanent handover record.

For a negative control, create a second notice with a new reference and change
only Total demand to Rs. 11,56,000.00. No total-mismatch alert should appear.

## Verification performed

The offline regression test covers sample extraction, discrepancy arithmetic,
report response fields, consistent risk scoring, checklist generation, the balanced
negative control, and handover with a mocked LLM. It does not validate live OCR,
LLM output or browser rendering. The API regression checks persistence and clearing
stale fields on reprocessing through an in-memory database.
