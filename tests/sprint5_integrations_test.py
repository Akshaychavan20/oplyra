"""Sprint 5A integration foundation tests."""
import json
import unittest
from datetime import datetime, timedelta

from app import create_app, db
from app.integrations.campaign_import import import_external_campaign
from app.integrations.sync_engine import SyncEngine
from app.models import (
    Campaign,
    ExternalCampaignMap,
    Membership,
    Organization,
    PlatformConnection,
    Project,
    SyncedMetric,
    User,
)


class Sprint5IntegrationsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app.config['INTEGRATIONS_MOCK_MODE'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self._seed()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _seed(self):
        self.org = Organization(name='Test Agency')
        db.session.add(self.org)
        db.session.commit()

        self.user = User(username='integrator', email='integrator@oplyra.com')
        self.user.set_password('Password123!')
        db.session.add(self.user)
        db.session.commit()

        db.session.add(Membership(user_id=self.user.id, organization_id=self.org.id, role='admin'))
        self.project = Project(user_id=self.user.id, name='Acme Client', description='Test client')
        db.session.add(self.project)
        db.session.commit()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user.id)
            sess['_fresh'] = True
            if 'csrf_token' not in sess:
                import secrets
                sess['csrf_token'] = secrets.token_hex(16)

    def _csrf(self):
        with self.client.session_transaction() as sess:
            return sess.get('csrf_token')

    def _create_mock_connection(self, provider='gsc'):
        conn = PlatformConnection(
            user_id=self.user.id,
            project_id=self.project.id,
            provider=provider,
            status='connected',
            external_account_id=f'mock-{provider}-1',
            external_account_name=f'Mock {provider.upper()}',
            is_mock=True,
            connection_metadata={'site_url': 'https://example.com'} if provider == 'gsc' else {'property_id': 'properties/123'},
        )
        conn.access_token = 'mock-token'
        conn.refresh_token = 'mock-refresh'
        conn.token_expires_at = datetime.utcnow() + timedelta(days=1)
        db.session.add(conn)
        db.session.commit()
        return conn

    def test_connected_apps_page_requires_auth(self):
        resp = self.client.get('/integrations/')
        self.assertEqual(resp.status_code, 302)

    def test_connected_apps_page_renders(self):
        self._login()
        resp = self.client.get('/integrations/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Connected Apps', resp.data)
        self.assertIn(b'Google Search Console', resp.data)

    def test_mock_connect_shows_property_selector(self):
        self._login()
        resp = self.client.get('/integrations/connect/gsc?project_id=%d' % self.project.id, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/integrations/select-property', resp.headers.get('Location', ''))

    def test_property_selection_creates_gsc_connection(self):
        self._login()
        self.client.get('/integrations/connect/gsc?project_id=%d' % self.project.id)
        token = self._csrf()
        resp = self.client.post(
            '/integrations/select-property',
            data={'csrf_token': token, 'property_id': 'https://demo-client.com'},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        conn = PlatformConnection.query.filter_by(user_id=self.user.id, provider='gsc').first()
        self.assertIsNotNone(conn)
        self.assertEqual(conn.connection_metadata.get('site_url'), 'https://demo-client.com')
        self.assertTrue(conn.is_mock)
        self.assertEqual(conn.status, 'connected')

    def test_property_selection_second_site_not_first(self):
        """Verify user choice is respected — not auto-first."""
        self._login()
        self.client.get('/integrations/connect/gsc')
        token = self._csrf()
        self.client.post(
            '/integrations/select-property',
            data={'csrf_token': token, 'property_id': 'https://example.com'},
            follow_redirects=True,
        )
        conn = PlatformConnection.query.filter_by(user_id=self.user.id, provider='gsc').first()
        self.assertEqual(conn.connection_metadata.get('site_url'), 'https://example.com')
        self.assertNotEqual(conn.connection_metadata.get('site_url'), 'https://demo-client.com')

    def test_manual_sync_stores_metrics_and_importables(self):
        conn = self._create_mock_connection('gsc')
        sync_run = SyncEngine.run_sync(conn.id, self.user.id)
        self.assertEqual(sync_run.status, 'success')
        self.assertGreater(sync_run.records_read, 0)

        metrics = SyncedMetric.query.filter_by(connection_id=conn.id).all()
        self.assertGreater(len(metrics), 0)

        maps = ExternalCampaignMap.query.filter_by(connection_id=conn.id).all()
        self.assertGreater(len(maps), 0)

    def test_duplicate_sync_does_not_duplicate_metrics(self):
        conn = self._create_mock_connection('ga4')
        SyncEngine.run_sync(conn.id, self.user.id)
        count_after_first = SyncedMetric.query.filter_by(connection_id=conn.id).count()
        SyncEngine.run_sync(conn.id, self.user.id)
        count_after_second = SyncedMetric.query.filter_by(connection_id=conn.id).count()
        self.assertEqual(count_after_first, count_after_second)

    def test_campaign_import_creates_campaign_once(self):
        conn = self._create_mock_connection('ga4')
        SyncEngine.run_sync(conn.id, self.user.id)
        ext = ExternalCampaignMap.query.filter_by(connection_id=conn.id).first()
        self.assertIsNotNone(ext)

        campaign1, created1 = import_external_campaign(
            self.user.id, conn.id, ext.external_campaign_id, self.project.id
        )
        self.assertTrue(created1)
        self.assertIsNotNone(campaign1.id)

        campaign2, created2 = import_external_campaign(
            self.user.id, conn.id, ext.external_campaign_id, self.project.id
        )
        self.assertFalse(created2)
        self.assertEqual(campaign1.id, campaign2.id)
        self.assertEqual(Campaign.query.filter_by(project_id=self.project.id).count(), 1)

    def test_sync_api_endpoint(self):
        self._login()
        conn = self._create_mock_connection('gsc')
        token = self._csrf()
        resp = self.client.post(
            '/integrations/sync/%d' % conn.id,
            headers={'X-CSRF-Token': token, 'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['success'])
        self.assertGreater(data['records_read'], 0)

    def test_disconnect_marks_connection_disconnected(self):
        self._login()
        conn = self._create_mock_connection('gsc')
        token = self._csrf()
        resp = self.client.post(
            '/integrations/disconnect/%d' % conn.id,
            headers={'X-CSRF-Token': token, 'X-Requested-With': 'XMLHttpRequest'},
            data={'csrf_token': token},
        )
        self.assertEqual(resp.status_code, 200)
        db.session.refresh(conn)
        self.assertEqual(conn.status, 'disconnected')

    def test_import_api_endpoint(self):
        self._login()
        conn = self._create_mock_connection('ga4')
        SyncEngine.run_sync(conn.id, self.user.id)
        ext = ExternalCampaignMap.query.filter_by(connection_id=conn.id).first()
        token = self._csrf()
        resp = self.client.post(
            '/integrations/import',
            headers={'X-CSRF-Token': token, 'Content-Type': 'application/json'},
            data=json.dumps({
                'connection_id': conn.id,
                'external_campaign_id': ext.external_campaign_id,
                'project_id': self.project.id,
            }),
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['success'])
        self.assertTrue(data['created'])

    def test_api_status_lists_connections(self):
        self._login()
        self._create_mock_connection('gsc')
        resp = self.client.get('/integrations/api/status')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['mock_mode'])
        self.assertEqual(len(data['connections']), 1)


if __name__ == '__main__':
    unittest.main()
