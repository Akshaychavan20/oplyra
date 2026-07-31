"""Closed Beta end-to-end workflow + bug-hunt tests.

Drives the full solo-marketer workflow through the Flask test client and
intentionally breaks workflows (bad input, unauthorized access, missing data)
to verify graceful handling. Uses the 'testing' config (CSRF disabled,
in-memory SQLite, integrations mock mode, Gemini mock mode).
"""
import json
import unittest

from app import create_app, db
from app.models import Campaign, Content, PlatformConnection, Project, Task, User


class BetaE2EWorkflowTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app.config['INTEGRATIONS_MOCK_MODE'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # ---- helpers ---------------------------------------------------------
    def _register(self, username='marketer', email='m@oplyra.com', password='Password123!'):
        return self.client.post('/register', data={
            'username': username,
            'email': email,
            'password': password,
            'confirm_password': password,
        }, follow_redirects=True)

    def _create_client(self, name='Acme Corp', description='Retail client'):
        return self.client.post('/clients/new', data={
            'name': name, 'description': description,
        }, follow_redirects=True)

    def _first_project(self):
        return Project.query.first()

    # ---- happy-path workflow --------------------------------------------
    def test_full_workflow_register_to_content(self):
        # Register (auto-login)
        resp = self._register()
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(User.query.filter_by(email='m@oplyra.com').first())

        # Home dashboard renders
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)

        # Create client
        self._create_client()
        project = self._first_project()
        self.assertIsNotNone(project)

        # View client detail
        resp = self.client.get(f'/clients/{project.id}')
        self.assertEqual(resp.status_code, 200)

        # Create campaign (JSON)
        resp = self.client.post('/content/campaigns', json={
            'name': 'Summer Launch', 'type': 'social_campaign',
            'project_id': project.id, 'budget': 500,
        })
        self.assertEqual(resp.status_code, 201)
        campaign = Campaign.query.first()
        self.assertIsNotNone(campaign)

        # Campaign workspace renders
        resp = self.client.get(f'/content/campaigns/{campaign.id}/workspace')
        self.assertEqual(resp.status_code, 200)

        # Generate content (mock Gemini) — blog
        resp = self.client.post('/content/generate', data={
            'project_id': project.id, 'type': 'blog', 'topic': 'Best Widgets 2026',
            'audience': 'Small business owners', 'tone': 'professional',
        })
        self.assertEqual(resp.status_code, 200, resp.data)
        data = json.loads(resp.data)
        self.assertTrue(data['success'], data)
        content = Content.query.first()
        self.assertIsNotNone(content)

        # View generated content
        resp = self.client.get(f'/content/view/{content.id}')
        self.assertEqual(resp.status_code, 200)

    def test_generate_all_content_types(self):
        self._register()
        self._create_client()
        project = self._first_project()

        cases = [
            {'type': 'blog', 'topic': 'X'},
            {'type': 'email', 'product_name': 'WidgetPro'},
            {'type': 'facebook_post', 'product_name': 'WidgetPro'},
            {'type': 'product_review', 'product_name': 'WidgetPro'},
            {'type': 'ad_copy', 'product_name': 'WidgetPro'},
        ]
        for case in cases:
            payload = {'project_id': project.id, 'audience': 'SMB', 'tone': 'professional'}
            payload.update(case)
            resp = self.client.post('/content/generate', data=payload)
            self.assertEqual(resp.status_code, 200, f"{case['type']}: {resp.data}")
            self.assertTrue(json.loads(resp.data)['success'], case['type'])

    def test_integration_connect_sync_import_flow(self):
        self._register()
        self._create_client()
        project = self._first_project()

        # Connect (mock) -> redirects to property selector
        resp = self.client.get('/integrations/connect/gsc', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/integrations/select-property', resp.headers.get('Location', ''))

        # Select property
        resp = self.client.post('/integrations/select-property', data={
            'property_id': 'https://example.com',
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        conn = PlatformConnection.query.filter_by(provider='gsc').first()
        self.assertIsNotNone(conn)

        # Sync
        resp = self.client.post(f'/integrations/sync/{conn.id}',
                                headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(json.loads(resp.data)['success'])

        # Import a campaign
        from app.models import ExternalCampaignMap
        ext = ExternalCampaignMap.query.filter_by(connection_id=conn.id).first()
        self.assertIsNotNone(ext)
        resp = self.client.post('/integrations/import', json={
            'connection_id': conn.id,
            'external_campaign_id': ext.external_campaign_id,
            'project_id': project.id,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(json.loads(resp.data)['success'])

    def test_task_create_and_toggle(self):
        self._register()
        resp = self.client.post('/api/tasks/new', json={'title': 'Review FB Ads'})
        self.assertEqual(resp.status_code, 201)
        task = Task.query.first()
        self.assertIsNotNone(task)
        resp = self.client.post(f'/api/tasks/toggle/{task.id}')
        self.assertEqual(resp.status_code, 200)

    # ---- bug hunt: break workflows --------------------------------------
    def test_generate_missing_required_fields_returns_400(self):
        self._register()
        self._create_client()
        project = self._first_project()
        resp = self.client.post('/content/generate', data={
            'project_id': project.id, 'type': 'blog',  # missing audience/tone
        })
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(json.loads(resp.data)['success'])

    def test_generate_unauthorized_project_returns_403(self):
        # user A creates project
        self._register(username='usera', email='a@oplyra.com')
        self._create_client(name='A Client')
        project_a = self._first_project()
        self.client.get('/logout', follow_redirects=True)

        # user B tries to generate into A's project
        self._register(username='userb', email='b@oplyra.com')
        resp = self.client.post('/content/generate', data={
            'project_id': project_a.id, 'type': 'blog', 'topic': 'x',
            'audience': 'y', 'tone': 'z',
        })
        self.assertEqual(resp.status_code, 403)

    def test_view_nonexistent_content_returns_404(self):
        self._register()
        resp = self.client.get('/content/view/99999')
        self.assertEqual(resp.status_code, 404)

    def test_view_other_users_project_returns_403(self):
        self._register(username='usera', email='a@oplyra.com')
        self._create_client(name='A Client')
        project_a = self._first_project()
        self.client.get('/logout', follow_redirects=True)

        self._register(username='userb', email='b@oplyra.com')
        resp = self.client.get(f'/clients/{project_a.id}')
        self.assertEqual(resp.status_code, 403)

    def test_create_client_empty_name_rejected(self):
        self._register()
        self.client.post('/clients/new', data={'name': '  '}, follow_redirects=True)
        self.assertEqual(Project.query.count(), 0)

    def test_campaign_missing_name_returns_400(self):
        self._register()
        resp = self.client.post('/content/campaigns', json={'type': 'social_campaign'})
        self.assertEqual(resp.status_code, 400)

    def test_protected_route_requires_login(self):
        resp = self.client.get('/clients/', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers.get('Location', ''))

    def test_unknown_route_returns_404(self):
        self._register()
        resp = self.client.get('/this/route/does/not/exist')
        self.assertEqual(resp.status_code, 404)

    def test_duplicate_email_registration_rejected(self):
        self._register(email='dup@oplyra.com', username='first')
        self.client.get('/logout', follow_redirects=True)
        self._register(email='dup@oplyra.com', username='second')
        self.assertEqual(User.query.filter_by(email='dup@oplyra.com').count(), 1)

    def test_sync_disconnected_connection_fails_gracefully(self):
        self._register()
        self._create_client()
        # Create + disconnect
        self.client.get('/integrations/connect/gsc')
        self.client.post('/integrations/select-property', data={'property_id': 'https://example.com'}, follow_redirects=True)
        conn = PlatformConnection.query.filter_by(provider='gsc').first()
        self.client.post(f'/integrations/disconnect/{conn.id}',
                         headers={'X-Requested-With': 'XMLHttpRequest'})
        resp = self.client.post(f'/integrations/sync/{conn.id}',
                                headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(json.loads(resp.data)['success'])


if __name__ == '__main__':
    unittest.main()
