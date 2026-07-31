"""Tests for multi-provider AI gateway, router, and fallback."""
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User, AIResponseCache, UserRateLimit, UserAIPreference
from app.services.ai_gateway import AIGateway
from app.services.ai.registry import ProviderRegistry
from app.services.ai.router import TaskRouter
from app.services.ai.types import AIRequest, ProviderId, TaskType


class MultiProviderGatewayTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        ProviderRegistry.reset()

        self.user = User(username='ai_tester', email='ai@test.com')
        self.user.set_password('pass123')
        db.session.add(self.user)
        db.session.commit()

        self.gateway = AIGateway(api_key='your_test_placeholder_key')

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        ProviderRegistry.reset()
        self.app_context.pop()

    def test_legacy_generate_contract(self):
        text, tokens = self.gateway.generate(
            prompt='Write a short SaaS tagline',
            system_instruction='Be concise',
            model='gemini-2.5-flash',
            user_id=self.user.id,
        )
        self.assertIn('MOCK GENERATION', text)
        self.assertGreater(tokens, 0)

    def test_auto_routing_classifies_marketing(self):
        router = TaskRouter(self.gateway.registry)
        task = router.classify('Write high-converting Facebook ad copy for a CRM')
        self.assertEqual(task, TaskType.AD_COPY)
        pid, model = router.select(AIRequest(
            prompt='Write high-converting Facebook ad copy for a CRM',
            provider=ProviderId.AUTO,
        ))
        self.assertIn(pid, (ProviderId.OPENAI, ProviderId.ANTHROPIC, ProviderId.GEMINI, ProviderId.DEEPSEEK))
        self.assertTrue(model)

    def test_explicit_provider_openai_mock(self):
        text, tokens = self.gateway.generate(
            prompt='Write a CTA',
            provider='openai',
            user_id=self.user.id,
        )
        self.assertIn('openai', text.lower())
        self.assertGreater(tokens, 0)

    def test_fallback_when_primary_disabled(self):
        registry = self.gateway.registry
        openai = registry.get(ProviderId.OPENAI)
        anthropic = registry.get(ProviderId.ANTHROPIC)
        gemini = registry.get(ProviderId.GEMINI)
        deepseek = registry.get(ProviderId.DEEPSEEK)
        # Disable all except deepseek
        for p in (openai, anthropic, gemini):
            if p:
                p.set_enabled(False)
        if deepseek:
            deepseek.set_enabled(True)

        resp = self.gateway.execute(AIRequest(
            prompt='Quick summary of benefits',
            provider=ProviderId.AUTO,
            user_id=self.user.id,
        ))
        self.assertEqual(resp.provider, 'deepseek')
        self.assertIn('MOCK', resp.text)

    def test_cache_still_works(self):
        prompt = 'Unique cache probe for multi-provider gateway'
        r1, t1 = self.gateway.generate(prompt=prompt, model='gemini-2.5-flash', user_id=self.user.id)
        self.assertGreater(t1, 0)
        r2, t2 = self.gateway.generate(prompt=prompt, model='gemini-2.5-flash', user_id=self.user.id)
        self.assertEqual(t2, 0)
        self.assertEqual(r1, r2)
        # Pipeline injects a default system prompt — verify a cache row exists
        self.assertGreaterEqual(AIResponseCache.query.count(), 1)

    def test_user_ai_preferences_table(self):
        prefs = UserAIPreference(user_id=self.user.id, preferred_provider='auto', creativity=0.8)
        db.session.add(prefs)
        db.session.commit()
        loaded = UserAIPreference.query.get(self.user.id)
        self.assertEqual(loaded.preferred_provider, 'auto')
        self.assertEqual(loaded.creativity, 0.8)

    def test_rate_limit_still_enforced(self):
        db.session.add(UserRateLimit(
            user_id=self.user.id,
            monthly_credits_limit=100,
            credits_used=200,
            reset_date=datetime.utcnow() + timedelta(days=10),
        ))
        db.session.commit()
        with self.assertRaises(ValueError):
            self.gateway.generate(prompt='x', user_id=self.user.id)


if __name__ == '__main__':
    unittest.main()
