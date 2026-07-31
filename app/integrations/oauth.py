"""Google OAuth helpers for GSC and GA4 (shared Google identity platform)."""
import secrets
import urllib.parse

import requests
from flask import current_app, session, url_for

PROVIDER_SCOPES = {
    'gsc': 'https://www.googleapis.com/auth/webmasters.readonly',
    'ga4': 'https://www.googleapis.com/auth/analytics.readonly',
}

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'


def integrations_mock_mode():
    """True when OAuth credentials are missing or mock flag is set."""
    if current_app.config.get('INTEGRATIONS_MOCK_MODE'):
        return True
    client_id = current_app.config.get('GOOGLE_OAUTH_CLIENT_ID', '')
    if not client_id or client_id.startswith('your_'):
        return True
    return False


def start_google_oauth(provider, user_id, project_id=None):
    """Build authorization URL and store OAuth state in session."""
    state = secrets.token_urlsafe(24)
    session['integration_oauth_state'] = {
        'state': state,
        'provider': provider,
        'user_id': user_id,
        'project_id': project_id,
    }
    params = {
        'client_id': current_app.config['GOOGLE_OAUTH_CLIENT_ID'],
        'redirect_uri': _redirect_uri(),
        'response_type': 'code',
        'scope': PROVIDER_SCOPES[provider],
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state,
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def _redirect_uri():
    return current_app.config.get('GOOGLE_OAUTH_REDIRECT_URI') or url_for(
        'integrations.google_callback', _external=True
    )


def exchange_code_for_tokens(code):
    """Exchange authorization code for access + refresh tokens."""
    from app.integrations.account_discovery import format_http_error
    try:
        resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                'code': code,
                'client_id': current_app.config['GOOGLE_OAUTH_CLIENT_ID'],
                'client_secret': current_app.config['GOOGLE_OAUTH_CLIENT_SECRET'],
                'redirect_uri': _redirect_uri(),
                'grant_type': 'authorization_code',
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise ValueError(f'Network error during token exchange: {exc}') from exc
    if not resp.ok:
        raise ValueError(format_http_error(resp))
    return resp.json()


def refresh_google_token(refresh_token):
    """Refresh an expired Google access token."""
    from app.integrations.account_discovery import format_http_error
    try:
        resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                'client_id': current_app.config['GOOGLE_OAUTH_CLIENT_ID'],
                'client_secret': current_app.config['GOOGLE_OAUTH_CLIENT_SECRET'],
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise ValueError(f'Network error during token refresh: {exc}') from exc
    if not resp.ok:
        raise ValueError(format_http_error(resp))
    return resp.json()
