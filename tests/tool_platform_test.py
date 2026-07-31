"""Tests for Enterprise MCP + Tool Calling Platform."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import (
    User, Organization, Membership,
    ToolDefinition, ToolRun, ToolMarketplaceItem, ToolCategory,
)
from app.services.tools.service import ToolPlatformService
from app.services.tools.registry import ToolRegistry
from app.services.tools.executor import ToolExecutor
from app.services.tools.agent_bridge import ToolAgentBridge
from app.services.tools.types import ToolCallRequest
from app.services.tools.builtins import CalculatorTool, GoogleSearchTool
from app.services.ai_gateway import AIGateway
from app.services.ai.registry import ProviderRegistry


class ToolPlatformTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        ProviderRegistry.reset()

        self.user = User(username='tool_tester', email='tools@test.com')
        self.user.set_password('pass123')
        db.session.add(self.user)
        db.session.flush()
        self.org = Organization(name="Tool Tester Workspace", plan_tier='pro')
        db.session.add(self.org)
        db.session.flush()
        db.session.add(Membership(
            organization_id=self.org.id,
            user_id=self.user.id,
            role='admin',
        ))
        db.session.commit()

        self.client = self.app.test_client()
        self.svc = ToolPlatformService()
        self.gateway = AIGateway(api_key='your_test_placeholder_key')

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        ProviderRegistry.reset()
        self.app_context.pop()

    def _login(self):
        return self.client.post('/login', data={
            'email_or_username': 'tool_tester',
            'password': 'pass123',
        }, follow_redirects=True)

    def test_seed_builtins_and_categories(self):
        tools = self.svc.list_tools()
        keys = {t['key'] for t in tools}
        for expected in (
            'google_search', 'web_browser', 'http_request', 'calculator',
            'datetime', 'file_reader', 'knowledge_search', 'workspace_search',
        ):
            self.assertIn(expected, keys)
        cats = self.svc.list_categories()
        self.assertGreaterEqual(len(cats), 5)
        self.assertGreaterEqual(ToolCategory.query.count(), 5)

    def test_calculator_tool(self):
        tool = CalculatorTool()
        result = tool.execute({'expression': '2 + 3 * 4'})
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['result'], 14)

    def test_google_search_stub(self):
        tool = GoogleSearchTool()
        result = tool.execute({'query': 'oplyra ai', 'num_results': 2})
        self.assertTrue(result['success'])
        self.assertTrue(result['mock'])
        self.assertEqual(len(result['data']['results']), 2)

    def test_executor_runs_and_logs(self):
        executor = ToolExecutor()
        result = executor.execute(ToolCallRequest(
            tool_key='datetime',
            arguments={},
            user_id=self.user.id,
            organization_id=self.org.id,
        ))
        self.assertTrue(result.success)
        self.assertIsNotNone(result.run_id)
        run = ToolRun.query.get(result.run_id)
        self.assertEqual(run.status, 'completed')
        self.assertGreaterEqual(len(run.logs), 1)

    def test_disabled_tool_denied(self):
        self.svc.registry.ensure_seeded()
        self.svc.set_enabled('google_search', False)
        result = self.svc.run_tool(
            tool_key='google_search',
            arguments={'query': 'x'},
            user_id=self.user.id,
            organization_id=self.org.id,
        )
        self.assertFalse(result['success'])
        self.assertIn('disabled', (result.get('error') or '').lower())

    def test_marketplace_install_placeholder(self):
        items = self.svc.list_marketplace()
        self.assertGreaterEqual(len(items), 5)
        result = self.svc.install('slack', self.user.id)
        self.assertTrue(result['tool']['is_installed'])
        self.assertFalse(result['tool']['is_enabled'])  # OAuth pending
        self.assertEqual(result['tool']['provider_type'], 'marketplace')

    def test_agent_bridge_with_tools(self):
        bridge = ToolAgentBridge(agent_manager=__import__(
            'app.services.agents.manager', fromlist=['AgentManager']
        ).AgentManager(gateway=self.gateway))
        out = bridge.run_agent_with_tools(
            user_id=self.user.id,
            goal='Find competitor insights for CRM SaaS',
            agent_key='research',
            organization_id=self.org.id,
            tool_keys=['google_search', 'knowledge_search'],
        )
        self.assertIn('agent_run', out)
        self.assertEqual(out['agent_run']['status'], 'completed')
        self.assertGreaterEqual(len(out['tool_results']), 1)
        self.assertTrue(any(r.get('success') for r in out['tool_results']))

    def test_mcp_local_lists_tools(self):
        tools = self.svc.mcp_list_tools()
        self.assertGreaterEqual(len(tools), 8)

    def test_api_list_and_run(self):
        self._login()
        res = self.client.get('/api/tools/')
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.get_json()['tools']), 8)

        run = self.client.post('/api/tools/run', json={
            'tool_key': 'calculator',
            'arguments': {'expression': '10/2'},
        })
        self.assertEqual(run.status_code, 200)
        self.assertTrue(run.get_json()['success'])
        self.assertEqual(run.get_json()['result']['data']['result'], 5.0)

    def test_api_marketplace_and_history(self):
        self._login()
        mp = self.client.get('/api/tools/marketplace')
        self.assertEqual(mp.status_code, 200)
        self.assertGreater(len(mp.get_json()['items']), 0)

        self.client.post('/api/tools/run', json={
            'tool_key': 'datetime',
            'arguments': {},
        })
        hist = self.client.get('/api/tools/history')
        self.assertEqual(hist.status_code, 200)
        self.assertGreaterEqual(len(hist.get_json()['runs']), 1)

    def test_api_install(self):
        self._login()
        res = self.client.post('/api/tools/install', json={'key': 'notion'})
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.get_json()['success'])

    def test_api_categories(self):
        self._login()
        res = self.client.get('/api/tools/categories')
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.get_json()['categories']), 0)

    def test_validation_missing_arg(self):
        result = self.svc.run_tool(
            tool_key='google_search',
            arguments={},
            user_id=self.user.id,
        )
        self.assertFalse(result['success'])


if __name__ == '__main__':
    unittest.main()
