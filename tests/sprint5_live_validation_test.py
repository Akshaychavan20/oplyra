"""Sprint 5A live-validation stabilization tests (mocked Google API)."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app import create_app, db
from app.integrations.account_discovery import (
    build_connection_from_selection,
    list_ga4_properties,
    list_gsc_sites,
)
from app.integrations.adapters.google_analytics4 import GoogleAnalytics4Adapter
from app.integrations.adapters.google_search_console import GoogleSearchConsoleAdapter
from app.models import Membership, Organization, PlatformConnection, Project, User


class Sprint5LiveStabilizationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app.config['INTEGRATIONS_MOCK_MODE'] = False
        self.app.config['GOOGLE_OAUTH_CLIENT_ID'] = 'live-test-client-id'
        self.app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = 'live-test-secret'
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self._seed()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _seed(self):
        org = Organization(name='Live Test Org')
        db.session.add(org)
        db.session.commit()
        user = User(username='liveuser', email='live@oplyra.com')
        user.set_password('Password123!')
        db.session.add(user)
        db.session.commit()
        db.session.add(Membership(user_id=user.id, organization_id=org.id, role='admin'))
        self.project = Project(user_id=user.id, name='Live Client')
        db.session.add(self.project)
        db.session.commit()
        self.user = user

    def _live_conn(self, provider, meta):
        conn = PlatformConnection(
            user_id=self.user.id,
            provider=provider,
            status='connected',
            external_account_id='ext-1',
            external_account_name='Live Account',
            is_mock=False,
            connection_metadata=meta,
        )
        conn.access_token = 'live-access'
        conn.refresh_token = 'live-refresh'
        conn.token_expires_at = datetime.utcnow() + timedelta(hours=1)
        db.session.add(conn)
        db.session.commit()
        return conn

    @patch('app.integrations.account_discovery.requests.get')
    def test_list_gsc_sites_returns_all_options(self, mock_get):
        mock_get.return_value = MagicMock(
            ok=True,
            json=lambda: {
                'siteEntry': [
                    {'siteUrl': 'https://www.example.com/', 'permissionLevel': 'siteOwner'},
                    {'siteUrl': 'sc-domain:example.org', 'permissionLevel': 'siteFullUser'},
                ],
            },
        )
        options = list_gsc_sites('token')
        self.assertEqual(len(options), 2)
        self.assertEqual(options[0]['site_url'], 'https://www.example.com/')

    @patch('app.integrations.account_discovery.requests.get')
    def test_build_connection_uses_selected_site_not_first(self, mock_get):
        mock_get.return_value = MagicMock(
            ok=True,
            json=lambda: {
                'siteEntry': [
                    {'siteUrl': 'https://first.com/'},
                    {'siteUrl': 'https://second.com/'},
                ],
            },
        )
        options = list_gsc_sites('token')
        selected = options[1]
        built = build_connection_from_selection('gsc', selected, options)
        self.assertEqual(built['connection_metadata']['site_url'], 'https://second.com/')
        self.assertIn('second.com', built['external_account_id'])

    @patch('app.integrations.account_discovery.requests.get')
    def test_list_ga4_properties_empty(self, mock_get):
        mock_get.return_value = MagicMock(ok=True, json=lambda: {'accountSummaries': []})
        options = list_ga4_properties('token')
        self.assertEqual(options, [])

    @patch('app.integrations.adapters.google_search_console.safe_google_request')
    def test_gsc_live_sync_empty_sites_returns_no_importables(self, mock_req):
        mock_req.return_value = MagicMock(json=lambda: {'siteEntry': []})
        conn = self._live_conn('gsc', {'site_url': 'https://www.example.com/'})
        adapter = GoogleSearchConsoleAdapter()
        items = adapter.fetch_importable_campaigns(conn)
        self.assertEqual(items, [])

    def test_gsc_live_sync_without_site_url_raises_clear_error(self):
        conn = self._live_conn('gsc', {'site_url': None})
        adapter = GoogleSearchConsoleAdapter()
        with self.assertRaisesRegex(ValueError, 'No Search Console site'):
            adapter.fetch_metrics(conn)

    @patch('app.integrations.adapters.google_analytics4.refresh_google_token')
    def test_token_refresh_failure_marks_token_expired(self, mock_refresh):
        mock_refresh.side_effect = ValueError('invalid_grant: Token has been revoked.')
        conn = self._live_conn('ga4', {'property_id': 'properties/999'})
        adapter = GoogleAnalytics4Adapter()
        with self.assertRaisesRegex(ValueError, 'Token refresh failed'):
            adapter.refresh_access_token(conn)
        self.assertEqual(conn.status, 'token_expired')

    @patch('app.integrations.adapters.google_analytics4.safe_google_request')
    def test_ga4_network_error_surfaces_readable_message(self, mock_req):
        mock_req.side_effect = ValueError('Network error contacting Google: timeout')
        conn = self._live_conn('ga4', {'property_id': 'properties/999'})
        adapter = GoogleAnalytics4Adapter()
        with self.assertRaisesRegex(ValueError, 'Network error'):
            adapter.fetch_metrics(conn)


if __name__ == '__main__':
    unittest.main()
