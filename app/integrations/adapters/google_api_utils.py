"""Shared adapter utilities for live Google API integrations."""
import requests

from app.integrations.oauth import integrations_mock_mode


def is_live_connection(connection):
    return not connection.is_mock and not integrations_mock_mode()


def google_headers(access_token):
    return {'Authorization': f'Bearer {access_token}'}


def raise_google_error(resp):
    from app.integrations.account_discovery import format_http_error
    raise ValueError(format_http_error(resp))


def safe_google_request(method, url, access_token, **kwargs):
    """Perform a Google API request with timeout and readable errors."""
    kwargs.setdefault('timeout', 30)
    headers = kwargs.pop('headers', {})
    headers.update(google_headers(access_token))
    try:
        resp = requests.request(method, url, headers=headers, **kwargs)
    except requests.RequestException as exc:
        raise ValueError(f'Network error contacting Google: {exc}') from exc
    if not resp.ok:
        raise_google_error(resp)
    return resp
