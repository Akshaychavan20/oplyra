from datetime import datetime, timedelta

import requests

from app.integrations.adapters.base import ReadOnlyAdapter
from app.integrations.adapters.google_api_utils import is_live_connection, safe_google_request
from app.integrations.adapters.mock_fixtures import gsc_importable, gsc_metrics
from app.integrations.oauth import integrations_mock_mode, refresh_google_token

GSC_API = 'https://www.googleapis.com/webmasters/v3/sites'


class GoogleSearchConsoleAdapter(ReadOnlyAdapter):
    provider = 'gsc'

    def refresh_access_token(self, connection):
        if not is_live_connection(connection):
            return False
        if not connection.refresh_token:
            connection.status = 'token_expired'
            raise ValueError('Refresh token missing. Disconnect and reconnect this integration.')
        try:
            data = refresh_google_token(connection.refresh_token)
        except Exception as exc:
            connection.status = 'token_expired'
            raise ValueError(f'Token refresh failed: {exc}. Disconnect and reconnect.') from exc
        connection.access_token = data['access_token']
        expires_in = data.get('expires_in', 3600)
        connection.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        connection.status = 'connected'
        return True

    def _ensure_token(self, connection):
        if not is_live_connection(connection):
            return
        if connection.token_expires_at and connection.token_expires_at <= datetime.utcnow() + timedelta(minutes=5):
            self.refresh_access_token(connection)

    def fetch_metrics(self, connection):
        site_url = connection.connection_metadata.get('site_url')
        if not is_live_connection(connection):
            return gsc_metrics(site_url or 'https://example.com')

        if not site_url:
            raise ValueError('No Search Console site linked to this connection. The Google account may have no verified properties.')

        self._ensure_token(connection)
        end = datetime.utcnow().date()
        start = end - timedelta(days=28)
        encoded_site = requests.utils.quote(site_url, safe='')
        resp = safe_google_request(
            'POST',
            f'https://www.googleapis.com/webmasters/v3/sites/{encoded_site}/searchAnalytics/query',
            connection.access_token,
            json={
                'startDate': start.isoformat(),
                'endDate': end.isoformat(),
                'dimensions': [],
                'rowLimit': 1,
            },
        )
        rows = resp.json().get('rows', [])
        row = rows[0] if rows else {}
        return [
            {
                'metric_key': 'gsc.summary',
                'period_start': start,
                'period_end': end,
                'value': {
                    'site_url': site_url,
                    'clicks': row.get('clicks', 0),
                    'impressions': row.get('impressions', 0),
                    'ctr': round(row.get('ctr', 0) * 100, 2),
                    'position': round(row.get('position', 0), 1),
                },
            }
        ]

    def fetch_importable_campaigns(self, connection):
        site_url = connection.connection_metadata.get('site_url')
        if not is_live_connection(connection):
            return gsc_importable(site_url or 'https://example.com')

        self._ensure_token(connection)
        resp = safe_google_request('GET', GSC_API, connection.access_token)
        items = []
        for entry in resp.json().get('siteEntry', []):
            url = entry.get('siteUrl', '')
            if not url:
                continue
            items.append({
                'external_campaign_id': f'gsc-site:{url}',
                'external_campaign_name': f'SEO Property — {url}',
                'external_metadata': {'site_url': url, 'source': 'gsc', 'permission': entry.get('permissionLevel')},
            })
        return items
