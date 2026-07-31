from datetime import datetime, timedelta

from app.integrations.adapters.base import ReadOnlyAdapter
from app.integrations.adapters.google_api_utils import is_live_connection, safe_google_request
from app.integrations.adapters.mock_fixtures import ga4_importable, ga4_metrics
from app.integrations.oauth import refresh_google_token

GA4_DATA_API = 'https://analyticsdata.googleapis.com/v1beta'


class GoogleAnalytics4Adapter(ReadOnlyAdapter):
    provider = 'ga4'

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
        property_id = connection.connection_metadata.get('property_id')
        if not is_live_connection(connection):
            return ga4_metrics(property_id or 'properties/123456789')

        if not property_id:
            raise ValueError('No GA4 property linked to this connection. The Google account may have no Analytics properties.')

        self._ensure_token(connection)
        end = datetime.utcnow().date()
        start = end - timedelta(days=28)
        resp = safe_google_request(
            'POST',
            f'{GA4_DATA_API}/{property_id}:runReport',
            connection.access_token,
            json={
                'dateRanges': [{'startDate': start.isoformat(), 'endDate': end.isoformat()}],
                'metrics': [
                    {'name': 'sessions'},
                    {'name': 'totalUsers'},
                    {'name': 'bounceRate'},
                    {'name': 'averageSessionDuration'},
                ],
            },
        )
        payload = resp.json()
        rows = payload.get('rows', [])
        row = rows[0] if rows else {}
        vals = [v.get('value', '0') for v in row.get('metricValues', [])]
        return [
            {
                'metric_key': 'ga4.summary',
                'period_start': start,
                'period_end': end,
                'value': {
                    'property_id': property_id,
                    'sessions': int(float(vals[0])) if len(vals) > 0 else 0,
                    'users': int(float(vals[1])) if len(vals) > 1 else 0,
                    'bounce_rate': round(float(vals[2]) * 100, 1) if len(vals) > 2 else 0,
                    'avg_session_duration': round(float(vals[3]), 1) if len(vals) > 3 else 0,
                },
            }
        ]

    def fetch_importable_campaigns(self, connection):
        property_id = connection.connection_metadata.get('property_id')
        if not is_live_connection(connection):
            return ga4_importable(property_id or 'properties/123456789')

        if not property_id:
            return []

        self._ensure_token(connection)
        end = datetime.utcnow().date()
        start = end - timedelta(days=90)
        resp = safe_google_request(
            'POST',
            f'{GA4_DATA_API}/{property_id}:runReport',
            connection.access_token,
            json={
                'dateRanges': [{'startDate': start.isoformat(), 'endDate': end.isoformat()}],
                'dimensions': [{'name': 'sessionCampaignName'}],
                'metrics': [{'name': 'sessions'}],
                'limit': 25,
            },
        )
        items = []
        for row in resp.json().get('rows', []):
            name = row.get('dimensionValues', [{}])[0].get('value', '')
            if not name or name == '(not set)':
                continue
            safe_id = name.lower().replace(' ', '_')
            items.append({
                'external_campaign_id': f'ga4-campaign:{safe_id}',
                'external_campaign_name': name,
                'external_metadata': {'property_id': property_id, 'source': 'ga4'},
            })
        return items
