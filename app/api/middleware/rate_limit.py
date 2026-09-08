"""
Rate limiting and per-plan usage-cap middleware.

Two independent protections on the cost-incurring (LLM / embeddings) endpoints:

1. Short-term rate limit — a fixed-window counter (default 100 requests / 60s)
   that stops bursts and runaway retry loops.
2. Monthly usage cap — a per-organization, per-calendar-month counter compared
   against the caller's plan quota, so pricing tiers are actually enforced and a
   single org cannot run unlimited paid AI calls.

Counters live in Redis (``settings.redis_url``) so they stay correct across the
service's multiple worker processes (an in-memory counter would undercount by a
factor of the worker count). The caller is identified from request headers set
by the .NET API — the only authenticated caller:

    X-Organization-Id : the org the work is billed to. When absent, a shared
                        ``__global__`` bucket is used so the wallet is still
                        protected before the header is wired up on the API side.
    X-Plan            : the caller's plan code (free/starter/professional/...);
                        selects the monthly cap. Falls back to the "default"
                        plan when absent or unknown.

If Redis is unavailable, behaviour follows ``settings.rate_limit_fail_open``
(default: allow the request but log a warning) — availability over strictness,
with the absolute global monthly ceiling as the backstop.

Only the monthly counter for *successful* (HTTP < 400) cost calls is recorded,
so failed requests are not charged against a customer's quota.
"""

import time
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = structlog.get_logger()

# Cost-incurring endpoints are mounted under these prefixes. Only POSTs are
# limited — GETs here (e.g. /embeddings/stats) do not call the LLM.
COST_PATH_PREFIXES = ("/api/v1/process", "/api/v1/embeddings")

GLOBAL_BUCKET = "__global__"
# ~40 days: comfortably longer than any calendar month so a month's counter
# survives until it is naturally superseded by the next month's key.
MONTHLY_TTL_SECONDS = 60 * 60 * 24 * 40


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed rate limiting + per-plan monthly usage caps."""

    def __init__(self, app):
        super().__init__(app)
        self._redis = None  # lazily created, then reused (redis-py pools internally)

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.from_url(
                settings.redis_url, encoding="utf-8", decode_responses=True
            )
        return self._redis

    @staticmethod
    def _is_cost_path(request: Request) -> bool:
        if request.method != "POST":
            return False
        return any(request.url.path.startswith(p) for p in COST_PATH_PREFIXES)

    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled or not self._is_cost_path(request):
            return await call_next(request)

        org = request.headers.get("X-Organization-Id") or GLOBAL_BUCKET
        plan = (request.headers.get("X-Plan") or "default").strip().lower()

        client = None
        try:
            client = await self._get_redis()

            # 1) Short-term burst limit
            allowed, retry_after = await self._check_rate_limit(client, org)
            if not allowed:
                logger.warning(
                    "Rate limit exceeded",
                    org=org, path=request.url.path, retry_after=retry_after,
                )
                return self._limited(
                    request, 429, "RATE_LIMIT",
                    "Too many requests. Please retry shortly.",
                    retry_after=retry_after,
                )

            # 2) Monthly per-plan usage cap
            if settings.usage_caps_enabled:
                ok, used, cap = await self._check_monthly_cap(client, org, plan)
                if not ok:
                    logger.warning(
                        "Monthly usage cap reached",
                        org=org, plan=plan, used=used, cap=cap, path=request.url.path,
                    )
                    return self._limited(
                        request, 429, "USAGE_CAP_EXCEEDED",
                        f"Monthly AI usage limit reached ({used}/{cap}). "
                        "Upgrade your plan to continue.",
                        extra={"used": used, "cap": cap, "plan": plan},
                    )
        except Exception as e:
            # Counter store failure — do not take the service down over a counter.
            logger.warning(
                "Rate-limit store unavailable; applying fail-open policy",
                error=str(e), fail_open=settings.rate_limit_fail_open,
                path=request.url.path,
            )
            if not settings.rate_limit_fail_open:
                return self._limited(
                    request, 503, "RATE_LIMIT_UNAVAILABLE",
                    "Service temporarily unavailable, please retry.",
                )
            return await call_next(request)

        response = await call_next(request)

        # Charge the monthly quota only for successful cost calls.
        if (
            settings.usage_caps_enabled
            and client is not None
            and response.status_code < 400
        ):
            try:
                await self._record_usage(client, org)
            except Exception as e:
                logger.warning("Failed to record usage", error=str(e), org=org)

        return response

    # ----- rate limiting (fixed window) -----------------------------------

    async def _check_rate_limit(self, client, org: str):
        """Return (allowed, retry_after_seconds)."""
        period = settings.rate_limit_period
        limit = settings.rate_limit_requests
        if limit <= 0 or period <= 0:
            return True, 0

        now = int(time.time())
        window = now // period
        key = f"ratelimit:{org}:{window}"

        count = await client.incr(key)
        if count == 1:
            await client.expire(key, period)

        if count > limit:
            retry_after = period - (now % period)
            return False, max(retry_after, 1)
        return True, 0

    # ----- monthly usage cap ----------------------------------------------

    @staticmethod
    def _month_key(org: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m")
        return f"usage:{org}:{stamp}"

    @staticmethod
    def _effective_cap(plan: str) -> int:
        """Lowest applicable cap (0 => unlimited)."""
        caps = settings.plan_monthly_request_caps
        plan_cap = caps.get(plan, caps.get("default", 0))
        limits = [
            c for c in (plan_cap, settings.usage_global_org_monthly_cap)
            if c and c > 0
        ]
        return min(limits) if limits else 0

    async def _check_monthly_cap(self, client, org: str, plan: str):
        """Return (allowed, used, cap). cap == 0 means unlimited."""
        cap = self._effective_cap(plan)
        if cap <= 0:
            return True, 0, 0
        used = int(await client.get(self._month_key(org)) or 0)
        return used < cap, used, cap

    async def _record_usage(self, client, org: str):
        key = self._month_key(org)
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, MONTHLY_TTL_SECONDS)

    # ----- response helper -------------------------------------------------

    @staticmethod
    def _limited(
        request: Request,
        status: int,
        code: str,
        message: str,
        retry_after: Optional[int] = None,
        extra: Optional[dict] = None,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        content = {
            "success": False,
            "error": message,
            "code": code,
            "request_id": request_id,
        }
        if extra:
            content.update(extra)
        headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
        return JSONResponse(status_code=status, content=content, headers=headers)
