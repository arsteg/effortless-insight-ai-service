---
reference: EI-ENTITIES
title: Main entities and status values
source_type: product_guide
summary: Glossary of core objects - notice, AI report, response, deadline, tasks, GST sync, invitations - with their status lifecycles.
keywords: [glossary, entities, notice status, processing status, priority, deadline, response status, definitions]
categories: [glossary, entities]
---

Organization: the tenant and security boundary. Owns GSTINs, members, notices, and the subscription. Users never see data from another organization.

Notice: a GST notice. Important fields:
- noticeType: DRC-01, DRC-01A, ASMT-10, SCN, REG-17, RFD-08, ADT-01, APL and other GST forms.
- status lifecycle: uploaded -> processing -> analyzed -> in_progress -> responded -> closed. Also: archived, failed.
- processingStatus (AI pipeline): queued -> ocr_processing -> extracting -> classifying -> analyzing -> completed, or failed (retry available).
- priority: low, medium, high, critical (computed from risk and deadline).
- responseDeadline (and extendedDeadline), amounts (tax, penalty, interest, total demand), gstin, issuing authority.
- source: upload, manual, or gstn_portal (synced from the GST portal).
- assignedTo: the member responsible; deadline reminders go to the assignee.

NoticeAiReport: the AI analysis of a notice - riskScore 0-100, riskLevel, summary in English and Hindi, plain-language explanation, actionItems, requiredDocuments, legalReferences.

NoticeResponse: a reply draft. Lifecycle: draft -> review -> approved -> submitted. Approval needs owner/admin/manager. "Submitted" means the human filed it on the GST portal and marked it; the app never files.

Deadlines and reminders: each notice can have response/payment/hearing deadlines. Automatic reminders at 7/3/1/0 days before (09:00 IST) to the assignee, a missed-deadline alert, daily digest, weekly summary. Custom reminders can be added per notice.

Tasks, Comments, Document Requests, Activity: collaboration items on a notice. Comments support @mentions and internal/external visibility (external = visible to the CA/client side).

GST sync (Chrome extension): GstClient = a monitored GSTIN; sync sessions pull the portal's "Notices and Orders"; synced items are staged for review and then imported as notices.

GSTN connection (Settings > Integrations): separate OTP-based GST-portal connection (GSP channel) per GSTIN.

Invitations: (a) organization invitation - owner/admin invites a member or CA into the org by email with a role; (b) CA client invitation - a CA invites a Business Owner client by GSTIN + email; expires in 14 days, max 3 resends; staged notices transfer when the client accepts.
