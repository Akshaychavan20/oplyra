"""Tests for the AI Agent Framework (above Multi-Provider AI Gateway)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import (
    User,
    AgentDefinition,
    AgentRun,
    AgentWorkflow,
    AgentMemory,
    AgentLog,
)
from app.services.agents.manager import AgentManager
from app.services.agents.catalog import AGENT_CATALOG, AUTO_AGENT_CHAIN
from app.services.agents.agents import create_agent, all_agent_keys
from app.services.ai_gateway import AIGateway
from app.services.ai.registry import ProviderRegistry


class AgentFrameworkTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        ProviderRegistry.reset()

        self.user = User(username='agent_tester', email='agents@test.com')
        self.user.set_password('pass123')
        db.session.add(self.user)
        db.session.commit()

        self.client = self.app.test_client()
        self.gateway = AIGateway(api_key='your_test_placeholder_key')
        self.manager = AgentManager(gateway=self.gateway)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        ProviderRegistry.reset()
        self.app_context.pop()

    def _login(self):
        return self.client.post('/login', data={
            'email_or_username': 'agent_tester',
            'password': 'pass123',
        }, follow_redirects=True)

    def test_catalog_has_eight_agents(self):
        keys = all_agent_keys()
        self.assertEqual(len(keys), 8)
        for expected in (
            'research', 'seo', 'content', 'campaign',
            'ads', 'analytics', 'email', 'social',
        ):
            self.assertIn(expected, keys)

    def test_seed_definitions_and_workflows(self):
        self.manager.ensure_seeded()
        self.assertEqual(AgentDefinition.query.count(), len(AGENT_CATALOG))
        self.assertGreaterEqual(AgentWorkflow.query.filter_by(is_system=True).count(), 1)
        # idempotent
        self.manager.ensure_seeded()
        self.assertEqual(AgentDefinition.query.count(), len(AGENT_CATALOG))

    def test_single_agent_run_via_gateway(self):
        run = self.manager.run(
            user_id=self.user.id,
            goal='Research competitors for a CRM SaaS',
            agent_key='research',
            brand_voice='Clear and confident',
        )
        self.assertEqual(run.status, 'completed')
        self.assertEqual(run.mode, 'single')
        self.assertTrue(run.final_output)
        self.assertIn('MOCK', run.final_output.upper())
        self.assertEqual(len(run.steps), 1)
        self.assertEqual(run.steps[0]['status'], 'completed')
        self.assertGreater(run.total_tokens, 0)
        self.assertGreater(AgentLog.query.filter_by(run_id=run.id).count(), 0)
        self.assertTrue(
            AgentMemory.query.filter_by(
                user_id=self.user.id,
                memory_type='previous_output',
                agent_key='research',
            ).first()
        )

    def test_auto_agent_chain(self):
        run = self.manager.run(
            user_id=self.user.id,
            goal='Plan a product launch for AI writing tools',
            mode='auto',
        )
        self.assertEqual(run.status, 'completed')
        self.assertEqual(run.mode, 'auto')
        self.assertEqual(len(run.steps), len(AUTO_AGENT_CHAIN))
        for step, key in zip(run.steps, AUTO_AGENT_CHAIN):
            self.assertEqual(step['agent_key'], key)
            self.assertEqual(step['status'], 'completed')
        self.assertIn('Research', run.final_output)
        self.assertIn('SEO', run.final_output)

    def test_workflow_run(self):
        self.manager.ensure_seeded()
        run = self.manager.run(
            user_id=self.user.id,
            goal='Build SEO content plan',
            workflow_key='content_seo_pipeline',
        )
        self.assertEqual(run.status, 'completed')
        self.assertEqual(run.mode, 'workflow')
        self.assertEqual(
            [s['agent_key'] for s in run.steps],
            ['research', 'seo', 'content'],
        )

    def test_create_custom_workflow(self):
        wf = self.manager.create_workflow(
            user_id=self.user.id,
            name='Ads Only',
            steps=['research', 'ads', 'invalid_key'],
        )
        self.assertEqual(wf.steps, ['research', 'ads'])

    def test_agent_uses_gateway_not_providers(self):
        agent = create_agent('content', gateway=self.gateway)
        result = agent.run(
            goal='Write a landing page hero',
            context={'brand_voice': 'Friendly'},
            user_id=self.user.id,
        )
        self.assertTrue(result['success'])
        self.assertIn('MOCK', result['output'].upper())

    def test_api_list_agents(self):
        self._login()
        res = self.client.get('/api/agents/')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['agents']), 8)

    def test_api_run_single(self):
        self._login()
        res = self.client.post('/api/agents/run', json={
            'goal': 'Write Meta ads for a fitness app',
            'agent_key': 'ads',
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['run']['status'], 'completed')
        self.assertTrue(data['run']['final_output'])

    def test_api_run_auto(self):
        self._login()
        res = self.client.post('/api/agents/run', json={
            'goal': 'Full funnel for eco packaging brand',
            'mode': 'auto',
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['run']['mode'], 'auto')
        self.assertEqual(len(data['run']['steps']), 4)

    def test_api_workflows_and_history(self):
        self._login()
        res = self.client.get('/api/agents/workflows')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])
        self.assertGreaterEqual(len(res.get_json()['workflows']), 1)

        self.client.post('/api/agents/run', json={
            'goal': 'Newsletter ideas',
            'agent_key': 'email',
        })
        hist = self.client.get('/api/agents/history')
        self.assertEqual(hist.status_code, 200)
        self.assertGreaterEqual(len(hist.get_json()['runs']), 1)

    def test_api_requires_goal(self):
        self._login()
        res = self.client.post('/api/agents/run', json={'agent_key': 'seo'})
        self.assertEqual(res.status_code, 400)

    def test_memory_brand_voice_persists(self):
        self.manager.run(
            user_id=self.user.id,
            goal='Draft social captions',
            agent_key='social',
            brand_voice='Witty and bold',
        )
        mem = AgentMemory.query.filter_by(
            user_id=self.user.id,
            memory_type='brand_voice',
        ).first()
        self.assertIsNotNone(mem)
        self.assertEqual(mem.value, 'Witty and bold')


if __name__ == '__main__':
    unittest.main()
