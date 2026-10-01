---
reference: EI-W09
title: "Workflow: switch organization / CA switching between clients"
source_type: product_guide
summary: How users with multiple organizations (especially CAs) switch the active workspace.
keywords: [switch organization, change org, client selector, multiple organizations, workspace]
categories: [workflow, organizations]
---

Switching the active organization:
1. Web: use the organization switcher in the header. CA accounts additionally have a client selector in the header to jump between client workspaces.
2. Everything in the app (notices, tasks, reports) is scoped to the currently selected organization - you never see data from another org at the same time.
3. Mobile: there is no organization switcher today; users with multiple organizations should use the web app to switch.

Notes:
- A CA appears in each client org as an external CA member; their own CA organizations are managed separately.
- If an invitation gave the CA time-limited access, switching into that client stops working after the access expires.
