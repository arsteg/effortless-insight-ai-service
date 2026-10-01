---
reference: EI-NAV-WEB
title: Web app navigation and screens
source_type: product_guide
summary: Where everything lives in the web app - routes for notices, GST sync, team, settings, billing, support.
keywords: [navigation, web, where is, how to find, screen, page, route, sidebar, settings]
categories: [navigation, web]
---

Web app layout: left sidebar + header. Header has the organization switcher, the CA client selector (for CA accounts), notifications bell, and the user menu.

Main screens (web routes):
- Dashboard: /dashboard - stats, upcoming deadlines, activity, charts.
- Notices list: /notices - filter by status, priority, GSTIN, search, deadline. Useful links: /notices?overdue=true (overdue), /notices?dueWithinDays=7 (due this week).
- Notice detail: /notices/{id} - tabs: Overview, AI Analysis, Similar, AI Chat, Tasks, Comments, Response, Documents, Requests, Activity.
- Upload a notice: /notices/upload (file, batch, ZIP, or manual entry).
- GST portal sync: /gst-sync - Chrome extension setup guide, connected GSTINs, synced notices to review/import, sync history.
- Tasks: /tasks (needs workflows feature). Calendar: /calendar. Reports: /reports (needs advanced_analytics). Notifications: /notifications.
- Team: /team - members, invite member/CA, pending invitations (needs collaboration feature; owner/admin only).
- CA client workspace: /clients/invite - CA accounts only; invite Business Owner clients, manage prospects.
- Support: /support (create/track tickets), /support/{ticketId}.
- Settings hub: /settings with subpages:
  - /settings/profile (name, avatar), /settings/security (password, 2FA, sessions)
  - /settings/organization (org details, GSTIN add/remove - owner/admin)
  - /settings/billing (plan, invoices, upgrade), /select-plan, /checkout
  - /settings/notifications (reminder/digest preferences)
  - /settings/integrations (GSTN portal OTP connection)
  - /settings/whatsapp (link WhatsApp bot), /settings/task-templates, /settings/teams
- Onboarding (new account): /onboarding - create organization with GSTIN validation, trial starts.

Features not on mobile (send users here on web): organization settings, team invitations, GST-sync extension, reports.
