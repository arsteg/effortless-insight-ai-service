---
reference: EI-NAV-MOBILE
title: Mobile app navigation and screens
source_type: product_guide
summary: Mobile app structure - 6 tabs (Home, Notices, Scan, Tasks, Alerts, Profile) and what is web-only.
keywords: [navigation, mobile, app, tabs, where is, screen, android, ios]
categories: [navigation, mobile]
---

Mobile app has 6 tabs: Home, Notices, Scan (center camera button), Tasks, Alerts, Profile.

Screens (mobile routes):
- Home: /(tabs)/ - greeting, overdue banner, stats (active/due soon/overdue), upcoming deadlines, my tasks this week, usage summary.
- Notices: /(tabs)/notices - list with filters and search.
- Notice detail: /notices/{id} - tabs: overview, analysis (AI report), response (draft/submit), tasks, comments, documents, activity.
- Scan/upload: /(tabs)/upload - capture a notice with the camera or pick from the library.
- Tasks: /(tabs)/tasks; deadline calendar via the calendar button in the Tasks header -> /calendar.
- Alerts: /(tabs)/notifications.
- Profile: /(tabs)/profile - hub for settings: edit profile, change password, language (English/Hindi), notification preferences, appearance (light/dark), biometric unlock, integrations (GSTN portal: /settings/integrations, /settings/gstn-otp, /settings/gstn-settings, /settings/gstn-history), support tickets (/support), billing (/billing, /billing/plans, /billing/checkout).

Web-only features (tell the user to use the web app at app.effortlessinsight.in):
- Organization settings and GSTIN management (web: /settings/organization)
- Team member / CA invitations (web: /team)
- GST portal sync via Chrome extension (web: /gst-sync)
- Reports and analytics (web: /reports)
- Switching organizations (web header switcher)
