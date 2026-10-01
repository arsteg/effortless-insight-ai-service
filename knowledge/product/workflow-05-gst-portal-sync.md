---
reference: EI-W05
title: "Workflow: auto-sync notices from the GST portal (Chrome extension)"
source_type: product_guide
summary: Setting up the Chrome extension, monitoring GSTINs, reviewing and importing synced notices.
keywords: [gst sync, chrome extension, portal sync, auto sync, gstin monitoring, import notices]
categories: [workflow, gst_sync]
---

Automatic notice sync from the GST portal (web only):
1. Open GST Sync from the sidebar (web /gst-sync).
2. Follow the 5-step Extension Setup Guide: install the EffortlessInsight Chrome extension from the Chrome Web Store, log into gst.gov.in in Chrome, and the extension syncs the portal's "Notices and Orders" section while you are logged in.
3. Add the GSTINs to monitor under "Connected GSTINs" (plan limits on GSTIN count apply).
4. Synced items appear under "Synced Notices" - review them and import the ones you want as notices (import can also be set to automatic per GSTIN).
5. "Sync History" shows each sync session and its results.

Notes:
- The extension only works while someone is logged into the GST portal in Chrome; it rides that logged-in session.
- Not available on mobile. A separate OTP-based GSTN portal connection exists under Settings > Integrations (per-GSTIN, where offered).
- CA accounts can monitor client GSTINs; synced notices route to the right client workspace.
