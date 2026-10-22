import unittest
from unittest.mock import AsyncMock, patch
from app.core.config import Settings, settings
from app.api.middleware.rate_limit import RateLimitMiddleware


class PlanRequestCapTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.caps = patch.object(settings, "plan_monthly_request_caps", Settings.model_fields["plan_monthly_request_caps"].default.copy())
        self.global_cap = patch.object(settings, "usage_global_org_monthly_cap", 5000)
        self.caps.start()
        self.global_cap.start()
        self.addCleanup(self.caps.stop)
        self.addCleanup(self.global_cap.stop)

    async def test_paid_plan_at_fifty_requests_is_not_blocked_as_unknown(self):
        redis = AsyncMock()
        redis.get.return_value = "50"
        allowed, used, cap = await RateLimitMiddleware(None)._check_monthly_cap(redis, "org", "understand_respond")
        self.assertTrue(allowed)
        self.assertEqual((used, cap), (50, 5000))

    async def test_real_limit_still_blocks(self):
        redis = AsyncMock()
        redis.get.return_value = "5000"
        allowed, _, _ = await RateLimitMiddleware(None)._check_monthly_cap(redis, "org", "understand_respond")
        self.assertFalse(allowed)

    def test_global_cap_and_unknown_plan_fallback_are_preserved(self):
        for plan in ("team", "ca_operator", "enterprise"):
            self.assertEqual(RateLimitMiddleware._effective_cap(plan), 5000)
        self.assertEqual(RateLimitMiddleware._effective_cap("unknown"), 50)
