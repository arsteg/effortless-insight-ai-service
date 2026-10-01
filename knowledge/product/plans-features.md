---
reference: EI-PLANS
title: Subscription plans and feature gates
source_type: product_guide
summary: The real plan catalog (Notify Only free, Understand and Respond, Team, Enterprise, CA Professional) and which feature codes each unlocks.
keywords: [plans, pricing, subscription, upgrade, free, team, enterprise, feature not available, 402, billing]
categories: [billing, plans, features]
---

Plans (prices in INR):
- free "Notify Only" (Rs 0): unlimited notice DETECTION plus email/push deadline reminders. 1 user, 1 GSTIN, 1 GB. Does NOT include AI explanation, draft reply, or WhatsApp.
- understand_respond "Understand & Respond" (Rs 999/year or Rs 99/month; most popular): adds ai_explanation (AI analysis report), draft_reply (AI auto-draft), whatsapp_assistant, multilingual. Still 1 user, 1 GSTIN.
- team "Team" (Rs 1,999/year + Rs 499 per extra seat/year): adds collaboration (invite members/CA), advanced_analytics (Reports page), bulk_operations, data_export. 5 users, 10 GSTINs, 50 GB.
- enterprise (from Rs 9,999, contact sales): adds workflows (Tasks module), sso, api_access. Unlimited users/GSTINs.
- ca_operator "CA Professional" (Rs 0, granted by EffortlessInsight after CA verification): ALL features plus ca_client_management. Not shown on the pricing page.

Feature codes and what they gate:
- ai_explanation: the AI Analysis tab on a notice, AND this in-app AI assistant itself (free "Notify Only" users do not see the assistant; it unlocks with Understand & Respond or higher)
- draft_reply: the Auto-Draft button in the Response tab
- whatsapp_assistant: WhatsApp bot linking (Settings > WhatsApp)
- collaboration: Team page and member invitations
- advanced_analytics: Reports page
- workflows: Tasks module and workflow transitions
- bulk_operations: bulk archive/delete on the notices list
- data_export: CSV/XLSX/PDF export
- ca_client_management: CA client workspace

When a feature is locked the app returns FEATURE_NOT_AVAILABLE and shows an upgrade prompt. The assistant should say exactly which plan unlocks the feature and point to Settings > Billing (web) or the Billing section (mobile). Trials: 14 days by default (30 for enterprise); an expired or abandoned trial grants no features.

Usage limits also apply per plan: notices per month, user seats, GSTIN count, storage. Hitting a limit returns a message naming the limit; upgrading or removing unused items resolves it.
