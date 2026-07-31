"""Regression tests for Production Phase 1 security blockers."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import (
    User, Organization, Membership, Project, Campaign, AgentRun,
)
from app.utils.security import safe_redirect_target, is_weak_secret_key, sanitize_html
from app.utils.org import get_user_org_id, user_is_org_admin
from app.integrations.token_vault import encrypt_token, decrypt_token, TokenVaultError
from app.services.ai.registry import ProviderRegistry
from config import ProductionConfig, TestingConfig


class Phase1SecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        ProviderRegistry.reset()

        self.admin = User(username='p1_admin', email='p1admin@test.com')
        self.admin.set_password('Pass1234!')
        self.editor = User(username='p1_editor', email='p1editor@test.com')
        self.editor.set_password('Pass1234!')
        self.outsider = User(username='p1_outsider', email='p1out@test.com')
        self.outsider.set_password('Pass1234!')
        db.session.add_all([self.admin, self.editor, self.outsider])
        db.session.flush()

        self.org = Organization(name='Phase1 Org', plan_tier='pro')
        self.other_org = Organization(name='Other Org', plan_tier='pro')
        db.session.add_all([self.org, self.other_org])
        db.session.flush()

        db.session.add(Membership(
            organization_id=self.org.id, user_id=self.admin.id, role='admin',
        ))
        db.session.add(Membership(
            organization_id=self.org.id, user_id=self.editor.id, role='editor',
        ))
        db.session.add(Membership(
            organization_id=self.other_org.id, user_id=self.outsider.id, role='admin',
        ))

        self.project = Project(
            name='Admin Client', user_id=self.admin.id, description='d',
        )
        db.session.add(self.project)
        db.session.flush()

        self.own_campaign = Campaign(
            name='Owned Campaign',
            organization_id=self.org.id,
            project_id=self.project.id,
            type='affiliate',
            status='active',
        )
        self.foreign_campaign = Campaign(
            name='Foreign Campaign',
            organization_id=self.other_org.id,
            type='affiliate',
            status='active',
        )
        db.session.add_all([self.own_campaign, self.foreign_campaign])
        db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        ProviderRegistry.reset()
        self.app_context.pop()

    def _login(self, username='p1_admin'):
        return self.client.post('/login', data={
            'email_or_username': username,
            'password': 'Pass1234!',
        }, follow_redirects=False)

    # --- SECRET_KEY / production config ---

    def test_weak_secret_detection(self):
        self.assertTrue(is_weak_secret_key('default-dev-secret-key'))
        self.assertTrue(is_weak_secret_key('generate-a-secure-secret-key-here'))
        self.assertTrue(is_weak_secret_key('short'))
        self.assertFalse(is_weak_secret_key('a' * 32))

    def test_production_rejects_weak_secret(self):
        class BoomApp:
            def __init__(self):
                self.config = {
                    'SECRET_KEY': 'default-dev-secret-key',
                    'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
                }

        with self.assertRaises(RuntimeError):
            ProductionConfig.init_app(BoomApp())

    def test_testing_config_has_strong_enough_secret(self):
        self.assertFalse(is_weak_secret_key(TestingConfig.SECRET_KEY))

    # --- Token vault fail-closed ---

    def test_token_vault_roundtrip(self):
        blob = encrypt_token('super-secret-token')
        self.assertIsInstance(blob, (bytes, bytearray))
        self.assertNotIn(b'super-secret-token', blob)
        self.assertEqual(decrypt_token(blob), 'super-secret-token')

    def test_token_vault_decrypt_fail_closed(self):
        with self.assertRaises(TokenVaultError):
            decrypt_token(b'not-a-valid-fernet-token')

    # --- Open redirect ---

    def test_safe_redirect_blocks_external(self):
        self.assertEqual(safe_redirect_target('https://evil.example/phish', '/'), '/')
        self.assertEqual(safe_redirect_target('//evil.example', '/'), '/')
        self.assertEqual(safe_redirect_target('/dashboard', '/'), '/dashboard')
        self.assertEqual(safe_redirect_target('/clients/1', '/home'), '/clients/1')

    def test_login_open_redirect_rejected(self):
        res = self.client.post(
            '/login?next=https://evil.example/steal',
            data={'email_or_username': 'p1_admin', 'password': 'Pass1234!'},
            follow_redirects=False,
        )
        self.assertIn(res.status_code, (302, 303))
        loc = res.headers.get('Location', '')
        self.assertNotIn('evil.example', loc)

    # --- Org helpers / agent scoping ---

    def test_get_user_org_id(self):
        self.assertEqual(get_user_org_id(self.admin.id), self.org.id)
        self.assertTrue(user_is_org_admin(self.admin.id, self.org.id))
        self.assertFalse(user_is_org_admin(self.editor.id, self.org.id))

    def test_agent_run_uses_membership_org(self):
        self._login('p1_admin')
        res = self.client.post('/api/agents/run', json={
            'goal': 'Summarize competitor landscape for CRM tools',
            'agent_key': 'research',
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        run = AgentRun.query.get(data['run']['id'])
        self.assertIsNotNone(run)
        self.assertEqual(run.organization_id, self.org.id)

    def test_agent_run_rejects_foreign_campaign(self):
        self._login('p1_admin')
        res = self.client.post('/api/agents/run', json={
            'goal': 'Should not access foreign campaign',
            'agent_key': 'research',
            'campaign_id': self.foreign_campaign.id,
        })
        self.assertEqual(res.status_code, 404)
        self.assertFalse(res.get_json()['success'])

    def test_agent_run_allows_own_campaign(self):
        self._login('p1_admin')
        res = self.client.post('/api/agents/run', json={
            'goal': 'Campaign scoped research goal for owned campaign',
            'agent_key': 'research',
            'campaign_id': self.own_campaign.id,
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

    # --- Tool permission authorization ---

    def test_editor_cannot_add_tool_permission(self):
        self._login('p1_editor')
        res = self.client.post('/api/tools/permissions', json={
            'tool_key': 'calculator',
            'effect': 'deny',
            'role': 'viewer',
        })
        self.assertEqual(res.status_code, 403)

    def test_admin_can_add_tool_permission(self):
        self._login('p1_admin')
        res = self.client.post('/api/tools/permissions', json={
            'tool_key': 'calculator',
            'effect': 'allow',
            'role': 'editor',
        })
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.get_json()['success'])

    def test_editor_cannot_enable_tool(self):
        self._login('p1_admin')
        # ensure tool exists via list (seeds registry)
        self.client.get('/api/tools/')
        self.client.get('/logout', follow_redirects=True)
        self._login('p1_editor')
        res = self.client.post('/api/tools/calculator/enable', json={'enabled': False})
        self.assertEqual(res.status_code, 403)

    # --- CSRF on unsafe methods ---

    def test_csrf_blocks_put_without_token(self):
        # Login while CSRF is disabled (TESTING=True), then enable checks
        self._login('p1_admin')
        self.app.config['TESTING'] = False
        try:
            with self.client.session_transaction() as sess:
                sess['csrf_token'] = 'expected-token'
            res = self.client.open(
                '/api/knowledge/documents/1',
                method='PUT',
                json={'title': 'x'},
                headers={'Content-Type': 'application/json'},
            )
            self.assertEqual(res.status_code, 400)
            body = res.get_json()
            self.assertFalse(body.get('success', True))
            self.assertIn('CSRF', body.get('error', ''))
        finally:
            self.app.config['TESTING'] = True

    # --- Security headers ---

    def test_security_headers_present(self):
        res = self.client.get('/login')
        self.assertEqual(res.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(res.headers.get('X-Frame-Options'), 'SAMEORIGIN')
        self.assertIn('Content-Security-Policy', res.headers)
        self.assertIn("default-src 'self'", res.headers.get('Content-Security-Policy', ''))

    # --- XSS sanitize helper ---

    def test_sanitize_html_strips_script(self):
        dirty = '<p>Hi</p><script>alert(1)</script><img src=x onerror=alert(1)>'
        clean = sanitize_html(dirty)
        self.assertNotIn('<script', clean.lower())
        self.assertNotIn('onerror', clean.lower())
        self.assertIn('<p>Hi</p>', clean)

    # --- Alembic wiring ---

    def test_migrate_extension_registered(self):
        from app import migrate
        self.assertIsNotNone(migrate)
        self.assertTrue(os.path.isdir(os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'migrations', 'versions',
        )))
        versions = os.listdir(os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'migrations', 'versions',
        ))
        self.assertTrue(any('baseline' in v for v in versions))

    def test_production_uses_alembic_only(self):
        self.assertTrue(ProductionConfig.USE_ALEMBIC_ONLY)


if __name__ == '__main__':
    unittest.main()
