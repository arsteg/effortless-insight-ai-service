---
reference: EI-ROLES
title: User roles and what each can do
source_type: product_guide
summary: The six organization roles (owner, admin, manager, member, ca, viewer), their permissions, and the CA account flag.
keywords: [roles, permissions, owner, admin, manager, member, ca, viewer, access, who can]
categories: [roles, permissions]
---

Every user belongs to one or more organizations; each membership has a role. The current organization is chosen at login and can be switched from the header (web).

Roles and capabilities:
- owner: everything, including billing, deleting the organization, and transferring ownership.
- admin: invite/remove members, change roles, manage GSTINs and org settings, delete notices, assign notices, approve responses. Cannot manage billing (view only), delete the org, or transfer ownership.
- manager: view all notices, create/edit/assign notices, approve responses, transition workflows, export reports. Cannot invite members or touch governance/billing.
- member: view/create/edit their own notices, comment, draft responses, create and complete tasks. Cannot assign, approve, delete, or see governance.
- ca (external collaborator): like member PLUS can view ALL notices in the client org, draft responses, comment, transition workflows. Can NEVER delete, assign, approve responses, or do any governance (invites, settings, billing, GSTIN changes). CA access may be time-limited and expire automatically.
- viewer: read-only across notices, workflow, and reports.

Special flag: a CA-as-distributor account (isCA) additionally gets the client workspace to invite and manage multiple Business Owner clients (web: /clients/invite).

If a user asks the assistant to do something their role does not allow, the backend rejects it; the assistant should explain which role is required and suggest asking the org owner/admin.

Only owner/admin can invite people. An admin can only assign roles lower than their own (member, viewer, ca).
