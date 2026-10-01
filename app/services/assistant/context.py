"""
Per-request assistant context, built from headers set by the .NET gateway.

The gateway authenticates the end user (JWT) and forwards:
- X-Organization-Id : current org (tenant scope)      [required]
- X-User-Id         : the asking user                  [required]
- X-User-Role       : org role (owner/admin/manager/member/ca/viewer)
- X-Plan            : plan code (for friendly gate explanations)
- X-Forwarded-Authorization : the user's own bearer token, used ONLY to
  execute read tools against the backend API on the user's behalf.
  It is never logged and never persisted.
"""

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from fastapi import Header, HTTPException


@dataclass
class AssistantContext:
    organization_id: UUID
    user_id: str
    user_role: str = "member"
    plan: str = ""
    user_token: Optional[str] = field(default=None, repr=False)  # never log

    @property
    def tools_available(self) -> bool:
        return bool(self.user_token)


async def get_assistant_context(
    x_organization_id: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_user_role: str = Header("member"),
    x_plan: str = Header(""),
    x_forwarded_authorization: Optional[str] = Header(None),
) -> AssistantContext:
    """FastAPI dependency validating the gateway-supplied identity headers."""
    if not x_organization_id or not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="Missing X-Organization-Id / X-User-Id headers (gateway required)",
        )
    try:
        org_id = UUID(x_organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Organization-Id")

    token = x_forwarded_authorization
    if token and token.lower().startswith("bearer "):
        token = token[7:]

    return AssistantContext(
        organization_id=org_id,
        user_id=x_user_id,
        user_role=(x_user_role or "member").lower(),
        plan=x_plan or "",
        user_token=token or None,
    )
